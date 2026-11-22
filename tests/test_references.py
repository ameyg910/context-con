import json
import sqlite3

import httpx
import pytest
from conftest import fixture_client
from langchain_core.messages import ToolMessage
from pydantic import ValidationError
from test_research import brief

from vendor_review.people import (
    PeopleSearch,
    PersonEnrich,
    PostSearch,
    people_body,
    project_professional_data,
)
from vendor_review.references import (
    role_timeline,
    validate_coverage,
    validate_reference,
)
from vendor_review.research import execute_local, validate_findings
from vendor_review.schemas import all_tools


def capture(path, artifact, data, op=None):
    return ToolMessage(
        tool_call_id=artifact,
        content=json.dumps(
            {
                "status": "ok",
                "api_path": path,
                "artifact_id": artifact,
                "operation_id": op or artifact,
                "data": data,
            }
        ),
    )


def company(domain="customer.example", name="Customer", cid=456):
    return capture(
        "/company/identify",
        "company",
        {
            "records": [
                {
                    "matches": [
                        {
                            "company_data": {
                                "crustdata_company_id": cid,
                                "basic_info": {"name": name, "primary_domain": domain},
                            }
                        }
                    ]
                }
            ]
        },
    )


CUSTOMER_QUOTE = "Customer reports deployment of Example tracking during its 2022 pilot."
POST_QUOTE = "I implemented the Example tracking integration during our 2022 pilot."


def page(artifact="page", url="https://customer.example/story", text=CUSTOMER_QUOTE, flags=None):
    return capture(
        "/web/enrich/live",
        artifact,
        [{"url": url, "excerpt": text, "quality": flags or [], "content_sha256": text}],
    )


def profile():
    return {
        "crustdata_person_id": 99,
        "basic_profile": {"name": "Jane Doe", "current_title": "Engineer"},
        "updated_at": "2026-11-01",
        "social_handles": {
            "professional_network_identifier": {
                "profile_url": "https://www.linkedin.com/in/jane-doe"
            }
        },
        "experience": {
            "employment_details": {
                "current": [],
                "past": [
                    {
                        "crustdata_company_id": 456,
                        "title": "Engineer",
                        "start_date": "2021-01-01",
                        "end_date": "2023-01-01",
                    }
                ],
            }
        },
    }


def post(kind="original", pid=99):
    return capture(
        "/social_post/search",
        "post",
        {
            "records": {
                "posts": [
                    {
                        "share_url": "https://www.linkedin.com/posts/example",
                        "text": POST_QUOTE,
                        "post_type": kind,
                        "date_posted": "2022-06-01T10:00:00Z",
                        "actor": {"actor_type": "person", "crustdata_entity_id": pid},
                    }
                ]
            }
        },
    )


def customer_reference():
    return {
        "id": "REF1",
        "kind": "customer",
        "name": "Customer",
        "domain": "customer.example",
        "requirement_ids": ["R1"],
        "relationship": "integrator",
        "product_scope": "Tracking pilot",
        "period_scope": "Historical 2022",
        "limitations": "No current contract or performance verification.",
        "citations": [
            {
                "artifact_id": "page",
                "url": "https://customer.example/story",
                "quote": CUSTOMER_QUOTE,
            }
        ],
    }


def state():
    return {
        "brief": brief(),
        "identity": {"resolved": True},
        "messages": [company(), page()],
        "references": [],
    }


def test_people_bodies_are_projected_scoped_and_do_not_request_contacts():
    body = people_body(
        PeopleSearch(company_id=456, employment="past", role_keywords=["Engineer"], limit=2)
    )
    assert body["filters"]["conditions"][0] == {
        "field": "experience.employment_details.past.company_id",
        "type": "=",
        "value": 456,
    }
    assert body["limit"] == 2 and "preview" not in body and "cursor" not in body
    assert "contact" not in json.dumps(body)
    assert people_body(PostSearch(person_id=99))["filters"]["conditions"][1]["value"] == "person"
    assert people_body(PersonEnrich(profile_url="https://www.linkedin.com/in/jane-doe"))[
        "professional_network_profile_urls"
    ] == ["https://www.linkedin.com/in/jane-doe"]
    with pytest.raises(ValidationError):
        PeopleSearch(company_id=456, limit=100)
    with pytest.raises(ValidationError):
        PersonEnrich(profile_url="https://other.example/in/person")
    assert not any("contact" in name or "send" in name for name in all_tools())


