"""Discovery via Crustdata ranked company search (synthetic HTTP fixtures, not live results)."""

import json
from datetime import date

import httpx
import pytest
from conftest import fixture_client
from pydantic import ValidationError

from vendor_review.brief import BuyerBrief
from vendor_review.discovery import (
    FIELDS,
    CompanySearch,
    CrustdataDiscovery,
    company_search_body,
    fit_score,
    range_floor,
    semantic_query,
)
from vendor_review.pipeline import build_spec
from vendor_review.schemas import all_tools, tool_schemas

SEARCH_ENTRY = {
    "path": "/company/search",
    "status": "enabled",
    "base_credits": 0.03,
    "effective_rate_limit_rpm": 30,
    "fields": {"enabled": ["basic_info", "locations"], "disabled": ["social_profiles.crunchbase"]},
    "premium_fields": [
        {"field": "taxonomy", "credits": 0.1},
        {"field": "headcount", "credits": 0.2},
    ],
    "premium_filters": [{"field": "taxonomy", "credits": 0.1}],
}
AUTOCOMPLETE_ENTRY = {
    "path": "/company/search/autocomplete",
    "status": "enabled",
    "base_credits": None,
    "effective_rate_limit_rpm": 300,
}
LABELS = ["2-10", "11-50", "51-200", "201-500", "501-1,000", "1,001-5,000", "10,001+"]


def brief():
    return BuyerBrief(
        service_category="warehouse management system",
        use_case="Replace spreadsheets to run multi-client warehouses with barcode scanning",
        must_haves=["multi-client billing", "barcode/RF scanning", "wave picking"],
        integrations=["SAP Business One", "Tally"],
        geography=["Maharashtra"],
        compliance=["GST e-invoicing"],
        deployment="Cloud SaaS hosted in India",
    )


def test_query_is_short_and_product_focused():
    q = semantic_query(brief())
    assert q.startswith("warehouse management system vendor. Use: run multi-client")
    trial = BuyerBrief(
        service_category="WMS",
        use_case="Replace spreadsheets and in-house tool to manage inbound and picking.",
    )
    assert semantic_query(trial) == "WMS vendor. Use: manage inbound and picking"
    assert "multi-client billing" in q and "wave picking" in q
    for noise in ("Tally", "SAP", "Maharashtra", "Cloud SaaS", "spreadsheet", "₹"):
        assert noise not in q
    spec = build_spec("run_x", brief())
    assert spec.semantic_query == q and spec.top_k == 4
    assert "3PL" not in semantic_query(BuyerBrief(service_category="payroll software"))


def test_body_combines_free_quality_filters_with_ranked_search():
    body = company_search_body(
        CompanySearch(query="wms", limit=12, employee_ranges=["51-200"], founded_on_or_before=2023)
    )
    assert body["search"] == {"query": "wms", "mode": "hybrid"} and body["limit"] == 12
    assert body["filters"] == {
        "op": "and",
        "conditions": [
            {"field": "basic_info.employee_count_range", "type": "in", "value": ["51-200"]},
            {"field": "basic_info.year_founded", "type": "=<", "value": 2023},
        ],
    }
    assert "sorts" not in body and "email" not in json.dumps(body)
    assert all(
        f.split(".")[0] in {"crustdata_company_id", "basic_info", "locations"} for f in FIELDS
    )
    single = company_search_body(CompanySearch(query="wms", hq_countries=["IND"]))
    assert single["filters"] == {"field": "locations.country", "type": "in", "value": ["IND"]}
    with pytest.raises(ValidationError):
        CompanySearch(query="wms", limit=50)


def test_discovery_tools_are_not_offered_to_the_v1_model():
    names = {t["function"]["name"] for t in tool_schemas()}
    assert not {"search_companies", "company_autocomplete"} & (names | set(all_tools()))


def test_prices_search_per_result_and_autocomplete_as_documented_free(setup):
    settings, ledger = setup
    client = fixture_client(settings, ledger, lambda _: httpx.Response(500))
    client.access["endpoints"] += [SEARCH_ENTRY, AUTOCOMPLETE_ENTRY]
    filtered = CompanySearch(
        query="wms", limit=12, employee_ranges=["51-200"], founded_on_or_before=2023
    )
    price, _ = client.price("/company/search", filtered)
    assert str(price) == "0.36"
    from vendor_review.discovery import CompanyAutocomplete

    free, _ = client.price(
        "/company/search/autocomplete", CompanyAutocomplete(field="basic_info.employee_count_range")
    )
    assert free == 0
    client.close()


