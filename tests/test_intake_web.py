import time

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage
from pydantic import SecretStr

from vendor_review.brief import BuyerBrief, merge_brief, missing_required
from vendor_review.chat_intake import IntakeDecision, parse_budget
from vendor_review.config import Settings
from vendor_review.demo import DemoDiscovery, DemoV1
from vendor_review.pipeline import (
    Candidate,
    Evidence,
    RequirementAnswer,
    V1Result,
    build_spec,
    compare,
)
from vendor_review.web.app import Runtime, create_app


def test_merge_never_erases_and_dedupes():
    b = merge_brief(BuyerBrief(), {"must_haves": ["GPS tracking", "e-way bill"]})
    b = merge_brief(b, {"must_haves": ["gps tracking", "POD capture"], "use_case": ""})
    assert b.must_haves == ["GPS tracking", "e-way bill", "POD capture"]
    b = merge_brief(b, {"remove": {"must_haves": ["E-way bill"]}})
    assert b.must_haves == ["GPS tracking", "POD capture"]
    b = merge_brief(b, {"budget": {"max_inr": 300000, "period": "monthly"}})
    assert b.budget.label() == "up to ₹300,000 monthly"


@pytest.mark.parametrize(
    "text,expected",
    [
        ("2-4 lakh per month", (200000, 400000, "monthly")),
        ("30 lakh one-time", (None, 3000000, "one_time")),
        ("1.5 crore annually", (None, 15000000, "annual")),
    ],
)
def test_parse_budget(text, expected):
    out = parse_budget(text)
    assert (out.get("min_inr"), out["max_inr"], out["period"]) == expected


def test_parse_budget_no_fixed():
    assert parse_budget("no fixed budget")["no_fixed_budget"] is True


