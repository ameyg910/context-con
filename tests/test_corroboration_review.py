"""Deterministic checks for the corroboration review fixes (synthetic fixtures, not live runs)."""

import json
import sqlite3

import pytest
from langchain_core.messages import AIMessage, ToolMessage
from test_references import (
    CUSTOMER_QUOTE,
    POST_QUOTE,
    capture,
    company,
    customer_reference,
    page,
    post,
    professional_reference,
    profile,
    state,
)

from vendor_review.evidence import compact, focus_windows, page_text
from vendor_review.references import (
    Citation,
    captured_pages,
    checked_passage,
    read_evidence,
    validate_coverage,
    validate_reference,
)
from vendor_review.research import execute_local, validate_findings

CONSENT = (
    '<div id="CybotCookiebotDialog" class="cookie-consent">'
    + "We use cookies to personalise content and ads. Necessary Preferences Statistics "
    "Marketing. Cookie vendor list: project44 tracking pixel, analytics, advertising. "
    * 120
    + "</div>"
)
ARTICLE = (
    "<article><h1>Information is key</h1>"
    + "<p>Supply chains need timely data across carriers and modes.</p>" * 30
    + "<p>Example Logistics uses project44 to share real-time shipment visibility with "
    "shippers across its European network.</p>"
    + "<p>Closing remarks about planning.</p>" * 10
    + "</article>"
)


def consent_page_html(body=ARTICLE):
    return f"<html><body><nav>Home About Careers</nav>{CONSENT}{body}<footer>Legal</footer></body></html>"


def test_consent_overlay_is_removed_and_article_text_preferred():
    text, full, notes = page_text(consent_page_html())
    assert "We use cookies" not in text and "We use cookies" in full
    assert "Example Logistics uses project44" in text
    assert "navigation_or_consent_boilerplate_removed" in notes
    assert "main_content_region:article" in notes
    # A page that discusses cookies in its own body is not stripped by text content.
    text, _, _ = page_text(
        "<html><body><p>" + "Cookie policy discussion. " * 50 + "</p></body></html>"
    )
    assert "Cookie policy discussion" in text


def test_fetch_compaction_excerpt_starts_with_article_not_consent_banner():
    pages = compact(
        "fetch_page",
        [{"success": True, "url": "https://customer.example/a", "content": consent_page_html()}],
        "https://customer.example/a",
    )
    assert pages[0]["excerpt"].startswith("Information is key")
    assert "navigation_or_consent_boilerplate_removed" in pages[0]["quality"]


def test_focus_windows_are_exact_slices_and_merge_overlaps():
    text = "alpha project44 beta " * 3 + "x" * 5000 + " project44 end"
    windows = focus_windows(text, "PROJECT44", width=200)
    assert len(windows) == 2
    assert all(text[w["start"] : w["end"]] == w["text"] for w in windows)


def saved(ledger, html, url="https://customer.example/a"):
    raw = [{"success": True, "url": url, "content": html}]
    op = ledger.reserve("a", "saved", "saved-" + str(len(html)), "tool", "fetch_page", credits=1)
    artifact = ledger.artifact(op, raw)
    first = compact("fetch_page", raw, url)
    message = ToolMessage(
        tool_call_id=artifact,
        content=json.dumps(
            {
                "status": "ok",
                "api_path": "/web/enrich/live",
                "artifact_id": artifact,
                "operation_id": op,
                "retrieved_at_unix": 1763769600,
                "data": first,
            }
        ),
    )
    return artifact, {"messages": [message]}


def test_focused_read_recovers_late_article_passage_with_original_retrieval_date(setup):
    _, ledger = setup
    body = ARTICLE.replace("<p>Closing", "<p>" + "Filler paragraph. " * 600 + "</p><p>Closing")
    late = "<p>Late mention: Example Logistics expanded its project44 integration in 2023.</p>"
    artifact, s = saved(ledger, consent_page_html(body.replace("</article>", late + "</article>")))
    result = read_evidence({"artifact_id": artifact, "focus": "project44"}, s, ledger)
    data = result["data"][0]
    assert data["focus_result"]["status"] == "found_in_readable_text"
    assert len(data["passages"]) >= 2 and data["retrieved_at_unix"] == 1763769600
    s["messages"].append(ToolMessage(tool_call_id="reuse", content=json.dumps(result)))
    quote = "Example Logistics expanded its project44 integration in 2023."
    citation = Citation(artifact_id=artifact, url="https://customer.example/a", quote=quote)
    assert checked_passage(citation, captured_pages(s["messages"]))


