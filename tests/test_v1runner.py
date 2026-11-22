"""V1 adapter: brief construction, verdict mapping, a full scripted V1 run and parallelism.

All model and HTTP traffic here is synthetic; none of it is live validation.
"""

import json
import threading
import time

import httpx
from conftest import MATCH, fixture_client
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from test_graph import ScriptedModel, answer

from vendor_review.brief import BuyerBrief
from vendor_review.graph import turn_progress
from vendor_review.intake import readiness, validate_brief
from vendor_review.pipeline import Candidate, RunCost, V1Request, V1Result, build_spec
from vendor_review.v1runner import V1Agent, buyer_message, to_result

QUOTE = "Example WMS supports multi-client billing with a separate invoice per client."


def request(credit_limit=2.0):
    brief = BuyerBrief(
        service_category="warehouse management system",
        use_case="run multi-client warehouses",
        must_haves=["multi-client billing"],
        integrations=["Tally"],
        geography=["Maharashtra"],
        budget={"min_inr": 150000, "max_inr": 300000, "period": "monthly"},
        timeline="4 months",
    )
    spec = build_spec("run_v1", brief)
    return V1Request(
        run_id="run_v1",
        candidate=Candidate(name="Example", domain="example.com", crustdata_company_id=123),
        brief=brief,
        questions=spec.questions,
        credit_limit=credit_limit,
        seconds_limit=60,
    )


def test_constructed_brief_passes_v1_grounding_and_readiness():
    req = request()
    text, args = buyer_message(req)
    brief = validate_brief(args, [HumanMessage(content=text)])
    assert readiness(brief)["ready"]
    assert [r["id"] for r in brief["requirements"]] == [
        f"R{i}" for i in range(1, len(req.questions) + 1)
    ]
    priorities = {r["text"]: r["priority"] for r in brief["requirements"]}
    assert priorities["multi-client billing"] == "must"
    assert priorities["Integrates with Tally"] == "must"
    assert any(p == "question" for p in priorities.values())  # budget
    assert brief["constraints"]["security"] == "unknown"  # explicit, not invented


def test_findings_map_to_conservative_verdicts_with_exact_evidence():
    req = request()
    state = {
        "findings": [
            {
                "requirement_id": "R1",
                "status": "vendor_documented",
                "claim": "Multi-client billing documented",
                "citations": [
                    {"artifact_id": "a1", "url": "https://example.com/docs", "quote": QUOTE}
                ],
                "limitations": "Vendor claim only",
            },
            {
                "requirement_id": "R2",
                "status": "cannot_verify",
                "claim": "Tally integration not found",
                "citations": [],
                "limitations": "No integration page found",
            },
        ]
    }
    pages = {("a1", "https://example.com/docs"): {"retrieved_at_unix": 1763769600}}
    result = to_result(req, state, pages, cost=RunCost(), notes="n")
    by_q = {a.question_id: a for a in result.answers}
    first, second = req.questions[0].id, req.questions[1].id
    assert by_q[first].verdict == "supported" and by_q[first].evidence[0].passage_or_field == QUOTE
    assert by_q[first].summary.startswith("Vendor's own documentation states this")
    assert by_q[second].verdict == "cannot_verify" and "integration" in by_q[second].missing
    assert result.status == "partial"  # geography/budget never researched
    assert len(result.answers) == len(req.questions)


class V1Script(ScriptedModel):
    """identify -> fetch -> record_findings -> answer, reading artifact IDs from tool results."""

    def __init__(self):
        super().__init__([])

    def invoke(self, messages):
        self.inputs.append(messages)
        step = len(self.inputs)
        latest = next((json.loads(m.content) for m in reversed(messages) if m.type == "tool"), {})
        if step == 1:
            call = ("identify_company", {"identifier": "example.com", "kind": "domain"})
        elif step == 2:
            call = ("fetch_page", {"url": "https://example.com/docs"})
        elif step == 3:
            call = (
                "record_findings",
                {
                    "findings": [
                        {
                            "requirement_id": "R1",
                            "claim": "Multi-client billing is documented",
                            "status": "vendor_documented",
                            "citations": [
                                {
                                    "artifact_id": latest["artifact_id"],
                                    "url": "https://example.com/docs",
                                    "quote": QUOTE,
                                }
                            ],
                            "limitations": "Vendor documentation; not runtime-tested",
                            "verification_steps": ["Pilot per-client invoicing."],
                        }
                    ]
                },
            )
        else:
            return answer("Example documents multi-client billing; other items unverified.")
        return answer(
            "", [{"name": call[0], "args": call[1], "id": f"s{step}", "type": "tool_call"}]
        )


