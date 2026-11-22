"""Compact, explicitly qualified evidence envelopes; raw captures stay in the ledger."""

import hashlib
import json
import re
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

ALWAYS_REMOVED = ["script", "style", "nav", "footer", "noscript", "template", "svg", "iframe"]
# Consent-manager/overlay markers seen on public pages. Matching is on id/class/aria-label only,
# never on visible body text, so an article that discusses cookies is not removed.
BOILERPLATE = re.compile(
    r"cookie|consent|gdpr|onetrust|cookiebot|usercentrics|didomi|cmplz|"
    r"cookieyes|\bcky-|termly|iubenda|truste|privacy[-_]?(banner|notice|popup|modal)",
    re.I,
)
PROTECTED = {"html", "body", "main", "article"}


def _marker(tag):
    attrs = getattr(tag, "attrs", None) or {}
    classes = attrs.get("class") or []
    return " ".join(
        [attrs.get("id") or "", *(classes if isinstance(classes, list) else [classes])]
        + [attrs.get("aria-label") or ""]
    )


def page_text(html_content):
    """Return (readable text, full text, extraction notes) for a saved HTML page.

    Readable text drops consent/navigation overlays and prefers an <article>/<main> region when
    one carries substantial text. Full text keeps everything except scripts/styles so a focus
    search can report text that exists only inside removed boilerplate. Raw HTML is untouched in
    the ledger; this is a reading aid, not a modification of the captured artifact.
    """
    soup = BeautifulSoup(html_content or "", "html.parser")
    for tag in soup(["script", "style", "noscript", "template"]):
        tag.decompose()
    full = soup.get_text(" ", strip=True)
    notes = []
    removed = 0
    for tag in soup.find_all(True):
        if getattr(tag, "decomposed", False) or tag.attrs is None:
            continue
        if tag.name in PROTECTED or tag.find(list(PROTECTED - {"html", "body"})):
            continue
        if tag.name in ALWAYS_REMOVED or BOILERPLATE.search(_marker(tag)):
            removed += len(tag.get_text(" ", strip=True))
            tag.decompose()
    if removed:
        notes.append("navigation_or_consent_boilerplate_removed")
    regions = [
        tag
        for tag in soup.find_all(["article", "main"]) + soup.find_all(attrs={"role": "main"})
        if len(tag.get_text(" ", strip=True)) >= 400
    ]
    if regions:
        best = max(regions, key=lambda tag: len(tag.get_text(" ", strip=True)))
        text = best.get_text(" ", strip=True)
        notes.append(f"main_content_region:{best.name}")
    else:
        text = soup.get_text(" ", strip=True)
    return text, full, notes


def focus_windows(text, focus, width=1500, limit=6):
    """Exact-text windows around each case-insensitive focus occurrence (non-overlapping)."""
    if not focus:
        return []
    folded, needle = text.casefold(), focus.casefold()
    windows, cursor = [], 0
    while len(windows) < limit:
        position = folded.find(needle, cursor)
        if position < 0:
            break
        start = max(0, position - width // 2)
        end = min(len(text), position + len(focus) + width // 2)
        if windows and start <= windows[-1]["end"]:
            windows[-1]["end"] = end
        else:
            windows.append({"start": start, "end": end})
        cursor = position + len(focus)
    return [{**w, "text": text[w["start"] : w["end"]]} for w in windows]


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
    if name in {"search_people", "enrich_person", "search_person_posts"}:
        if name in {"search_people", "enrich_person"}:
            from vendor_review.people import compact_role_records

            raw = compact_role_records(raw)
        serialized = json.dumps(raw, ensure_ascii=False)
        return {
            "records": raw if len(serialized) <= 18000 else None,
            "excerpt": serialized[:18000] if len(serialized) > 18000 else None,
            "truncated": len(serialized) > 18000,
            "provenance": "Indexed provider fields, not independent verification; roles and post dates require matching",
        }
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
            links = list(
                dict.fromkeys(
                    urljoin(page.get("url") or requested or "", a["href"])
                    for a in soup.find_all("a", href=True)
                    if urlsplit(urljoin(page.get("url") or requested or "", a["href"])).scheme
                    in {"http", "https"}
                )
            )[:40]
            text, full, notes = page_text(html)
            flags = [
                "relevance_and_claim_support_require_review",
                "final_redirect_url_not_exposed",
                *notes,
            ]
            if not page.get("success") or not text:
                flags.append("fetch_failed_or_empty")
            if any(
                marker in (page.get("title") or "").lower()
                for marker in ("page not found", "404 not found", "page unavailable")
            ):
                flags.append("possible_not_found")
            if any(
                marker in (text if len(text) > 1500 else full).lower()
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
                    "links": links,
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
    if name == "search_people":
        return (
            isinstance(raw, dict)
            and isinstance(raw.get("profiles"), list)
            and all(isinstance(p, dict) for p in raw["profiles"])
        )
    if name == "search_person_posts":
        return (
            isinstance(raw, dict)
            and isinstance(raw.get("posts"), list)
            and all(isinstance(p, dict) for p in raw["posts"])
        )
    if name == "enrich_person":
        return (
            isinstance(raw, list)
            and len(raw) == 1
            and all(
                isinstance(r, dict)
                and isinstance(r.get("matches"), list)
                and all(isinstance(m.get("person_data"), dict) for m in r["matches"])
                for r in raw
            )
        )
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