def test_nested_contact_fields_are_discarded_before_capture():
    raw = {
        "profiles": [
            {
                "crustdata_person_id": 99,
                "contact": {"email": "private@example.com"},
                "basic_profile": {"name": "Jane", "email": "private@example.com"},
                "phone_numbers": ["123"],
            }
        ]
    }
    projected = project_professional_data(raw)
    assert "private@example.com" not in json.dumps(projected) and "phone_numbers" not in json.dumps(
        projected
    )


def test_search_reserves_filter_and_return_premiums_once_each(setup):
    settings, ledger = setup
    client = fixture_client(
        settings,
        ledger,
        lambda _: httpx.Response(200, json={"profiles": []}, headers={"X-Credits-Used": "0"}),
    )
    client.access["endpoints"].append(
        {
            "path": "/person/search",
            "status": "enabled",
            "base_credits": 0.03,
            "premium_filters": [{"field": "experience", "credits": 0.1}],
            "premium_fields": [{"field": "experience", "credits": 0.1}],
        }
    )
    price, _ = client.price(
        "/person/search",
        PeopleSearch(company_id=456, role_keywords=["Engineer", "Product"], limit=3),
    )
    assert str(price) == "0.69"
    client.close()


def test_customer_identity_and_source_scope_are_preserved():
    s = state()
    ref = validate_reference(customer_reference(), s)
    assert ref["customer_owned_account"] and ref["company_id"] == 456
    assert not ref["direct_contract_verified"] and not ref["independently_verified"]
    args = {
        "findings": [
            {
                "requirement_id": "R1",
                "claim": "Customer reports historical tracking use",
                "status": "customer_reported",
                "citations": [
                    {
                        "artifact_id": "page",
                        "url": "https://customer.example/story",
                        "quote": CUSTOMER_QUOTE,
                        "source_kind": "customer_account",
                        "reference_id": "REF1",
                    }
                ],
                "limitations": "Only stated historical scope",
                "verification_steps": ["Compare the actual buyer lanes and time period."],
            }
        ]
    }
    result = validate_findings(args, s["brief"], s["messages"], [ref])
    assert (
        result[0]["status"] == "customer_reported" and result[0]["independently_verified"] is False
    )
    args["findings"][0]["citations"][0]["reference_id"] = "invented"
    with pytest.raises(ValueError):
        validate_findings(args, s["brief"], s["messages"], [ref])


@pytest.mark.parametrize(
    "failure", ["identity", "wrong_page", "unrelated", "challenge", "vendor_only"]
)
def test_customer_leads_cannot_be_laundered_as_customer_corroboration(failure):
    s = state()
    r = customer_reference()
    if failure == "identity":
        s["messages"] = [page()]
    if failure == "wrong_page":
        r["citations"][0]["artifact_id"] = "fake"
    if failure == "unrelated":
        s["messages"] = [
            company(),
            page(text="Customer is recruiting drivers for transport operations."),
        ]
        r["citations"][0]["quote"] = "Customer is recruiting drivers for transport operations."
    if failure == "challenge":
        s["messages"] = [company(), page(flags=["possible_login_or_challenge"])]
    if failure == "vendor_only":
        s["messages"] = [company(), page(url="https://example.com/customers")]
        r["citations"][0]["url"] = "https://example.com/customers"
        ref = validate_reference(r, s)
        assert not ref["customer_owned_account"]
        args = {
            "findings": [
                {
                    "requirement_id": "R1",
                    "claim": "Customer deployed Example",
                    "status": "customer_reported",
                    "citations": [
                        {
                            **r["citations"][0],
                            "source_kind": "customer_account",
                            "reference_id": "REF1",
                        }
                    ],
                    "limitations": "Uncertain",
                    "verification_steps": ["Review customer-owned evidence."],
                }
            ]
        }
        with pytest.raises(ValueError):
            validate_findings(args, s["brief"], s["messages"], [ref])
        return
    with pytest.raises(ValueError):
        validate_reference(r, s)


