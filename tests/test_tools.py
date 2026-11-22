import json
import time
from decimal import Decimal

import httpx
import pytest
from conftest import MATCH, execute, fixture_client
from pydantic import ValidationError

from vendor_review.config import Settings
from vendor_review.evidence import compact, ground_final
from vendor_review.schemas import Enrich, Fetch, Search
from vendor_review.store import Ledger, LimitError


def test_exact_rest_request_charge_and_provenance(setup):
    settings, ledger = setup

    def handler(request):
        assert request.url == "https://api.crustdata.com/company/identify"
        assert request.method == "POST"
        assert request.headers["x-api-version"] == "2025-11-01"
        assert request.headers["authorization"] == "Bearer test-secret-not-real"
        assert json.loads(request.content) == {"domains": ["example.com"], "exact_match": True}
        return httpx.Response(
            200, json=MATCH, headers={"X-Credits-Used": "0.2", "X-Request-Id": "r1"}
        )

    with_client = fixture_client(settings, ledger, handler)
    result = execute(with_client)
    assert result["status"] == "ok"
    assert result["artifact_id"]
    assert "company_data" in result["data"]["provenance"]
    assert ledger.summary("a")["observed_credits"] == 0.2
    assert json.loads(ledger.recent("a")[0]["details"])["provider_request_id"] == "r1"
    # Completed replay uses captured result; no second request/charge.
    assert execute(with_client) == result
    assert ledger.summary("a")["tool_calls"] == 1
    with_client.close()


def test_multi_call_cumulative_cap_across_turns_and_lowered_restart(setup):
    settings, ledger = setup
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(
            200, json={"success": True, "results": []}, headers={"X-Credits-Used": "1"}
        )

    client = fixture_client(settings, ledger, handler)
    low = settings.model_copy(update={"session_credits": Decimal("1.5")})
    ledger.settings = low
    ledger.session("a")
    assert execute(client, "web_search", {"query": "x"}, "one", "one")["status"] == "ok"
    assert execute(client, "web_search", {"query": "x"}, "two", "two")["status"] == "denied"
    assert len(calls) == 1
    # Returning to a larger env limit cannot undo a previously lowered durable limit.
    ledger.settings = settings
    ledger.session("a")
    assert execute(client, "web_search", {"query": "x"}, "three", "three")["status"] == "denied"
    assert ledger.summary("a")["remaining_credits"] == 0.5
    client.close()


def test_unknown_charge_and_pending_dispatch_are_not_free_or_replayed(setup):
    settings, ledger = setup
    calls = []

    def handler(request):
        calls.append(1)
        raise httpx.ReadTimeout("contains test-secret-not-real")

    client = fixture_client(settings, ledger, handler)
    result = execute(client)
    assert result["status"] == "unknown"
    assert "test-secret" not in json.dumps(result)
    assert ledger.summary("a")["held_credits_including_unknown"] == 0.2
    assert execute(client) == result
    op = ledger.reserve("a", "t", "pending", "tool", "identify_company", credits=0.2)
    assert execute(client, key="pending")["operation_id"] == op
    assert len(calls) == 1
    client.close()


@pytest.mark.parametrize("status", [400, 401, 403, 429, 500])
def test_errors_are_recorded_and_never_retried(setup, status):
    settings, ledger = setup
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(
            status, json={"error": "fixture failure"}, headers={"X-Credits-Used": "0.1"}
        )

    client = fixture_client(settings, ledger, handler)
    assert execute(client)["status"] == "provider_error"
    assert len(calls) == 1
    assert ledger.summary("a")["observed_credits"] == 0.1
    client.close()


def test_missing_charge_header_retains_reservation_and_schema_failure_charged(setup):
    settings, ledger = setup
    client = fixture_client(settings, ledger, lambda _: httpx.Response(200, json={"made_up": True}))
    result = execute(client)
    assert result["status"] == "provider_error"
    assert result["actual_credits"] is None
    assert ledger.summary("a")["held_credits_including_unknown"] == 0.2
    client.close()