class FakeStructured:
    def __init__(self, decisions):
        self.decisions = list(decisions)

    def invoke(self, messages):
        d = self.decisions.pop(0)
        if isinstance(d, Exception):
            raise d
        return {
            "raw": AIMessage(
                content="",
                usage_metadata={"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
            ),
            "parsed": d,
            "parsing_error": None,
        }


class FakeModel:
    def __init__(self, decisions):
        self.s = FakeStructured(decisions)

    def with_structured_output(self, schema, include_raw=True):
        return self.s


def make_client(tmp_path, model=None, v1=None, discovery=None):
    settings = Settings(data_dir=tmp_path, gemini_api_key=SecretStr(""))
    rt = Runtime(settings, model=model, v1=v1, discovery=discovery)
    if model is None:
        rt.model = None
    return TestClient(create_app(rt)), rt


def fill_by_rules(c, sid):
    for text in [
        "TMS for our FTL network, we need to cut freight cost and track trucks",
        "Reduce freight cost and give clients live tracking",
        "GPS tracking, e-way bill integration, carrier rate comparison",
        "2-4 lakh per month",
        "Maharashtra, Gujarat",
    ]:
        s = c.post(f"/api/sessions/{sid}/messages", json={"text": text}).json()
    return s


def test_rule_based_intake_reaches_ready_without_model(tmp_path):
    c, _ = make_client(tmp_path)
    with c:
        s = c.post("/api/sessions").json()
        assert s["messages"][0]["role"] == "assistant" and s["stage"] == "collecting"
        r = c.post(f"/api/sessions/{s['id']}/search", json={"confirm": True})
        assert r.status_code == 409  # incomplete brief cannot start a search
        s = fill_by_rules(c, s["id"])
        assert s["mode"] == "fallback"
        assert s["missing_required"] == []
        assert s["stage"] == "ready"
        assert s["brief"]["geography"] == ["Maharashtra", "Gujarat"]
        assert s["brief"]["budget"]["max_inr"] == 400000


def test_model_intake_patch_and_failure_falls_back(tmp_path):
    first = IntakeDecision(
        reply="Got it. What are your must-haves?",
        patch={
            "service_category": "Cold-chain carrier",
            "use_case": "Pharma distribution",
            "geography": ["Pan-India"],
        },
    )
    model = FakeModel([first, TimeoutError("provider")])
    c, rt = make_client(tmp_path, model=model)
    with c:
        sid = c.post("/api/sessions").json()["id"]
        s = c.post(
            f"/api/sessions/{sid}/messages",
            json={"text": "Need a pharma cold chain carrier across India"},
        ).json()
        assert s["mode"] == "model"
        assert s["brief"]["service_category"] == "Cold-chain carrier"
        assert s["messages"][-1]["text"].startswith("Got it")
        # Second turn: provider fails, rules take over and still record the answer.
        s = c.post(
            f"/api/sessions/{sid}/messages", json={"text": "2-8C temperature logging"}
        ).json()
        assert s["mode"] == "fallback"
        assert "2-8C temperature logging" in s["brief"]["must_haves"]
        assert rt.ledger.summary("intake:" + sid)["model_calls"] == 2


def test_brief_edit_validation_and_lock(tmp_path):
    c, _ = make_client(tmp_path, v1=DemoV1(delay=0), discovery=DemoDiscovery())
    with c:
        sid = c.post("/api/sessions").json()["id"]
        bad = c.put(f"/api/sessions/{sid}/brief", json={"brief": {"top_k": 99}})
        assert bad.status_code == 422
        brief = BuyerBrief(
            service_category="WMS",
            use_case="Multi-client warehouses",
            must_haves=["Multi-tenant billing"],
            geography=["Pune"],
            budget={"no_fixed_budget": True},
            top_k=3,
        )
        s = c.put(f"/api/sessions/{sid}/brief", json={"brief": brief.model_dump()}).json()
        assert s["stage"] == "ready"
        first = c.post(f"/api/sessions/{sid}/search", json={"confirm": True}).json()
        again = c.post(f"/api/sessions/{sid}/search", json={"confirm": True}).json()
        assert first["run_id"] == again["run_id"]  # double approval does not start twice
        assert c.post(f"/api/sessions/{sid}/messages", json={"text": "x"}).status_code == 409
        for _ in range(100):
            r = c.get(f"/api/sessions/{sid}/search").json()
            if r["status"] == "done":
                break
            time.sleep(0.05)
        assert r["status"] == "done"
        # Duplicate discovery record collapsed; top_k respected.
        assert len(r["candidates"]) == 3
        assert len({x["key"] for x in r["candidates"]}) == 3
        assert r["comparison"]["ranking"]


def test_restart_resumes_without_repeating_completed(tmp_path, monkeypatch):
    monkeypatch.setenv("V1_PARALLEL", "1")  # deterministic crash point; parallel tested separately
    calls = []

    class CountingV1(DemoV1):
        def evaluate(self, request):
            calls.append(request.candidate.key)
            return super().evaluate(request)

    c, rt = make_client(tmp_path, v1=CountingV1(delay=0), discovery=DemoDiscovery())
    with c:
        sid = c.post("/api/sessions").json()["id"]
        brief = BuyerBrief(
            service_category="TMS",
            use_case="x",
            must_haves=["GPS"],
            geography=["Delhi"],
            budget={"max_inr": 100000},
            top_k=3,
        )
        c.put(f"/api/sessions/{sid}/brief", json={"brief": brief.model_dump()})
    # Simulate a kill after discovery and one completed evaluation.
    rid, _ = rt.store.start_run(sid, brief)
    from vendor_review.searches import execute_run

    class Boom(CountingV1):
        n = 0

        def evaluate(self, request):
            Boom.n += 1
            if Boom.n == 2:
                raise SystemExit  # process killed mid-evaluation
            return super().evaluate(request)

    with pytest.raises(SystemExit):
        execute_run(rt.store, rid, DemoDiscovery(), Boom(delay=0), 10, 10, event=lambda _: None)
    done_before = [k for k, v in rt.store.evaluations(rid).items() if v["status"] == "completed"]
    assert len(done_before) == 1
    calls.clear()
    execute_run(rt.store, rid, DemoDiscovery(), CountingV1(delay=0), 10, 10, event=lambda _: None)
    assert done_before[0] not in calls and len(calls) == 2
    assert rt.store.run(rid)["status"] == "done"


def test_compare_requires_evidence_and_blocks_contradiction():
    brief = BuyerBrief(
        service_category="TMS",
        use_case="x",
        must_haves=["GPS", "E-way bill"],
        geography=["Delhi"],
        budget={"no_fixed_budget": True},
    )
    spec = build_spec("r", brief)
    a, b = Candidate(name="A", domain="a.example"), Candidate(name="B", domain="b.example")
    ev = [Evidence(url="https://a.example/x", passage_or_field="GPS tracking included")]
    qid = {q.text: q.id for q in spec.questions}
    res = {
        a.key: V1Result(
            candidate_key=a.key,
            status="completed",
            answers=[
                RequirementAnswer(question_id=q.id, verdict="supported", summary="", evidence=ev)
                for q in spec.questions
            ],
        ),
        b.key: V1Result(
            candidate_key=b.key,
            status="completed",
            answers=[
                RequirementAnswer(question_id=qid["GPS"], verdict="supported", summary=""),  # no ev
                RequirementAnswer(
                    question_id=qid["E-way bill"], verdict="contradicted", summary=""
                ),
            ],
        ),
    }
    out = compare(spec, [a, b], res)
    assert out.recommended_key == a.key
    rb = next(r for r in out.ranking if r.candidate_key == b.key)
    assert rb.score == 0 and rb.disqualified_by == ["E-way bill"] and rb.must_have_supported == 0


def test_no_recommendation_when_v1_not_connected(tmp_path):
    c, _ = make_client(tmp_path)
    with c:
        sid = c.post("/api/sessions").json()["id"]
        brief = BuyerBrief(
            service_category="TMS",
            use_case="x",
            must_haves=["GPS"],
            geography=["Delhi"],
            budget={"max_inr": 1},
            include_vendors=["X Co"],
        )
        c.put(f"/api/sessions/{sid}/brief", json={"brief": brief.model_dump()})
        c.post(f"/api/sessions/{sid}/search", json={"confirm": True})
        for _ in range(100):
            r = c.get(f"/api/sessions/{sid}/search").json()
            if r["status"] == "done":
                break
            time.sleep(0.05)
        assert r["comparison"]["recommended_key"] is None
        assert r["evaluations"][r["candidates"][0]["key"]]["status"] == "not_connected"
        assert missing_required(brief) == []


def test_existing_shortlist_is_evaluated_once_v1_is_connected(tmp_path):
    """A shortlist found while V1 was disconnected is evaluated later without new discovery."""
    from vendor_review.pipeline import NotConnectedV1
    from vendor_review.searches import execute_run

    found = []

    class CountingDiscovery(DemoDiscovery):
        def find(self, spec):
            found.append(spec.run_id)
            return super().find(spec)

    c, rt = make_client(tmp_path, v1=DemoV1(delay=0), discovery=CountingDiscovery())
    with c:
        sid = c.post("/api/sessions").json()["id"]
        brief = BuyerBrief(
            service_category="TMS",
            use_case="x",
            must_haves=["GPS"],
            geography=["Delhi"],
            budget={"max_inr": 100000},
            top_k=3,
        )
        c.put(f"/api/sessions/{sid}/brief", json={"brief": brief.model_dump()})
        rid, _ = rt.store.start_run(sid, brief)
        execute_run(
            rt.store, rid, CountingDiscovery(), NotConnectedV1(), 10, 10, event=lambda _: None
        )
        assert {v["status"] for v in rt.store.evaluations(rid).values()} == {"not_connected"}
        assert (
            c.post(f"/api/sessions/{sid}/search/evaluate", json={"confirm": False}).status_code
            == 400
        )
        r = c.post(f"/api/sessions/{sid}/search/evaluate", json={"confirm": True})
        assert r.status_code == 200
        for _ in range(50):
            if rt.store.run(rid)["status"] == "done":
                break
            time.sleep(0.05)
        statuses = {v["status"] for v in rt.store.evaluations(rid).values()}
        assert statuses <= {"completed", "partial"} and len(found) == 1
        assert rt.store.run(rid)["comparison"]