@pytest.mark.parametrize(
    "when,expected",
    [
        ("2022-06-01", "consistent_with_indexed_role"),
        ("2024-01-01", "outside_recorded_role"),
        ("2020-01-01", "outside_recorded_role"),
        ("", "date_unknown"),
    ],
)
def test_role_event_matching_does_not_assume_current_title_at_event(when, expected):
    assert role_timeline(profile(), 456, "Engineer", when)["status"] == expected


def professional_reference():
    return {
        "id": "REF2",
        "kind": "professional",
        "name": "Jane Doe",
        "requirement_ids": ["R1"],
        "relationship": "customer_employee",
        "product_scope": "Tracking integration",
        "period_scope": "Historical 2022",
        "citations": [
            {
                "artifact_id": "post",
                "url": "https://www.linkedin.com/posts/example",
                "quote": POST_QUOTE,
            }
        ],
        "limitations": "Attributed original post, not an independent performance test.",
        "person_id": 99,
        "profile_artifact_id": "profile",
        "role_company_id": 456,
        "role_title": "Engineer",
        "event_date": "2022-06-01",
    }


def test_professional_attribution_and_role_dates_are_captured_not_inferred():
    s = state()
    s["messages"] += [
        capture(
            "/person/enrich", "profile", {"records": [{"matches": [{"person_data": profile()}]}]}
        ),
        post(),
    ]
    ref = validate_reference(professional_reference(), s)
    assert ref["authorship"] == "indexed_original_post"
    assert ref["timeline"]["status"] == "consistent_with_indexed_role"
    assert ref["authored_sources"] == [
        {"artifact_id": "post", "url": "https://www.linkedin.com/posts/example"}
    ]
    r = professional_reference()
    r["event_date"] = "2026-11-22"
    with pytest.raises(ValueError):
        validate_reference(r, s)


@pytest.mark.parametrize("kind,pid", [("repost_without_thoughts", 99), ("original", 100)])
def test_reposts_or_other_authors_do_not_establish_professional_authorship(kind, pid):
    s = state()
    s["messages"] += [
        capture(
            "/person/enrich", "profile", {"records": [{"matches": [{"person_data": profile()}]}]}
        ),
        post(kind, pid),
    ]
    assert validate_reference(professional_reference(), s)["authorship"] == "unconfirmed"


def test_coverage_cannot_invent_work_or_sufficiency():
    s = state()
    coverage = {
        "branch": "customer",
        "status": "blocked",
        "requirement_ids": ["R1"],
        "operation_ids": ["page"],
        "rationale": "Captured source requires more review",
        "gaps": ["Current scope unknown"],
    }
    assert validate_coverage(coverage, s)["status"] == "blocked"
    coverage["operation_ids"] = ["invented"]
    with pytest.raises(ValueError):
        validate_coverage(coverage, s)
    coverage.update(operation_ids=["page"], status="sufficient")
    with pytest.raises(ValueError):
        validate_coverage(coverage, s)


def test_brief_changes_clear_reference_and_branch_assertions():
    s = state()
    s.update(brief={}, references=[{"id": "old"}], coverage={"customer": {"status": "sufficient"}})
    from langchain_core.messages import HumanMessage
    from test_research import BUYER

    s["messages"] = [HumanMessage(BUYER)]
    _, updates = execute_local("update_intake", brief(), s)
    assert updates["references"] == [] and updates["coverage"] == {}