def test_focus_found_only_in_consent_markup_is_not_admissible(setup):
    _, ledger = setup
    body = (
        "<article>" + "<p>Supply chains need timely data across carriers.</p>" * 30 + "</article>"
    )
    artifact, s = saved(ledger, consent_page_html(body))
    result = read_evidence({"artifact_id": artifact, "focus": "project44"}, s, ledger)
    data = result["data"][0]
    assert data["focus_result"]["status"] == "only_in_removed_boilerplate"
    assert data["passages"] == [] and data["excerpt"] == ""
    assert "focus_only_in_removed_boilerplate_review_required" in data["quality"]
    s["messages"].append(ToolMessage(tool_call_id="reuse", content=json.dumps(result)))
    citation = Citation(
        artifact_id=artifact,
        url="https://customer.example/a",
        quote="Cookie vendor list: project44 tracking pixel, analytics, advertising.",
    )
    with pytest.raises(ValueError):
        checked_passage(citation, captured_pages(s["messages"]))


def test_not_found_page_cannot_become_reference_evidence(setup):
    _, ledger = setup
    html = (
        "<html><head><title>Page not found</title></head><body>Example case study 404</body></html>"
    )
    raw = [
        {
            "success": True,
            "url": "https://example.com/case-study",
            "title": "Page not found",
            "content": html,
        }
    ]
    pages = compact("fetch_page", raw, "https://example.com/case-study")
    assert "possible_not_found" in pages[0]["quality"]


def test_vendor_mention_and_customer_ownership_must_be_the_same_passage():
    s = state()
    unrelated = "Customer is recruiting drivers for transport operations this year."
    s["messages"] = [
        company(),
        page(artifact="own", text=unrelated),
        page(artifact="vendor", url="https://example.com/customers", text=CUSTOMER_QUOTE),
    ]
    r = customer_reference()
    r["relationship"] = "direct_customer"
    r["citations"] = [
        {"artifact_id": "own", "url": "https://customer.example/story", "quote": unrelated},
        {"artifact_id": "vendor", "url": "https://example.com/customers", "quote": CUSTOMER_QUOTE},
    ]
    ref = validate_reference(r, s)
    assert ref["customer_owned_account"] is False and ref["customer_owned_sources"] == []
    owners = {o["artifact_id"]: o for o in ref["source_ownership"]}
    assert owners["own"]["owner"] == "customer_domain" and not owners["own"]["names_vendor"]
    assert owners["vendor"]["owner"] == "vendor_domain" and owners["vendor"]["names_vendor"]


def test_indirect_customer_relationship_cannot_make_branch_sufficient():
    s = state()
    ref = validate_reference(customer_reference(), s)  # integrator
    assert ref["relationship_directness"] == "indirect" and ref["customer_owned_account"]
    s["references"] = [ref]
    coverage = {
        "branch": "customer",
        "status": "sufficient",
        "requirement_ids": ["R1"],
        "operation_ids": ["page"],
        "reference_ids": ["REF1"],
        "rationale": "Customer-owned integrator page reviewed",
    }
    with pytest.raises(ValueError):
        validate_coverage(coverage, s)
    direct = customer_reference()
    direct["relationship"] = "direct_customer"
    s["references"] = [validate_reference(direct, s)]
    assert validate_coverage(coverage, s)["status"] == "sufficient"


def test_relationship_must_fit_reference_kind():
    s = state()
    r = customer_reference()
    r["relationship"] = "vendor_employee"
    with pytest.raises(ValueError):
        validate_reference(r, s)


def professional_state():
    s = state()
    s["messages"] += [
        capture(
            "/person/enrich", "profile", {"records": [{"matches": [{"person_data": profile()}]}]}
        ),
        post(),
        page(
            artifact="article",
            url="https://news.example/story",
            text="Jane Doe was quoted about the Example tracking integration in an article.",
        ),
    ]
    return s


def test_professional_authorship_is_recorded_per_source():
    s = professional_state()
    r = professional_reference()
    r["citations"].append(
        {
            "artifact_id": "article",
            "url": "https://news.example/story",
            "quote": "Jane Doe was quoted about the Example tracking integration",
        }
    )
    ref = validate_reference(r, s)
    assert ref["authorship"] == "indexed_original_post"
    assert ref["authored_sources"] == [
        {"artifact_id": "post", "url": "https://www.linkedin.com/posts/example"}
    ]
    assert ref["unauthored_sources"][0]["artifact_id"] == "article"
    assert ref["event_date_basis"] == "indexed_publication_date"
    finding = {
        "findings": [
            {
                "requirement_id": "R1",
                "claim": "Professional describes an integration",
                "status": "professional_attributed",
                "citations": [
                    {
                        "artifact_id": "article",
                        "url": "https://news.example/story",
                        "quote": "Jane Doe was quoted about the Example tracking integration",
                        "source_kind": "professional_statement",
                        "reference_id": "REF2",
                    }
                ],
                "limitations": "Attributed only",
                "verification_steps": ["Review the original authored artifact."],
            }
        ]
    }
    with pytest.raises(ValueError):
        validate_findings(finding, s["brief"], s["messages"], [ref])


