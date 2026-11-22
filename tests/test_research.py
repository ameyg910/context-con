import json
import sqlite3

import httpx
import pytest
from conftest import fixture_client
from langchain_core.messages import HumanMessage, ToolMessage
from langgraph.checkpoint.sqlite import SqliteSaver
from test_graph import ScriptedModel, answer

from vendor_review.graph import build_graph, turn_input
from vendor_review.intake import CONSTRAINTS, readiness, validate_brief
from vendor_review.report import render_report, write_report
from vendor_review.research import execute_local, validate_findings

BUYER = "Review Example example.com for API integration. Must: REST lookup. Pass: returns company ID. Constraints unknown."


def brief():
    return {
        "vendor": "Example",
        "domain": "example.com",
        "use_case": "API integration",
        "requirements": [
            {
                "id": "R1",
                "text": "REST lookup",
                "buyer_quote": "REST lookup",
                "priority": "must",
                "acceptance_criterion": "returns company ID",
            }
        ],
        "constraints": {k: "unknown" for k in CONSTRAINTS},
        "buyer_quotes": {
            **{k: "Constraints unknown." for k in CONSTRAINTS},
            "vendor": "Example",
            "domain": "example.com",
            "use_case": "API integration",
        },
    }


def page_message(
    text="The REST lookup returns a company ID in its response.", host="example.com", flags=None
):
    return ToolMessage(
        tool_call_id="fetch",
        content=json.dumps(
            {
                "status": "ok",
                "api_path": "/web/enrich/live",
                "artifact_id": "a1",
                "data": [
                    {
                        "url": f"https://{host}/docs",
                        "title": "API docs",
                        "excerpt": text,
                        "quality": flags or [],
                        "content_sha256": "hash",
                    }
                ],
            }
        ),
    )


def finding():
    return {
        "findings": [
            {
                "requirement_id": "R1",
                "claim": "REST lookup returns company IDs",
                "status": "vendor_documented",
                "citations": [
                    {
                        "artifact_id": "a1",
                        "url": "https://example.com/docs",
                        "quote": "The REST lookup returns a company ID in its response.",
                    }
                ],
                "limitations": "Documentation is not a production test.",
                "verification_steps": [
                    "Run a scoped pilot with a known input and compare the returned ID."
                ],
            }
        ]
    }


def test_intake_requires_quotes_and_explicit_constraints():
    b = validate_brief(brief(), [HumanMessage(BUYER)])
    assert readiness(b)["ready"] and readiness(b)["completeness_score"] == 100
    assert len(readiness(b)["unknown_constraints"]) == 6
    del b["constraints"]["security"]
    assert not readiness(b)["ready"] and "security" in readiness(b)["missing"]
    b["buyer_quotes"]["vendor"] = "Invented buyer"
    with pytest.raises(ValueError):
        validate_brief(b, [HumanMessage(BUYER)])


def test_vague_requirements_need_priority_and_pass_criteria():
    b = brief()
    b["requirements"][0]["acceptance_criterion"] = ""
    assert not readiness(b)["ready"] and readiness(b)["specificity_score"] == 50
    assert readiness(b)["questions"]


def test_changed_brief_invalidates_previous_findings():
    state = {"messages": [HumanMessage(BUYER)], "brief": {}, "findings": [{"old": True}]}
    result, change = execute_local("update_intake", brief(), state)
    assert result["intake"]["ready"] and change["findings"] == [] and change["identity"] == {}


@pytest.mark.parametrize(
    "mutation", ["quote", "artifact", "domain", "challenge", "snippet", "duplicate_conflict"]
)
def test_findings_reject_unfetched_or_unusable_evidence(mutation):
    f = finding()
    messages = [page_message()]
    if mutation == "quote":
        f["findings"][0]["citations"][0]["quote"] = "This quote has been made up entirely."
    if mutation == "artifact":
        f["findings"][0]["citations"][0]["artifact_id"] = "fake"
    if mutation == "domain":
        messages = [page_message(host="wrong.example")]
        f["findings"][0]["citations"][0]["url"] = "https://wrong.example/docs"
    if mutation == "challenge":
        messages = [page_message(flags=["possible_login_or_challenge"])]
    if mutation == "snippet":
        messages = []
    if mutation == "duplicate_conflict":
        f["findings"][0]["status"] = "conflicting_vendor_docs"
        f["findings"][0]["citations"] *= 2
    with pytest.raises(ValueError):
        validate_findings(f, brief(), messages)


def test_dossier_never_calls_vendor_material_independent_verification(setup):
    settings, ledger = setup
    b = brief()
    b["vendor"] = "<script>alert(1)</script>"
    state = {
        "brief": b,
        "findings": validate_findings(finding(), b, [page_message()]),
        "messages": [page_message()],
    }
    rendered = render_report(state, "a", ledger.summary("a"), [])
    assert "<script>" not in rendered and "&lt;script&gt;" in rendered
    assert "Independently verified: <strong>No</strong>" in rendered
    assert "<th>Steps to verify</th>" in rendered and "a1" in rendered
    path = write_report(state, ledger, "a", settings)
    assert path.exists() and path.with_suffix(".json").exists()
    assert (path.parent / "latest.html").exists()