def test_full_scripted_v1_run_for_one_candidate(setup, tmp_path, monkeypatch):
    monkeypatch.setenv("V1_PREFETCH", "0")  # these scripted runs drive identify/fetch
    settings, _ = setup
    settings = settings.model_copy(update={"data_dir": tmp_path / "runtime"})

    def handler(req):
        if req.url.path == "/company/identify":
            return httpx.Response(200, json=MATCH, headers={"X-Credits-Used": "0.2"})
        page = [{"success": True, "url": "https://example.com/docs", "title": "Docs",
                 "content": f"<html><body><main><p>{QUOTE}</p></main></body></html>"}]  # fmt: skip
        return httpx.Response(200, json=page, headers={"X-Credits-Used": "1"})

    agent = V1Agent(
        settings,
        model_factory=lambda s: V1Script(),
        client_factory=lambda s, ledger: fixture_client(s, ledger, handler),
        event=lambda _: None,
    )
    result = agent.evaluate(request(credit_limit=2.0))
    first = result.answers[0]
    assert first.verdict == "supported" and first.evidence[0].passage_or_field == QUOTE
    assert first.evidence[0].retrieved_at  # original capture time carried through
    assert result.cost.crustdata_credits == 1.2
    assert result.status == "partial" and "Dossier:" in result.notes
    assert (tmp_path / "reports").exists()


def test_vendor_credit_cap_never_exceeds_session_cap(setup):
    settings, _ = setup
    agent = V1Agent(settings, event=lambda _: None)
    _, cap = agent.vendor_settings(1000)
    assert cap == settings.session_credits
    _, small = agent.vendor_settings(0.5)
    assert str(small) == "0.5"


def test_candidates_are_evaluated_in_parallel(tmp_path, monkeypatch):
    from vendor_review.searches import SearchStore, execute_run

    monkeypatch.setenv("V1_PARALLEL", "4")
    active, peak, lock = [0], [0], threading.Lock()

    class Discovery:
        def find(self, spec):
            return [Candidate(name=f"V{i}", domain=f"v{i}.example") for i in range(4)]

    class SlowV1:
        def evaluate(self, req):
            with lock:
                active[0] += 1
                peak[0] = max(peak[0], active[0])
            time.sleep(0.2)
            with lock:
                active[0] -= 1
            return V1Result(candidate_key=req.candidate.key, status="completed")

    store = SearchStore(tmp_path / "search.sqlite")
    sid = store.create_session()
    rid, _ = store.start_run(sid, BuyerBrief(service_category="wms", must_haves=["x"]))
    execute_run(store, rid, Discovery(), SlowV1(), 4, 10, event=lambda _: None)
    assert peak[0] >= 2 and store.run(rid)["status"] == "done"
    assert all(v["status"] == "completed" for v in store.evaluations(rid).values())


def test_turn_progress_lists_completed_steps_after_latest_buyer_message():
    history = [
        HumanMessage(content="old"),
        AIMessage(content="", tool_calls=[{"name": "web_search", "args": {"query": "old"}, "id": "o"}]),
        ToolMessage(content=json.dumps({"status": "ok"}), tool_call_id="o"),
        HumanMessage(content="new"),
        AIMessage(content="", tool_calls=[{"name": "read_evidence", "args": {"artifact_id": "a", "focus": "x"}, "id": "r"}]),
        ToolMessage(content=json.dumps({"status": "ok", "artifact_id": "a"}), tool_call_id="r"),
        AIMessage(content="", tool_calls=[{"name": "search_person_posts", "args": {"person_id": 7}, "id": "p"}]),
        ToolMessage(content=json.dumps({"status": "denied", "message": "budget"}), tool_call_id="p"),
    ]  # fmt: skip
    steps = turn_progress(history)
    assert [s["tool"] for s in steps] == ["read_evidence", "search_person_posts"]
    assert steps[0]["args"] == {"artifact_id": "a", "focus": "x"} and steps[1]["reason"] == "budget"