def test_byline_in_any_saved_passage_is_needs_review_not_verified():
    s = professional_state()
    s["messages"].append(
        page(
            artifact="blog",
            url="https://blog.example/post",
            text="Written by Jane Doe. " + POST_QUOTE,
        )
    )
    r = professional_reference()
    r.update(event_date="", author_quote="Written by Jane Doe.")
    r["citations"] = [
        {"artifact_id": "blog", "url": "https://blog.example/post", "quote": POST_QUOTE}
    ]
    ref = validate_reference(r, s)
    assert ref["authorship"] == "captured_byline_needs_review"
    assert ref["timeline"]["status"] == "date_unknown"
    assert ref["independently_verified"] is False


def test_customer_finding_does_not_overwrite_vendor_finding():
    s = state()
    s["messages"].append(
        page(
            artifact="vendor",
            url="https://example.com/docs",
            text="Example documents a tracking API for every mode.",
        )
    )
    ref = validate_reference(customer_reference(), s)
    s["references"] = [ref]
    from test_research import brief as make_brief

    s["brief"] = make_brief()

    def finding(status, citation):
        return {
            "findings": [
                {
                    "requirement_id": "R1",
                    "claim": status,
                    "status": status,
                    "citations": [citation],
                    "limitations": "Scoped",
                    "verification_steps": ["Pilot."],
                }
            ]
        }

    vendor = finding(
        "vendor_documented",
        {
            "artifact_id": "vendor",
            "url": "https://example.com/docs",
            "quote": "Example documents a tracking API for every mode.",
        },
    )
    customer = finding(
        "customer_reported",
        {
            "artifact_id": "page",
            "url": "https://customer.example/story",
            "quote": CUSTOMER_QUOTE,
            "source_kind": "customer_account",
            "reference_id": "REF1",
        },
    )
    _, change = execute_local("record_findings", vendor, s)
    s.update(change)
    result, change = execute_local("record_findings", customer, s)
    assert {f["status"] for f in change["findings"]} == {"vendor_documented", "customer_reported"}
    assert result["saved_requirements"] == ["R1"]
    from vendor_review.report import render_report

    html = render_report({**s, **change}, "a", {}, [])
    assert "Separate customer finding" in html


def test_token_overrun_records_budget_stop_and_branch_gaps(setup):
    from langgraph.checkpoint.sqlite import SqliteSaver
    from test_graph import ScriptedModel
    from test_research import BUYER

    from vendor_review.graph import build_graph, turn_input

    settings, ledger = setup
    huge = AIMessage(
        content="partial",
        usage_metadata={"input_tokens": 10**8, "output_tokens": 1, "total_tokens": 10**8 + 1},
    )
    with sqlite3.connect(":memory:", check_same_thread=False) as connection:
        graph = build_graph(
            ScriptedModel([huge]),
            None,
            ledger,
            settings,
            SqliteSaver(connection),
            lambda _: None,
            review=True,
        )
        result = graph.invoke(turn_input(BUYER, settings), {"configurable": {"thread_id": "a"}})
    assert result["outcome"] == "budget_stop"
    for branch in ("customer", "professional"):
        assert result["coverage"][branch]["status"] == "blocked"
        assert "reservation" in result["coverage"][branch]["stop_reason"]
        assert result["coverage"][branch]["gaps"]


def test_legacy_not_found_capture_without_flag_is_still_rejected():
    s = state()
    s["messages"] = [
        company(),
        capture(
            "/web/enrich/live",
            "legacy",
            [
                {
                    "url": "https://example.com/case-studies/customer",
                    "title": "Page not found | Example",
                    "excerpt": CUSTOMER_QUOTE,
                    "quality": ["relevance_and_claim_support_require_review"],
                }
            ],
        ),
    ]
    citation = Citation(
        artifact_id="legacy", url="https://example.com/case-studies/customer", quote=CUSTOMER_QUOTE
    )
    with pytest.raises(ValueError):
        checked_passage(citation, captured_pages(s["messages"]))