def test_read_saved_page_can_expand_beyond_first_excerpt_without_refetch(setup):
    settings, ledger = setup
    from vendor_review.references import Citation, captured_pages, checked_passage, read_evidence

    text = (
        "Old context. " * 900
        + "The customer confirms Example deployment during a historical trial."
    )
    raw = [
        {
            "success": True,
            "url": "https://customer.example/story",
            "content": "<html><body>" + text + "</body></html>",
        }
    ]
    op = ledger.reserve("a", "saved", "saved", "tool", "fetch_page", credits=1)
    artifact = ledger.artifact(op, raw)
    source = page(artifact=artifact, text=text[:8000])
    s = {"messages": [source]}
    result = read_evidence({"artifact_id": artifact, "focus": "The customer confirms"}, s, ledger)
    s["messages"].append(ToolMessage(tool_call_id="reuse", content=json.dumps(result)))
    citation = Citation(
        artifact_id=artifact,
        url="https://customer.example/story",
        quote="The customer confirms Example deployment during a historical trial.",
    )
    assert checked_passage(citation, captured_pages(s["messages"]))
    assert "not a fresh retrieval" in result["message"]
    with pytest.raises(ValueError):
        read_evidence({"artifact_id": "other-thread"}, s, ledger)


def test_customer_resolution_does_not_replace_vendor_identity(setup):
    from conftest import MATCH
    from langgraph.checkpoint.sqlite import SqliteSaver
    from test_graph import ScriptedModel, answer
    from test_research import BUYER

    from vendor_review.graph import build_graph, turn_input

    settings, ledger = setup

    def handler(request):
        if json.loads(request.content)["domains"] == ["example.com"]:
            raw = MATCH
        else:
            raw = [
                {
                    "matched_on": "customer.example",
                    "matches": [
                        {
                            "company_data": {
                                "crustdata_company_id": 456,
                                "basic_info": {
                                    "name": "Customer",
                                    "primary_domain": "customer.example",
                                },
                            }
                        }
                    ],
                }
            ]
        return httpx.Response(200, json=raw, headers={"X-Credits-Used": "0.2"})

    client = fixture_client(settings, ledger, handler)

    def call(name, args, key):
        return {"name": name, "args": args, "id": key, "type": "tool_call"}

    model = ScriptedModel(
        [
            answer("", [call("update_intake", brief(), "b")]),
            answer("", [call("identify_company", {"identifier": "example.com"}, "v")]),
            answer("", [call("identify_company", {"identifier": "customer.example"}, "c")]),
            answer("References are scoped separately."),
        ]
    )
    with sqlite3.connect(":memory:", check_same_thread=False) as connection:
        graph = build_graph(
            model, client, ledger, settings, SqliteSaver(connection), lambda _: None, review=True
        )
        result = graph.invoke(turn_input(BUYER, settings), {"configurable": {"thread_id": "a"}})
        assert result["identity"]["company_id"] == 123 and result["identity"]["resolved"]
        assert result["identity"]["domain"] == "example.com"
    client.close()


def test_pending_branches_and_reference_roles_are_human_readable_in_report():
    from vendor_review.report import render_report

    s = state()
    s["references"] = [validate_reference(customer_reference(), s)]
    rendered = render_report(s, "a", {}, [])
    assert (
        "Customer and professional references" in rendered and "Investigation coverage" in rendered
    )
    assert "Historical 2022" in rendered and "No references were contacted" in rendered
    assert "Direct contract: not verified" in rendered and "pending" in rendered


