"""V1 reliability: partial saves, exact candidate passages, page slimming (synthetic)."""

import pytest
from langchain_core.messages import HumanMessage
from test_research import BUYER, brief, page_message

from vendor_review.graph import slim_page
from vendor_review.references import Citation, captured_pages, checked_passage
from vendor_review.research import execute_local, find_passages

PAGE = (
    "Welcome to Example. The REST lookup returns a company ID in its response. "
    "Our pricing starts at a monthly plan. Contact sales for enterprise options."
)


def state():
    return {
        "messages": [HumanMessage(BUYER), page_message(PAGE)],
        "brief": brief(),
        "identity": {"resolved": True},
        "findings": [],
        "references": [],
    }


def good():
    return {
        "requirement_id": "R1",
        "claim": "REST lookup returns a company ID",
        "status": "vendor_documented",
        "citations": [
            {
                "artifact_id": "a1",
                "url": "https://example.com/docs",
                "quote": "The REST lookup returns a company ID in its response.",
            }
        ],
        "limitations": "Vendor docs only",
        "verification_steps": ["Call the API in a sandbox."],
    }


def test_valid_findings_are_saved_when_others_are_rejected():
    bad_schema = {**good(), "verification_steps": []}
    bad_quote = {
        **good(),
        "citations": [{**good()["citations"][0], "quote": "A quote that never appeared anywhere."}],
    }
    result, change = execute_local(
        "record_findings", {"findings": [bad_schema, good(), bad_quote]}, state()
    )
    assert result["status"] == "partial" and len(change["findings"]) == 1
    reasons = {r["index"]: r["reason"] for r in result["rejected"]}
    assert set(reasons) == {0, 2}
    assert any("verification_steps" in x for x in reasons[0])
    assert "exact captured passage" in reasons[2]


def test_all_rejected_findings_still_deny_with_reasons():
    with pytest.raises(ValueError, match="No finding saved"):
        execute_local(
            "record_findings", {"findings": [{**good(), "requirement_id": "R9"}]}, state()
        )


def test_find_passages_returns_exact_admissible_sentences():
    s = state()
    out = find_passages({"requirement_id": "R1"}, s)
    assert out["passages"][0]["quote"] == "The REST lookup returns a company ID in its response."
    assert out["passages"][0]["on_vendor_domain"] is True
    pages = captured_pages(s["messages"])
    for p in out["passages"]:
        citation = Citation(artifact_id=p["artifact_id"], url=p["url"], quote=p["quote"])
        assert checked_passage(citation, pages)  # verbatim, so always admissible by origin
    assert find_passages({"query": "pricing monthly plan"}, s)["passages"][0]["quote"].startswith(
        "Our pricing"
    )
    with pytest.raises(ValueError):
        find_passages({"requirement_id": "R7"}, s)


def test_find_passages_skips_blocked_and_not_found_pages():
    s = state()
    s["messages"] = [HumanMessage(BUYER), page_message(PAGE, flags=["possible_login_or_challenge"])]
    assert find_passages({"requirement_id": "R1"}, s)["passages"] == []


def test_model_sees_slim_page_views_but_captures_stay_whole():
    page = {
        "excerpt": "x" * 9000,
        "passages": ["y" * 4000] * 5,
        "links": [str(i) for i in range(40)],
    }
    view = slim_page(page)
    assert len(view["excerpt"]) < 3100 and "find_passages" in view["excerpt"]
    assert len(view["passages"]) == 3 and all(len(p) == 1500 for p in view["passages"])
    assert len(view["links"]) == 15 and len(page["excerpt"]) == 9000


def test_heading_quotes_cannot_support_a_claim():
    s = state()
    s["messages"] = [
        HumanMessage(BUYER),
        page_message("Account Management Client Masters versus Global Masters"),
    ]
    heading = {
        **good(),
        "citations": [
            {
                "artifact_id": "a1",
                "url": "https://example.com/docs",
                "quote": "Account Management Client Masters versus Global Masters",
            }
        ],
    }
    with pytest.raises(ValueError, match="menu heading"):
        execute_local("record_findings", {"findings": [heading]}, s)


def test_saved_heading_only_support_is_downgraded_when_mapped():
    from test_v1runner import request

    from vendor_review.pipeline import RunCost
    from vendor_review.v1runner import to_result

    req = request()
    state_ = {
        "findings": [
            {
                "requirement_id": "R1",
                "status": "vendor_documented",
                "claim": "Multi-client supported",
                "citations": [
                    {
                        "artifact_id": "a1",
                        "url": "https://example.com/docs",
                        "quote": "Account Management Client Masters versus Global Masters",
                    }
                ],
                "limitations": "Docs index only",
            }
        ]
    }
    answer = to_result(req, state_, {}, RunCost(), "n").answers[0]
    assert answer.verdict == "cannot_verify" and answer.summary.startswith("Only a menu heading")


def test_free_local_lookups_do_not_consume_the_tool_call_cap(setup):
    settings, ledger = setup
    settings = settings.model_copy(update={"turn_tool_calls": 2})
    ledger.settings = settings
    for i in range(10):  # well beyond the per-turn tool cap
        op = ledger.reserve("a", "t", f"local-{i}", "local", "find_passages")
        ledger.finish(op, "ok", {"status": "ok"}, actual=0)
    for i in range(2):
        op = ledger.reserve("a", "t", f"tool-{i}", "tool", "record_findings")
        ledger.finish(op, "ok", {"status": "ok"}, actual=0)
    with pytest.raises(Exception, match="tool call limit"):
        ledger.reserve("a", "t", "tool-3", "tool", "record_findings")
    assert ledger.summary("a")["tool_calls"] == 2