def test_paced_model_retries_once_only_on_provider_rate_limit():
    from vendor_review.v1runner import PacedModel, Pacer

    class Flaky:
        def __init__(self, errors):
            self.errors, self.calls = list(errors), 0

        def bind_tools(self, schemas):
            return self

        def invoke(self, messages):
            self.calls += 1
            if self.errors:
                raise self.errors.pop(0)
            return "ok"

    slept = []
    limit = RuntimeError("429 RESOURCE_EXHAUSTED ... Please retry in 3.5s.")
    model = Flaky([limit])
    paced = PacedModel(model, Pacer(6000), sleep=slept.append).bind_tools([])
    assert paced.invoke([]) == "ok" and model.calls == 2 and slept == [4.5]
    twice = Flaky([limit, limit])
    try:
        PacedModel(twice, Pacer(6000), sleep=slept.append).invoke([])
        raise AssertionError("second rate limit must surface")
    except RuntimeError:
        assert twice.calls == 2
    other = Flaky([ValueError("bad schema")])
    try:
        PacedModel(other, Pacer(6000), sleep=slept.append).invoke([])
        raise AssertionError("non-rate-limit errors are never retried")
    except ValueError:
        assert other.calls == 1
    long_wait = Flaky([RuntimeError("RESOURCE_EXHAUSTED retry in 90s")])
    try:
        PacedModel(long_wait, Pacer(6000), sleep=slept.append).invoke([])
        raise AssertionError("waits beyond the bound are not attempted")
    except RuntimeError:
        assert long_wait.calls == 1