def test_denied_access_missing_price_and_invalid_schema_never_dispatch(setup):
    settings, ledger = setup

    def handler(_):
        pytest.fail("Unauthorized dispatch")

    client = fixture_client(settings, ledger, handler)
    client.access["endpoints"][0]["status"] = "disabled"
    assert execute(client)["status"] == "denied"
    client.access["endpoints"][0]["status"] = "enabled"
    del client.access["endpoints"][0]["base_credits"]
    assert execute(client, key="price")["status"] == "denied"
    assert (
        execute(client, args={"identifier": "x", "endpoint": "https://evil"}, key="bad")["status"]
        == "denied"
    )
    assert execute(client, name="send_email", key="no")["status"] == "denied"
    client.close()


def test_enrich_selected_id_and_one_page_search(setup):
    settings, ledger = setup
    requests = []

    def handler(request):
        requests.append(json.loads(request.content))
        return httpx.Response(
            200,
            json=MATCH
            if request.url.path == "/company/enrich"
            else {"success": True, "results": []},
            headers={"X-Credits-Used": "0"},
        )

    client = fixture_client(settings, ledger, handler)
    execute(client, "enrich_company", {"company_id": 123, "fields": ["basic_info", "headcount"]})
    execute(client, "web_search", {"query": "x"}, key="search")
    assert requests == [
        {"crustdata_company_ids": [123], "fields": ["basic_info", "headcount"]},
        {"query": "x", "sources": ["web"], "page": 1},
    ]
    client.close()


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "http://127.0.0.1",
        "http://10.0.0.1/x",
        "https://user:secret@example.com",
        "http://foo.local",
        "https://example.com/?api_key=x",
    ],
)
def test_fetch_rejects_nonpublic_or_secret_urls(url):
    with pytest.raises(ValidationError):
        Fetch(url=url)


def test_no_generated_pagination_or_premium_fields():
    with pytest.raises(ValidationError):
        Search(query="x", page=15)
    with pytest.raises(ValidationError):
        Enrich(company_id=123, fields=["technographics"])


def test_fetch_qualifies_truncation_challenge_and_freshness():
    raw = [
        {
            "success": True,
            "url": "https://other.example",
            "timestamp": 123,
            "title": "Login",
            "content": "<html>verify you are human " + "x" * 9000,
        }
    ]
    result = compact("fetch_page", raw, "https://example.com")[0]
    assert len(result["excerpt"]) == 8000
    assert {
        "excerpt_truncated",
        "possible_login_or_challenge",
        "returned_host_differs",
        "possibly_incomplete_html",
    } <= set(result["quality"])
    assert result["provider_timestamp_seconds"] == 123


def test_restart_preserves_pending_reservations_and_thread_isolation(setup):
    settings, ledger = setup
    ledger.reserve("a", "t", "k", "tool", "identify_company", credits=0.2)
    other = Ledger(settings.data_dir / "ledger.sqlite", settings)
    other.session("a")
    other.session("b")
    assert other.summary("a")["held_credits_including_unknown"] == 0.2
    assert other.summary("b")["held_credits_including_unknown"] == 0
    other.close()


def test_token_and_call_limits_do_not_reset_per_turn(setup):
    settings, ledger = setup
    ledger.settings = settings.model_copy(update={"session_model_tokens": 10, "turn_tool_calls": 1})
    ledger.session("a")
    ledger.reserve("a", "t", "m", "model", "fixture", tokens=10)
    with pytest.raises(LimitError):
        ledger.reserve("a", "next", "m2", "model", "fixture", tokens=1)
    ledger.reserve("a", "t", "tool", "tool", "fixture")
    with pytest.raises(LimitError):
        ledger.reserve("a", "t", "tool2", "tool", "fixture")