def test_partial_report_retains_unresearched_requirements():
    b = brief()
    b["requirements"].append({**b["requirements"][0], "id": "R2", "text": "Other need"})
    text = render_report({"brief": b, "findings": [], "messages": []}, "a", {}, [])
    assert (
        "R2" in text and "Cannot verify from the available evidence" in text and "partial" in text
    )


def test_review_graph_blocks_paid_calls_before_intake(setup):
    settings, ledger = setup
    client = fixture_client(settings, ledger, lambda _: pytest.fail("Paid dispatch before intake"))
    model = ScriptedModel(
        [
            answer(
                "",
                [
                    {
                        "name": "web_search",
                        "args": {"query": "x"},
                        "id": "early",
                        "type": "tool_call",
                    }
                ],
            ),
            answer("Please provide constraints"),
        ]
    )
    with sqlite3.connect(":memory:", check_same_thread=False) as connection:
        graph = build_graph(
            model, client, ledger, settings, SqliteSaver(connection), lambda _: None, review=True
        )
        state = graph.invoke(
            turn_input("Review Example", settings), {"configurable": {"thread_id": "a"}}
        )
        tool = next(m for m in state["messages"] if m.type == "tool")
        assert "Intake incomplete" in tool.content
    client.close()


def test_literal_constraint_quotes_survive_provider_omitting_dictionary_values():
    b = brief()
    b["constraints"] = {}
    b["buyer_quotes"].update({key: "Constraints unknown." for key in CONSTRAINTS})
    validated = validate_brief(b, [HumanMessage(BUYER)])
    assert readiness(validated)["ready"]


def test_redaction_preserves_authentication_requirement(setup):
    settings, _ = setup
    assert settings.redact("Requires bearer authentication.") == "Requires bearer authentication."
    assert "hidden-token" not in settings.redact("Authorization: Bearer hidden-token")


def test_html_structure_has_all_requirements_and_no_executable_source_markup():
    from bs4 import BeautifulSoup

    b = brief()
    text = render_report({"brief": b, "findings": [], "messages": []}, "a", {}, [])
    soup = BeautifulSoup(text, "html.parser")
    assert len(soup.select("table")[0].select("thead th")) == 7
    assert len(soup.select("table")[0].select("tbody tr")) == 1
    assert not soup.select("script, iframe, img")
    assert soup.find("meta", attrs={"http-equiv": "Content-Security-Policy"})


def test_local_schema_dereferences_nested_pydantic_types():
    from vendor_review.research import local_schemas

    schema = json.dumps(local_schemas())
    assert "$ref" not in schema and "$defs" not in schema
    assert "verification_steps" in schema and "geography" in schema


def test_complete_review_graph_persists_intake_claims_and_fetched_provenance(setup):
    from conftest import MATCH

    settings, ledger = setup

    def handler(request):
        if request.url.path == "/company/identify":
            return httpx.Response(200, json=MATCH, headers={"X-Credits-Used": "0.2"})
        assert request.url.path == "/web/enrich/live"
        return httpx.Response(
            200,
            json=[
                {
                    "success": True,
                    "url": "https://example.com/docs",
                    "title": "API docs",
                    "content": "<html><body>The REST lookup returns a company ID in its response.</body></html>",
                }
            ],
            headers={"X-Credits-Used": "1"},
        )

    client = fixture_client(settings, ledger, handler)

    class ReviewModel(ScriptedModel):
        def invoke(self, messages):
            self.inputs.append(messages)
            step = len(self.inputs)
            name, args = (
                [
                    ("update_intake", brief()),
                    ("identify_company", {"identifier": "example.com"}),
                    ("fetch_page", {"url": "https://example.com/docs"}),
                ][step - 1]
                if step <= 3
                else ("", {})
            )
            if step == 4:
                name, args = "record_findings", finding()
                args["findings"][0]["citations"][0]["artifact_id"] = json.loads(
                    messages[-1].content
                )["artifact_id"]
            if step == 5:
                return answer("Vendor documentation states the interface contract; pilot pending.")
            return answer(
                "", [{"name": name, "args": args, "id": f"review-{step}", "type": "tool_call"}]
            )

    with sqlite3.connect(":memory:", check_same_thread=False) as connection:
        graph = build_graph(
            ReviewModel([]),
            client,
            ledger,
            settings,
            SqliteSaver(connection),
            lambda _: None,
            review=True,
        )
        state = graph.invoke(turn_input(BUYER, settings), {"configurable": {"thread_id": "a"}})
        assert state["identity"]["resolved"]
        assert state["findings"][0]["status"] == "vendor_documented"
        assert state["findings"][0]["independently_verified"] is False
        assert ledger.summary("a")["observed_credits"] == 1.2
        assert write_report(state, ledger, "a", settings).exists()
    client.close()