def test_pacer_spaces_calls_across_threads():
    from vendor_review.v1runner import Pacer

    pacer = Pacer(1200)  # 50 ms spacing
    starts = []

    def call():
        pacer.wait()
        starts.append(time.monotonic())

    threads = [threading.Thread(target=call) for _ in range(4)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    starts.sort()
    assert all(b - a >= 0.045 for a, b in zip(starts, starts[1:]))


def test_resumed_review_reloads_account_access_instead_of_cached_preflight(
    setup, tmp_path, monkeypatch
):
    monkeypatch.setenv("V1_PREFETCH", "0")  # these scripted runs drive identify/fetch
    """Regression: a reused preflight key returned a cached result and left access unset."""
    import sqlite3

    settings, _ = setup
    settings = settings.model_copy(update={"data_dir": tmp_path / "runtime"})

    def handler(req):
        if req.url.path == "/account/endpoints":
            return httpx.Response(200, json=fresh["access"])
        if req.url.path == "/account/credits":
            return httpx.Response(200, json={"account": {"credits": 50}})
        if req.url.path == "/company/identify":
            return httpx.Response(200, json=MATCH, headers={"X-Credits-Used": "0.2"})
        page = [{"success": True, "url": "https://example.com/docs", "title": "Docs",
                 "content": f"<html><body><main><p>{QUOTE}</p></main></body></html>"}]  # fmt: skip
        return httpx.Response(200, json=page, headers={"X-Credits-Used": "1"})

    fresh = {}

    def client_factory(s, ledger):
        client = fixture_client(s, ledger, handler)
        fresh["access"] = client.access
        client.access, client.balance = None, None  # force a real preflight, as in production
        return client

    agent = V1Agent(
        settings,
        model_factory=lambda s: V1Script(),
        client_factory=client_factory,
        event=lambda _: None,
    )
    agent.evaluate(request(credit_limit=3.0))
    second = agent.evaluate(request(credit_limit=3.0))  # resumes the same V1 thread
    db = sqlite3.connect(tmp_path / "runtime" / "v1" / "ledger.sqlite")
    denied = db.execute(
        "SELECT count(*) FROM operations WHERE status='denied' AND result LIKE '%preflight%'"
    ).fetchone()[0]
    loads = db.execute(
        "SELECT count(*) FROM operations WHERE name='account_access' AND status='ok'"
    ).fetchone()[0]
    assert denied == 0 and loads == 2
    assert second.answers[0].verdict == "supported"


def test_worn_thread_continues_in_new_attempt_with_remaining_allowance(
    setup, tmp_path, monkeypatch
):
    monkeypatch.setenv("V1_PREFETCH", "0")  # these scripted runs drive identify/fetch
    import sqlite3

    from langgraph.checkpoint.sqlite import SqliteSaver

    from vendor_review.store import Ledger

    monkeypatch.setenv("V1_MODEL_TOKENS", "60030")  # first run leaves < 60k tokens: worn
    settings, _ = setup
    settings = settings.model_copy(update={"data_dir": tmp_path / "runtime"})

    def handler(req):
        if req.url.path == "/company/identify":
            return httpx.Response(200, json=MATCH, headers={"X-Credits-Used": "0.2"})
        page = [{"success": True, "url": "https://example.com/docs", "title": "Docs",
                 "content": f"<html><body><main><p>{QUOTE}</p></main></body></html>"}]  # fmt: skip
        return httpx.Response(200, json=page, headers={"X-Credits-Used": "1"})

    agent = V1Agent(
        settings,
        model_factory=lambda s: V1Script(),
        client_factory=lambda s, ledger: fixture_client(s, ledger, handler),
        event=lambda _: None,
    )
    req = request(credit_limit=2.0)
    agent.evaluate(req)
    base = f"v1-run_v1-{req.candidate.key}"
    ledger = Ledger(tmp_path / "runtime" / "v1" / "ledger.sqlite", settings)
    saver = SqliteSaver(sqlite3.connect(tmp_path / "runtime" / "v1" / "checkpoints.sqlite"))
    thread, seed, spent = agent.attempt(ledger, saver, base)
    assert thread == base + "-a2" and str(spent) == "1.2"
    assert seed["findings"][0]["requirement_id"] == "R1"  # saved work carries forward
    assert any(m.type == "tool" for m in seed["messages"])  # captures carry forward
    monkeypatch.setenv("V1_MAX_ATTEMPTS", "1")
    capped = V1Agent(settings, event=lambda _: None)
    assert capped.attempt(ledger, saver, base)[0] == base  # no new attempts beyond the limit
    ledger.close()


def test_menu_headings_are_not_offered_as_quotes():
    from vendor_review.research import heading_like

    assert heading_like("Account Management Client Masters versus Global Masters")
    assert heading_like("Data Upload Processing")
    assert not heading_like(
        "BrilliantWMS supports 3PL environments where multiple customers are managed."
    )


def test_closing_turn_records_explicit_unknowns_when_model_stops_early(setup, tmp_path):
    settings, _ = setup
    settings = settings.model_copy(update={"data_dir": tmp_path / "runtime"})
    req = request(credit_limit=1.0)
    n = len(req.questions)

    class StopsEarly(ScriptedModel):
        def __init__(self):
            super().__init__([])

        def invoke(self, messages):
            self.inputs.append(messages)
            last_human = next(m for m in reversed(messages) if m.type == "human").content
            if "Close this vendor review" not in last_human:
                return answer("I could not fetch more pages.")  # first turn: gives up
            if len(self.inputs) == 2:
                findings = [
                    {
                        "requirement_id": f"R{i}",
                        "claim": "No captured evidence",
                        "status": "cannot_verify",
                        "limitations": "Nothing captured for this requirement",
                        "verification_steps": ["Ask the vendor for documentation."],
                    }
                    for i in range(1, n + 1)
                ]
                return answer("", [{"name": "record_findings", "args": {"findings": findings},
                                    "id": "close", "type": "tool_call"}])  # fmt: skip
            return answer("Closed with explicit unknowns.")

    agent = V1Agent(
        settings,
        model_factory=lambda s: StopsEarly(),
        client_factory=lambda s, ledger: fixture_client(s, ledger, lambda r: httpx.Response(500)),
        event=lambda _: None,
    )
    result = agent.evaluate(req)
    assert all(a.verdict == "cannot_verify" for a in result.answers)
    assert result.status == "completed"  # every requirement explicitly answered
    assert all(a.summary.startswith("No admissible evidence found") for a in result.answers)
