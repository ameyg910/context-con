"""Compact, explicitly qualified evidence envelopes; raw captures stay in the ledger."""

import hashlib
import json
import re
from urllib.parse import urlsplit

from bs4 import BeautifulSoup


def ground_final(content, messages):
    """Reject newly invented citation URLs and always attach actual API receipts.

    This is a citation-origin check, not semantic verification of every generated claim.
    """
    captures = []
    for message in messages:
        if getattr(message, "type", None) != "tool":
            continue
        try:
            result = json.loads(message.content)
        except (ValueError, TypeError):
            continue
        if result.get("status") in {"ok", "partial", "no_match"} and result.get("artifact_id"):
            captures.append(result)
    if not captures:
        return content
    pattern = r"https?://[^\s<>\"')\]]+"

    def urls(text):
        return {url.rstrip("/.,;") for url in re.findall(pattern, text)}

    permitted = urls(json.dumps([item.get("data") for item in captures]))
    text = (
        content
        if isinstance(content, str)
        else "\n".join(part.get("text", "") for part in content if isinstance(part, dict))
    )
    if urls(text) - permitted:
        text = (
            "Citation check: generated links were absent from the retrieved evidence and "
            "could not be verified. Captured provider evidence follows instead:\n"
            + json.dumps(captures[-1]["data"], ensure_ascii=False)[:6000]
            + "\nFurther technical claims remain unverified."
        )
    receipts = list(
        dict.fromkeys(
            f"{item['api_path']} · artifact {item['artifact_id']}" for item in captures[-3:]
        )
    )
    return text + "\n\nAPI evidence (retrieved earlier in this thread):\n" + "\n".join(receipts)


def compact(name, raw, requested=None):
    if name == "account_access":
        return {
            "api_version": raw.get("api_version"),
            "endpoints": [
                {
                    k: entry.get(k)
                    for k in ("path", "status", "base_credits", "effective_rate_limit_rpm")
                }
                for entry in raw["endpoints"]
                if entry.get("path")
                in {"/company/identify", "/company/enrich", "/web/search/live", "/web/enrich/live"}
            ],
        }
    if name == "account_credits":
        return raw
    if name == "web_search":
        return {
            "results": raw["results"][:8],
            "provider_timestamp_ms": raw.get("timestamp"),
            "metadata": raw.get("metadata"),
            "quality": ["discovery_snippets_only", "dates_and_origin_require_verification"]
            + (
                ["opaque_redirect_urls_present"]
                if any(
                    "/goto?" in str(result.get("url", ""))
                    for result in raw["results"]
                    if isinstance(result, dict)
                )
                else []
            ),
            "results_omitted": max(0, len(raw["results"]) - 8),
        }
    if name == "fetch_page":
        pages = []
        for page in raw:
            html = page.get("content") or ""
            soup = BeautifulSoup(html, "html.parser")
            for tag in soup(["script", "style", "nav", "footer", "noscript"]):
                tag.decompose()
            text = soup.get_text(" ", strip=True)
            flags = ["relevance_and_claim_support_require_review", "final_redirect_url_not_exposed"]
            if not page.get("success") or not text:
                flags.append("fetch_failed_or_empty")
            if any(
                marker in text.lower()
                for marker in (
                    "verify you are human",
                    "access denied",
                    "sign in to continue",
                    "just a moment",
                )
            ):
                flags.append("possible_login_or_challenge")
            if len(text) > 8000:
                flags.append("excerpt_truncated")
            if html and "<html" in html.lower() and "</html>" not in html.lower():
                flags.append("possibly_incomplete_html")
            if (
                page.get("url")
                and requested
                and urlsplit(page["url"]).hostname != urlsplit(requested).hostname
            ):
                flags.append("returned_host_differs")
            pages.append(
                {
                    "url": page.get("url"),
                    "requested_url": requested,
                    "title": page.get("title"),
                    "provider_timestamp_seconds": page.get("timestamp"),
                    "excerpt": text[:8000],
                    "quality": flags,
                    "content_sha256": hashlib.sha256(text.encode()).hexdigest(),
                }
            )
        return pages
    # Preserve all candidate identities. Large profiles remain accessible in the artifact.
    serialized = json.dumps(raw, ensure_ascii=False)
    if len(serialized) <= 10000:
        return {
            "records": raw,
            "provenance": "matches[].company_data; indexed provider fields",
            "quality": ["provider_record_not_independent_claim_verification"],
        }
    return {
        "excerpt": serialized[:10000],
        "truncated": True,
        "quality": ["truncated_provider_record_requires_artifact_review"],
    }


def validate_response(name, raw):
    if name == "account_access":
        return (
            isinstance(raw, dict)
            and isinstance(raw.get("endpoints"), list)
            and all(
                isinstance(entry, dict) and isinstance(entry.get("path"), str)
                for entry in raw["endpoints"]
            )
        )
    if name == "account_credits":
        return (
            isinstance(raw, dict)
            and isinstance(raw.get("account"), dict)
            and isinstance(raw["account"].get("credits"), (int, float))
        )
    if name == "web_search":
        return (
            isinstance(raw, dict)
            and isinstance(raw.get("results"), list)
            and isinstance(raw.get("success"), bool)
        )
    if not isinstance(raw, list):
        return False
    if name == "fetch_page":
        return len(raw) == 1 and all(
            isinstance(p, dict) and isinstance(p.get("success"), bool) for p in raw
        )
    return len(raw) == 1 and all(
        isinstance(row, dict)
        and isinstance(row.get("matches"), list)
        and all(
            isinstance(m, dict) and isinstance(m.get("company_data"), dict) for m in row["matches"]
        )
        for row in raw
    )