def test_fit_score_prefers_established_matching_vendors():
    b = brief()
    big = {
        "basic_info": {
            "description": "Warehouse management system with multi-client billing, RF barcode "
            "scanning and wave picking for 3PLs in Maharashtra",
            "employee_count_range": "1,001-5,000",
            "year_founded": 2008,
        }
    }
    echo = {
        "basic_info": {
            "description": "warehouse management system multi-client billing",
            "employee_count_range": "51-200",
            "year_founded": date.today().year - 3,
        }
    }
    s_big, parts, weights = fit_score(big, b)
    s_echo, _, _ = fit_score(echo, b)
    assert s_big > s_echo and parts["region"] == 1.0 and sum(weights.values()) == 1
    assert range_floor("1,001-5,000") == 1001 and range_floor("10,001+") == 10001


def handler_factory(seen, companies):
    def handler(request):
        body = json.loads(request.content)
        if request.url.path == "/company/search/autocomplete":
            seen["autocomplete"] = body
            return httpx.Response(200, json={"suggestions": [{"value": v} for v in LABELS]})
        seen["search"] = body
        seen.setdefault("searches", []).append(body)
        countries = (
            [
                c["value"]
                for c in body.get("filters", {}).get("conditions", [])
                if c["field"] == "locations.country"
            ]
            or [[]]
        )[0]
        pool = [c for c in companies if not countries or c["locations"]["country"] in countries]
        returned = pool[: body["limit"]]
        return httpx.Response(
            200,
            json={"companies": returned, "next_cursor": None, "total_count": None},
            headers={"X-Credits-Used": str(round(0.03 * len(returned), 2))},
        )

    return handler


def company(i, desc, size, year):
    return {
        "crustdata_company_id": 100 + i,
        "basic_info": {
            "name": f"Vendor {i}",
            "primary_domain": f"www.vendor{i}.example",
            "description": desc,
            "employee_count_range": size,
            "year_founded": year,
        },
        "locations": {"country": "India", "headquarters": "Pune, Maharashtra, India"},
    }


def test_find_filters_pool_and_reranks_with_transparent_scores(setup, monkeypatch):
    monkeypatch.setenv("DISCOVERY_POOL", "6")
    monkeypatch.setenv("DISCOVERY_LOCAL_SHARE", "0")  # single global search in this test
    settings, ledger = setup
    seen = {}
    companies = [
        company(0, "Generic logistics consulting", "51-200", 2015),
        company(1, "Warehouse management system: multi-client billing, barcode/RF scanning, wave picking", "1,001-5,000", 2006),
        company(2, "Warehouse management system for multi-client billing", "51-200", 2021),
        company(3, "Transport software", "201-500", 2012),
        company(4, "WMS with barcode RF scanning and wave picking", "501-1,000", 2010),
        company(5, "HR payroll", "51-200", 2018),
    ]  # fmt: skip
    client = fixture_client(settings, ledger, handler_factory(seen, companies))
    client.access["endpoints"] += [SEARCH_ENTRY, AUTOCOMPLETE_ENTRY]
    discovery = CrustdataDiscovery(settings, ledger, client, event=lambda _: None)
    spec = build_spec("run_test", brief())
    found = discovery.find(spec)
    assert seen["autocomplete"] == {
        "field": "basic_info.employee_count_range",
        "query": "",
        "limit": 100,
    }
    conditions = seen["search"]["filters"]["conditions"]
    assert conditions[0]["value"] == ["51-200", "201-500", "501-1,000", "1,001-5,000", "10,001+"]
    assert conditions[1] == {
        "field": "basic_info.year_founded",
        "type": "=<",
        "value": date.today().year - 3,
    }
    assert seen["search"]["limit"] == 6 and len(found) == 6
    assert found[0].name == "Vendor 1" and found[0].rank == 2
    assert found[0].relevance >= found[1].relevance >= found[-1].relevance
    assert (
        found[0].discovery_fit["pool_size"] == 6 and "size ≥51" in found[0].discovery_fit["filters"]
    )
    summary = ledger.summary("discovery:run_test")
    assert summary["observed_credits"] == 0.18  # autocomplete free, 6 results x 0.03
    client.close()


