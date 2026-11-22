"""Final verdict page data: deterministic, evidence-traced recommendations (synthetic)."""

import json

from vendor_review.brief import BuyerBrief
from vendor_review.pipeline import (
    Candidate,
    Evidence,
    RequirementAnswer,
    V1Result,
    build_spec,
    compare,
)
from vendor_review.searches import SearchStore
from vendor_review.verdict import build_verdict


def brief():
    return BuyerBrief(
        service_category="multi-carrier shipping platform",
        use_case="ship D2C orders",
        must_haves=["Shopify integration", "NDR management"],
        budget={"max_inr": 60000, "period": "monthly"},
        scale="9,000 orders/month",
        timeline="Go live within 6 weeks",
        top_k=2,
    )


def answer(qid, verdict, quote="", url="https://a.example/x"):
    ev = [Evidence(url=url, passage_or_field=quote)] if quote else []
    return RequirementAnswer(
        question_id=qid, verdict=verdict, summary=verdict, evidence=ev, missing="Ask vendor"
    )


def run_row(tmp_path, answers_by_vendor):
    b = brief()
    store = SearchStore(tmp_path / "s.sqlite")
    sid = store.create_session()
    rid, _ = store.start_run(sid, b)
    spec = build_spec(rid, b)
    cands = [Candidate(name=n, domain=f"{n.lower()}.example") for n in answers_by_vendor]
    results = {}
    for cand in cands:
        verdicts = answers_by_vendor[cand.name]
        results[cand.key] = V1Result(
            candidate_key=cand.key,
            status="completed",
            answers=[
                answer(q.id, *verdicts.get(q.kind, ("cannot_verify",))) for q in spec.questions
            ],
        )
        store.mark_evaluating(rid, cand.key)
        store.save_evaluation(rid, cand.key, results[cand.key])
    comp = compare(spec, cands, results)
    store.update_run(
        rid,
        status="done",
        candidates=json.dumps([c.model_dump(mode="json") for c in cands]),
        comparison=comp.model_dump_json(),
    )
    return store.run(rid), store.evaluations(rid)


def test_recommends_only_when_every_critical_requirement_has_evidence(tmp_path):
    run, evals = run_row(
        tmp_path,
        {
            "Alpha": {
                "must_have": ("supported", "Alpha does it."),
                "budget": ("supported", "From ₹40,000 a month."),
            },
            "Beta": {"must_have": ("partially_supported", "Beta partly.")},
        },
    )
    v = build_verdict(run, evals)
    assert v["verdict"] == "recommend" and v["headline"].endswith("Alpha")
    assert v["vendors"][0]["supported"][0]["quote"] == "Alpha does it."
    titles = [r["title"] for r in v["recommendations"]]
    assert titles[0] == "Run a scoped pilot with Alpha"
    assert "Get written quotes" not in titles  # pricing was evidenced
    assert any(t.startswith("Pilot pass/fail") for t in titles)
    assert any("6 weeks" in r["detail"] for r in v["recommendations"])


def test_leading_candidate_and_common_gaps_when_nobody_is_proven(tmp_path):
    run, evals = run_row(
        tmp_path,
        {"Alpha": {"must_have": ("partially_supported", "Alpha partly.")}, "Beta": {}},
    )
    v = build_verdict(run, evals)
    assert v["verdict"] == "leading_candidate" and "Alpha" in v["headline"]
    titles = [r["title"] for r in v["recommendations"]]
    assert titles[0].startswith("Shortlist for demos: Alpha")
    assert any(t.startswith("Ask every vendor to prove") for t in titles)
    assert "Get written quotes" in titles
    assert v["caveats"] and "not independently verified" not in v["headline"]


def test_no_evidence_verdict_never_recommends(tmp_path):
    run, evals = run_row(tmp_path, {"Alpha": {}, "Beta": {}})
    v = build_verdict(run, evals)
    assert v["verdict"] == "no_evidence" and v["leader_key"] is None
    assert v["recommendations"][0]["title"] == "Widen the search or ask vendors directly"


def test_verdict_endpoint_waits_for_finished_comparison(tmp_path):
    from fastapi.testclient import TestClient
    from pydantic import SecretStr

    from vendor_review.config import Settings
    from vendor_review.demo import DemoDiscovery, DemoV1
    from vendor_review.web.app import Runtime, create_app

    rt = Runtime(Settings(data_dir=tmp_path, gemini_api_key=SecretStr("")), model=None,
                 v1=DemoV1(delay=0), discovery=DemoDiscovery())  # fmt: skip
    rt.model = None
    with TestClient(create_app(rt)) as c:
        sid = c.post("/api/sessions").json()["id"]
        assert c.get(f"/api/sessions/{sid}/verdict").status_code == 409
        full = brief().model_copy(update={"geography": ["Pan-India"]})
        c.put(f"/api/sessions/{sid}/brief", json={"brief": full.model_dump()})
        assert c.post(f"/api/sessions/{sid}/search", json={"confirm": True}).status_code == 200
        import time

        for _ in range(60):
            if c.get(f"/api/sessions/{sid}/search").json()["status"] == "done":
                break
            time.sleep(0.05)
        v = c.get(f"/api/sessions/{sid}/verdict").json()
        assert v["verdict"] in {"recommend", "leading_candidate", "no_evidence"}
        assert v["vendors"] and v["recommendations"] and v["caveats"]
        assert c.get("/verdict").status_code == 200