def test_redaction_applies_to_artifact_ledger_and_configuration_repr(setup):
    settings, ledger = setup
    op = ledger.reserve("a", "t", "k", "tool", "fixture")
    artifact = ledger.artifact(op, {"text": "test-secret-not-real Bearer hidden-token"})
    ledger.finish(op, "ok", {"text": "test-secret-not-real"}, actual=0)
    text = ledger.db.execute("SELECT payload FROM artifacts WHERE id=?", (artifact,)).fetchone()[0]
    assert "test-secret-not-real" not in text
    assert "hidden-token" not in text
    assert "test-secret-not-real" not in repr(settings)


def test_deadline_stops_before_dispatch(setup):
    settings, ledger = setup
    client = fixture_client(settings, ledger, lambda _: pytest.fail("Dispatched past deadline"))
    result = client.execute(
        "identify_company", {"identifier": "x"}, "a", "t", "k", time.monotonic() - 1
    )
    assert result["status"] == "denied"
    client.close()


def test_local_model_requires_explicit_selection():
    with pytest.raises(ValidationError):
        Settings(model_provider="ollama")
    assert Settings(model_provider="ollama", model_name="chosen-model").model_name == "chosen-model"


def test_paid_only_gemini_models_and_rates_are_rejected():
    with pytest.raises(ValidationError):
        Settings(model_provider="gemini", model_name="gemini-4-carbon")
    with pytest.raises(ValidationError):
        Settings(model_provider="gemini", model_input_usd_per_million=Decimal("1"))
    assert Settings(model_provider="gemini").model_name == "gemini-3.1-flash-lite"


def test_final_source_check_replaces_invented_link_and_attaches_real_receipt():
    from langchain_core.messages import ToolMessage

    capture = {
        "status": "ok",
        "artifact_id": "artifact-1",
        "api_path": "/company/identify",
        "data": {"records": MATCH},
    }
    message = ToolMessage(content=json.dumps(capture), tool_call_id="call-1")
    text = ground_final("Example is verified: https://invented.example/about", [message])
    assert "https://invented.example" not in text
    assert "Citation check" in text and "artifact-1" in text
    assert '"crustdata_company_id": 123' in text


def test_credit_limit_is_independent_per_turn_and_cumulative(setup):
    settings, ledger = setup
    ledger.settings = settings.model_copy(update={"turn_credits": Decimal("0.2")})
    ledger.reserve("a", "turn1", "first", "tool", "fixture", credits=0.2)
    with pytest.raises(LimitError, match="Per-turn"):
        ledger.reserve("a", "turn1", "second", "tool", "fixture", credits=0.2)
    ledger.reserve("a", "turn2", "third", "tool", "fixture", credits=0.2)
    assert ledger.summary("a")["held_credits_including_unknown"] == 0.4


@pytest.mark.parametrize(
    "name,body,expected",
    [
        ("fetch_page", [{"success": False, "url": None, "content": None}], "partial"),
        ("web_search", {"success": False, "results": [], "metadata": {}}, "partial"),
        ("identify_company", [{"matched_on": "example.com", "matches": []}], "no_match"),
    ],
)
def test_unusable_or_no_match_is_not_reported_as_evidence_success(setup, name, body, expected):
    settings, ledger = setup
    client = fixture_client(
        settings,
        ledger,
        lambda _: httpx.Response(200, json=body, headers={"X-Credits-Used": "0.2"}),
    )
    args = (
        {"url": "https://example.com"}
        if name == "fetch_page"
        else {"query": "x"}
        if name == "web_search"
        else {"identifier": "example.com"}
    )
    result = execute(client, name, args)
    assert result["status"] == expected
    assert result["artifact_id"] and ledger.summary("a")["observed_credits"] == 0.2
    client.close()


def test_zero_account_rate_is_denied_without_dispatch(setup):
    settings, ledger = setup
    client = fixture_client(settings, ledger, lambda _: pytest.fail("Dispatch with zero rate"))
    client.access["endpoints"][0]["effective_rate_limit_rpm"] = 0
    assert execute(client)["status"] == "denied"
    client.close()
