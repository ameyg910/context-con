"""Pre-fetch of the vendor's own pages and evidence-based related domains (synthetic HTTP)."""

import json

import httpx
from conftest import fixture_client
from test_graph import ScriptedModel, answer
from test_v1runner import request

from vendor_review.research import validate_findings
from vendor_review.v1runner import V1Agent, pick_links, related_domains


def test_related_domain_needs_a_vendor_link_and_a_name_mention():
    links = [
        "https://www.technoforte.co.in/solutions/wms/",
        "https://www.linkedin.com/company/onpalms",
        "https://partner-example.com/",
    ]
    text = "Palms WMS. OnPalms Yet? is a Technoforte Supply Chain initiative."
    assert related_domains(links, "onpalms.com", text) == ["technoforte.co.in"]
    assert related_domains(links, "onpalms.com", "Palms WMS only") == []


def test_pick_links_prefers_product_pages_and_skips_noise():
    links = [
        "https://vendor.example/blog/3pl-tips",
        "https://vendor.example/careers",
        "https://vendor.example/features/multi-client-billing",
        "https://vendor.example/integrations",
        "https://vendor.example/pricing",
        "https://other.example/features",
        "https://vendor.example/",
    ]
    picked = pick_links(links, ["vendor.example"], 2)
    assert picked == [
        "https://vendor.example/features/multi-client-billing",
        "https://vendor.example/pricing",
    ] or set(picked) <= {
        "https://vendor.example/features/multi-client-billing",
        "https://vendor.example/integrations",
        "https://vendor.example/pricing",
    }
    assert not any("blog" in p or "careers" in p or "other.example" in p for p in picked)


def test_related_official_domain_citation_is_admitted_only_when_listed():
    from langchain_core.messages import HumanMessage
    from test_research import BUYER, brief, page_message

    quote = "PALMS supports multi-client warehouse operations with client-wise billing."
    messages = [HumanMessage(BUYER), page_message(quote, host="technoforte.co.in")]
    finding = {
        "findings": [
            {
                "requirement_id": "R1",
                "claim": "Multi-client documented",
                "status": "vendor_documented",
                "citations": [
                    {"artifact_id": "a1", "url": "https://technoforte.co.in/docs", "quote": quote}
                ],
                "limitations": "Vendor docs",
                "verification_steps": ["Pilot."],
            }
        ]
    }
    try:
        validate_findings(finding, brief(), messages)
        raise AssertionError("unrelated domain must be rejected")
    except ValueError:
        pass
    assert validate_findings(finding, brief(), messages, related_domains=["technoforte.co.in"])


QUOTE = "Example WMS supports multi-client billing with a separate invoice per client."


def test_prefetch_captures_vendor_pages_before_the_model_runs(setup, tmp_path):
    settings, _ = setup
    settings = settings.model_copy(update={"data_dir": tmp_path / "runtime"})
    fetched = []

    def handler(req):
        body = json.loads(req.content)
        if req.url.path == "/company/identify":
            from conftest import MATCH

            return httpx.Response(200, json=MATCH, headers={"X-Credits-Used": "0.2"})
        url = body["urls"][0]
        fetched.append(url)
        links = '<a href="/features/billing">Billing</a><a href="/blog/x">Blog</a>'
        html = f"<html><body><main><p>{QUOTE}</p>{links}</main></body></html>"
        return httpx.Response(
            200,
            json=[{"success": True, "url": url, "title": "Example", "content": html}],
            headers={"X-Credits-Used": "1"},
        )

    seen = {}

    class Reviewer(ScriptedModel):
        def __init__(self):
            super().__init__([])

        def invoke(self, messages):
            self.inputs.append(messages)
            if len(self.inputs) == 1:
                seen["system"] = messages[0].content
                return answer(
                    "",
                    [{"name": "find_passages", "args": {"requirement_id": "R1"}, "id": "f", "type": "tool_call"}],
                )  # fmt: skip
            if len(self.inputs) == 2:
                p = json.loads(messages[-1].content)["passages"][0]
                finding = {
                    "requirement_id": "R1",
                    "claim": "Per-client billing documented",
                    "status": "vendor_documented",
                    "citations": [{"artifact_id": p["artifact_id"], "url": p["url"], "quote": p["quote"]}],
                    "limitations": "Vendor docs",
                    "verification_steps": ["Pilot invoicing."],
                }  # fmt: skip
                return answer(
                    "",
                    [{"name": "record_findings", "args": {"findings": [finding]}, "id": "r", "type": "tool_call"}],
                )  # fmt: skip
            return answer("Done.")

    agent = V1Agent(
        settings,
        model_factory=lambda s: Reviewer(),
        client_factory=lambda s, ledger: fixture_client(s, ledger, handler),
        event=lambda _: None,
    )
    result = agent.evaluate(request(credit_limit=3.0))
    assert (
        fetched[0] == "https://example.com/" and "https://example.com/features/billing" in fetched
    )
    assert not any("blog" in u for u in fetched)
    assert '"resolved": true' in seen["system"]  # identity came from the pre-fetch
    assert result.answers[0].verdict == "supported"
    assert result.cost.crustdata_credits == 2.2  # identify 0.2 + home 1 + one product page 1