def test_full_customer_and_professional_graph_records_both_branches(setup):
    from conftest import MATCH
    from langgraph.checkpoint.sqlite import SqliteSaver
    from test_graph import ScriptedModel, answer
    from test_research import BUYER

    from vendor_review.graph import build_graph, turn_input

    settings, ledger = setup
    settings = settings.model_copy(update={"turn_tool_calls": 20, "turn_model_calls": 20})
    ledger.settings = settings

    def handler(request):
        body = json.loads(request.content)
        if request.url.path == "/company/identify":
            raw = (
                MATCH
                if body["domains"] == ["example.com"]
                else json.loads(company().content)["data"]["records"]
            )
            cost = ".2"
        elif request.url.path == "/web/enrich/live":
            raw = [
                {
                    "success": True,
                    "url": "https://customer.example/story",
                    "content": "<html><body>" + CUSTOMER_QUOTE + "</body></html>",
                }
            ]
            cost = "1"
        elif request.url.path == "/person/search":
            assert body["filters"]["field"] == "experience.employment_details.past.company_id"
            raw = {"profiles": [profile()]}
            cost = ".23"
        else:
            assert request.url.path == "/social_post/search"
            raw = json.loads(post().content)["data"]["records"]
            cost = ".5"
        return httpx.Response(200, json=raw, headers={"X-Credits-Used": cost})

    client = fixture_client(settings, ledger, handler)
    for path, cost in [("/person/search", 0.23), ("/social_post/search", 0.5)]:
        client.access["endpoints"].append(
            {
                "path": path,
                "status": "enabled",
                "base_credits": cost,
                "effective_rate_limit_rpm": 300,
            }
        )

    class Model(ScriptedModel):
        def invoke(self, messages):
            self.inputs.append(messages)
            step = len(self.inputs)
            latest = next(
                (json.loads(m.content) for m in reversed(messages) if m.type == "tool"), {}
            )
            if step == 1:
                name, args = "update_intake", brief()
            elif step == 2:
                name, args = "identify_company", {"identifier": "example.com"}
            elif step == 3:
                name, args = "identify_company", {"identifier": "customer.example"}
            elif step == 4:
                name, args = "fetch_page", {"url": "https://customer.example/story"}
            elif step == 5:
                self.customer_artifact = latest["artifact_id"]
                self.customer_op = latest["operation_id"]
                name, args = "register_reference", customer_reference()
                args["citations"][0]["artifact_id"] = self.customer_artifact
            elif step == 6:
                name, args = "search_people", {"company_id": 456, "employment": "past", "limit": 1}
            elif step == 7:
                self.profile_artifact = latest["artifact_id"]
                name, args = "search_person_posts", {"person_id": 99, "limit": 1}
            elif step == 8:
                self.post_artifact = latest["artifact_id"]
                self.post_op = latest["operation_id"]
                name, args = "register_reference", professional_reference()
                args["profile_artifact_id"] = self.profile_artifact
                args["citations"][0]["artifact_id"] = self.post_artifact
            elif step == 9:
                name, args = (
                    "record_findings",
                    {
                        "findings": [
                            {
                                "requirement_id": "R1",
                                "claim": "Customer and professional report limited historical implementation.",
                                "status": "partially_supported",
                                "citations": [
                                    {
                                        "artifact_id": self.customer_artifact,
                                        "url": "https://customer.example/story",
                                        "quote": CUSTOMER_QUOTE,
                                        "source_kind": "customer_account",
                                        "reference_id": "REF1",
                                    },
                                    {
                                        "artifact_id": self.post_artifact,
                                        "url": "https://www.linkedin.com/posts/example",
                                        "quote": POST_QUOTE,
                                        "source_kind": "professional_statement",
                                        "reference_id": "REF2",
                                    },
                                ],
                                "limitations": "No current contract or independent outcome validation.",
                                "verification_steps": [
                                    "Test the buyer-specific scope against the attributed historical scope."
                                ],
                            }
                        ]
                    },
                )
            elif step in {10, 11}:
                branch = "customer" if step == 10 else "professional"
                name, args = (
                    "record_coverage",
                    {
                        "branch": branch,
                        "status": "attempted",
                        "requirement_ids": ["R1"],
                        "operation_ids": [self.customer_op if step == 10 else self.post_op],
                        "reference_ids": ["REF1" if step == 10 else "REF2"],
                        "rationale": "Scoped source review performed",
                        "gaps": [
                            "Current product comparability and independently measured outcome unknown."
                        ],
                    },
                )
            else:
                return answer(
                    "Historical attributed references recorded; verification remains limited."
                )
            return answer(
                "", [{"name": name, "args": args, "id": f"branch-{step}", "type": "tool_call"}]
            )

    with sqlite3.connect(":memory:", check_same_thread=False) as connection:
        graph = build_graph(
            Model([]),
            client,
            ledger,
            settings,
            SqliteSaver(connection),
            lambda _: None,
            review=True,
        )
        result = graph.invoke(turn_input(BUYER, settings), {"configurable": {"thread_id": "a"}})
        assert len(result["references"]) == 2
        assert set(result["coverage"]) == {"customer", "professional"}
        assert result["findings"][0]["independently_verified"] is False
        assert result["identity"]["company_id"] == 123
        assert ledger.summary("a")["observed_credits"] == 2.13
    client.close()