def test_execute_run_keeps_best_k_from_reranked_pool(setup, monkeypatch, tmp_path):
    from vendor_review.pipeline import NotConnectedV1
    from vendor_review.searches import SearchStore, execute_run

    monkeypatch.setenv("DISCOVERY_POOL", "6")
    monkeypatch.setenv("DISCOVERY_LOCAL_SHARE", "0")
    settings, ledger = setup
    companies = [
        company(i, "Warehouse management system multi-client billing", "51-200", 2015)
        for i in range(5)
    ]
    companies.append(
        company(
            9,
            "Warehouse management system: multi-client billing, barcode/RF scanning, wave picking",
            "1,001-5,000",
            2006,
        )
    )
    client = fixture_client(settings, ledger, handler_factory({}, companies))
    client.access["endpoints"] += [SEARCH_ENTRY, AUTOCOMPLETE_ENTRY]
    store = SearchStore(tmp_path / "search.sqlite")
    sid = store.create_session()
    rid, _ = store.start_run(sid, brief())
    discovery = CrustdataDiscovery(settings, ledger, client, event=lambda _: None)
    execute_run(store, rid, discovery, NotConnectedV1(), 0, 10, event=lambda _: None)
    chosen = json.loads(store.run(rid)["candidates"])
    assert len(chosen) == 4 and chosen[0]["name"] == "Vendor 9"
    client.close()


def test_no_guessing_when_size_labels_unavailable(setup):
    settings, ledger = setup
    client = fixture_client(settings, ledger, lambda _: httpx.Response(500))
    client.access["endpoints"] += [SEARCH_ENTRY, AUTOCOMPLETE_ENTRY]
    discovery = CrustdataDiscovery(settings, ledger, client, event=lambda _: None)
    with pytest.raises(RuntimeError):
        discovery.find(build_spec("run_denied", brief()))
    client.close()


def test_market_country_query_and_local_first_split(setup, monkeypatch):
    from vendor_review.discovery import market_country

    assert market_country(BuyerBrief(geography=["Pan-India"])) == ("India", "IND")
    assert market_country(BuyerBrief(geography=["Maharashtra", "Karnataka"])) == ("India", "IND")
    assert market_country(BuyerBrief(geography=["India", "USA"])) is None  # ambiguous: no filter
    assert market_country(BuyerBrief(geography=["Mars"])) is None
    b = BuyerBrief(
        service_category="shipping platform", geography=["Pan-India"], must_haves=["NDR"]
    )
    assert semantic_query(b).endswith("Market: businesses in India")

    monkeypatch.setenv("DISCOVERY_POOL", "6")
    settings, ledger = setup
    seen = {}
    companies = [
        company(i, "Shipping platform with NDR management", "51-200", 2015) for i in range(4)
    ]
    abroad = company(7, "Shipping platform with NDR management", "201-500", 2010)
    abroad["locations"] = {"country": "USA", "headquarters": "New York, USA"}
    for c in companies:
        c["locations"]["country"] = "IND"
    client = fixture_client(settings, ledger, handler_factory(seen, companies + [abroad]))
    client.access["endpoints"] += [SEARCH_ENTRY, AUTOCOMPLETE_ENTRY]
    found = CrustdataDiscovery(settings, ledger, client, event=lambda _: None).find(
        build_spec("run_m", b)
    )
    local, global_ = seen["searches"]
    assert local["limit"] == 4 and global_["limit"] == 2
    assert {"field": "locations.country", "type": "in", "value": ["IND"]} in local["filters"][
        "conditions"
    ]
    assert all(c["field"] != "locations.country" for c in global_["filters"]["conditions"])
    assert len({c.crustdata_company_id for c in found}) == len(found)  # deduplicated
    assert "4 of 6 slots HQ in India" in found[0].discovery_fit["filters"]
    assert ledger.summary("discovery:run_m")["observed_credits"] == 0.18  # 4 + 2 results
    client.close()
