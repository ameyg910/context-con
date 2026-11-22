"""Source-grounded customer/professional references, scope, attribution and branch coverage."""

import calendar
import hashlib
import json
import re
from datetime import date
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field

from vendor_review.people import public_profile_url
from vendor_review.schemas import StrictInput


def host(url):
    return (urlsplit(url).hostname or "").lower().removeprefix("www.")


def on_domain(url, domain):
    name = host(url)
    return bool(domain and (name == domain or name.endswith("." + domain)))


def normalized(text):
    return re.sub(r"\s+", " ", text).strip()


class Citation(StrictInput):
    artifact_id: str
    url: str
    quote: str = Field(min_length=20, max_length=2000)
    source_kind: Literal[
        "vendor_document", "customer_account", "professional_statement", "third_party_analysis"
    ] = "vendor_document"
    reference_id: str = ""


class Reference(StrictInput):
    id: str = Field(pattern=r"^REF[1-9][0-9]*$")
    kind: Literal["customer", "professional", "third_party"]
    name: str = Field(min_length=1, max_length=200)
    domain: str = Field(default="", max_length=200)
    requirement_ids: list[str] = Field(min_length=1, max_length=40)
    relationship: Literal[
        "direct_customer",
        "integrator",
        "downstream_beneficiary",
        "partner",
        "vendor_employee",
        "former_vendor_employee",
        "customer_employee",
        "supplier",
        "unknown",
    ] = "unknown"
    product_scope: str = Field(min_length=1, max_length=600)
    period_scope: str = Field(
        min_length=1,
        max_length=300,
        description="Historical/current/unknown scope attributed to source; never infer current contract",
    )
    citations: list[Citation] = Field(min_length=1, max_length=20)
    limitations: str = Field(min_length=1, max_length=1500)
    person_id: int | None = Field(default=None, gt=0)
    profile_artifact_id: str = ""
    role_company_id: int | None = Field(default=None, gt=0)
    role_title: str = ""
    event_date: str = Field(default="", max_length=40)
    author_quote: str = Field(
        default="",
        max_length=1000,
        description="For an article, exact byline identifying the professional; otherwise keep unknown",
    )


class Coverage(StrictInput):
    branch: Literal["customer", "professional"]
    status: Literal["pending", "attempted", "blocked", "not_applicable", "sufficient"]
    requirement_ids: list[str] = Field(min_length=1, max_length=40)
    operation_ids: list[str] = Field(default_factory=list, max_length=50)
    reference_ids: list[str] = Field(default_factory=list, max_length=30)
    rationale: str = Field(min_length=1, max_length=1500)
    gaps: list[str] = Field(default_factory=list, max_length=30)


class ReadEvidence(StrictInput):
    artifact_id: str
    focus: str = Field(
        default="",
        max_length=200,
        description="Optional exact text to locate in a saved public page",
    )


def captures(messages):
    for message in messages:
        if message.type != "tool":
            continue
        try:
            result = json.loads(message.content)
        except (ValueError, TypeError):
            continue
        if isinstance(result, dict):
            yield result


def captured_pages(messages):
    found = {}
    for result in captures(messages):
        if result.get("status") not in {"ok", "partial"} or not result.get("artifact_id"):
            continue
        pages = []
        if result.get("api_path") in {"/web/enrich/live", "local:read_evidence"}:
            pages = result.get("data", [])
        if result.get("api_path") == "/social_post/search":
            raw = (result.get("data") or {}).get("records") or {}
            for post in raw.get("posts", []):
                text = post.get("text", "")
                pages.append(
                    {
                        "url": post.get("share_url"),
                        "title": "Indexed public post",
                        "excerpt": text,
                        "quality": ["indexed_post_attributed_not_independent_verification"],
                        "content_sha256": hashlib.sha256(normalized(text).encode()).hexdigest(),
                        "publication_date": post.get("date_posted"),
                        "post_type": post.get("post_type"),
                        "actor": post.get("actor", {}),
                        "links": (post.get("hyperlinks") or {}).get("other_urls", []),
                    }
                )
        for page in pages:
            key = (result["artifact_id"], page.get("url"))
            previous = found.get(key, {})
            passages = list(dict.fromkeys([*previous.get("passages", []), page.get("excerpt", "")]))
            found[key] = {
                **previous,
                **page,
                "passages": passages,
                "artifact_id": result["artifact_id"],
                "retrieved_at_unix": result.get("retrieved_at_unix"),
            }
    return found


def company_records(messages):
    records = {}
    for result in captures(messages):
        if result.get("status") != "ok" or result.get("api_path") != "/company/identify":
            continue
        rows = (result.get("data") or {}).get("records") or []
        for row in rows:
            if len(row.get("matches", [])) != 1:
                continue
            company = row["matches"][0]["company_data"]
            domain = (
                (company.get("basic_info") or {})
                .get("primary_domain", "")
                .lower()
                .removeprefix("www.")
            )
            if domain:
                records[domain] = {**company, "artifact_id": result.get("artifact_id")}
    return records


def person_records(messages):
    found = {}
    for result in captures(messages):
        if result.get("status") != "ok":
            continue
        if result.get("api_path") not in {"/person/search", "/person/enrich"}:
            continue
        raw = (result.get("data") or {}).get("records")
        profiles = []
        if result.get("api_path") == "/person/search" and isinstance(raw, dict):
            profiles = raw.get("profiles", [])
        if result.get("api_path") == "/person/enrich" and isinstance(raw, list):
            profiles = [m["person_data"] for row in raw for m in row.get("matches", [])]
        for profile in profiles:
            if profile.get("crustdata_person_id"):
                found[(result["artifact_id"], profile["crustdata_person_id"])] = profile
    return found


def checked_passage(citation, pages):
    page = pages.get((citation.artifact_id, citation.url))
    if not page or not any(
        normalized(citation.quote) in normalized(text)
        for text in page.get("passages", [page.get("excerpt", "")])
    ):
        raise ValueError("Citation must match an exact captured passage and artifact")
    if any(
        flag in page.get("quality", [])
        for flag in (
            "possible_login_or_challenge",
            "fetch_failed_or_empty",
            "returned_host_differs",
            "possible_not_found",
        )
    ):
        raise ValueError("Blocked, empty or redirected-host evidence cannot support a reference")
    return page


def read_evidence(args, state, ledger):
    request = ReadEvidence.model_validate(args)
    saved = next(
        (r for r in captures(state["messages"]) if r.get("artifact_id") == request.artifact_id),
        None,
    )
    if not saved:
        raise ValueError("Read only artifacts already captured in this conversation")
    if saved.get("api_path") != "/web/enrich/live":
        return {
            "status": "ok",
            "artifact_id": request.artifact_id,
            "data": saved.get("data"),
            "message": "Reused captured provider result; no new external call",
        }
    row = ledger.db.execute(
        "SELECT payload FROM artifacts WHERE id=?", (request.artifact_id,)
    ).fetchone()
    if not row:
        raise ValueError("Saved raw artifact is unavailable")
    from bs4 import BeautifulSoup

    raw = json.loads(row[0])
    pages = []
    originals = captured_pages(state["messages"])
    for item in raw:
        original = originals.get((request.artifact_id, item.get("url")))
        if not original:
            continue
        soup = BeautifulSoup(item.get("content") or "", "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "noscript"]):
            tag.decompose()
        text = soup.get_text(" ", strip=True)
        position = text.casefold().find(request.focus.casefold()) if request.focus else 0
        start = max(0, position - 1000) if position >= 0 else 0
        pages.append(
            {
                **original,
                "excerpt": text[start : start + 8000],
                "passage_offset": start,
                "focus_found": position >= 0,
                "passages": [],
            }
        )
    return {
        "status": "ok",
        "api_path": "local:read_evidence",
        "artifact_id": request.artifact_id,
        "retrieved_at_unix": saved.get("retrieved_at_unix"),
        "data": pages,
        "message": "Reused original capture, not a fresh retrieval",
    }


def date_bounds(value):
    value = str(value or "").strip()[:10]
    try:
        if re.fullmatch(r"\d{4}", value):
            return date(int(value), 1, 1), date(int(value), 12, 31)
        if re.fullmatch(r"\d{4}-\d{2}", value):
            year, month = map(int, value.split("-"))
            return date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1])
        exact = date.fromisoformat(value)
        return exact, exact
    except ValueError:
        return None


def role_timeline(profile, company_id, title, event_date):
    event = date_bounds(event_date)
    employment = (profile.get("experience") or {}).get("employment_details", {})
    matched = []
    for kind in ("current", "past"):
        for role in employment.get(kind, []) or []:
            if (
                role.get("crustdata_company_id") == company_id
                and normalized(role.get("title", "")).casefold() == normalized(title).casefold()
            ):
                matched.append((kind, role))
    if not matched:
        return {"status": "role_not_matched", "roles": []}
    status = "date_unknown"
    statuses = []
    for kind, role in matched:
        start = date_bounds(role.get("start_date"))
        end = date_bounds(role.get("end_date"))
        refresh = date_bounds(
            profile.get("updated_at") or (profile.get("metadata") or {}).get("updated_at")
        )
        if not event or not start:
            statuses.append("date_unknown")
        elif event[1] < start[0] or (end and event[0] > end[1]):
            statuses.append("outside_recorded_role")
        elif event[0] >= start[1] and (
            (end and event[1] <= end[0])
            or (kind == "current" and refresh and event[1] <= refresh[0])
        ):
            statuses.append("consistent_with_indexed_role")
        else:
            statuses.append("date_precision_or_freshness_uncertain")
    if "consistent_with_indexed_role" in statuses:
        status = "consistent_with_indexed_role"
    elif all(value == "outside_recorded_role" for value in statuses):
        status = "outside_recorded_role"
    else:
        status = statuses[0]
    return {
        "status": status,
        "roles": [role for _, role in matched],
        "limitation": "Indexed role chronology, not independent verification or buying participation",
    }


def validate_reference(args, state):
    reference = Reference.model_validate(args)
    ids = {r["id"] for r in state.get("brief", {}).get("requirements", [])}
    if not set(reference.requirement_ids) <= ids:
        raise ValueError("Reference must map to existing requirements")
    pages = captured_pages(state["messages"])
    checked = [checked_passage(c, pages) for c in reference.citations]
    vendor = state["brief"].get("domain", "")
    extra = {
        "direct_contract_verified": False,
        "independently_verified": False,
        "attribution": "Source interpretation; does not establish a contract or all technical outcomes",
    }
    if reference.kind == "customer":
        company = company_records(state["messages"]).get(reference.domain)
        if not company or reference.domain == vendor:
            raise ValueError("Resolve the distinct customer's exact company domain first")
        vendor_name = re.sub(r"\W+", "", state["brief"].get("vendor", "")).casefold()
        if not vendor_name or not any(
            vendor_name in re.sub(r"\W+", "", c.quote).casefold() for c in reference.citations
        ):
            raise ValueError(
                "Customer relationship evidence must explicitly identify the vendor; unrelated pages are not corroboration"
            )
        extra.update(
            {
                "resolved_name": (company.get("basic_info") or {}).get("name"),
                "company_id": company.get("crustdata_company_id"),
                "identity_artifact_id": company["artifact_id"],
                "customer_owned_account": any(
                    on_domain(c.url, reference.domain) for c in reference.citations
                ),
            }
        )
    elif reference.kind == "professional":
        profile = person_records(state["messages"]).get(
            (reference.profile_artifact_id, reference.person_id)
        )
        if not profile:
            raise ValueError("Professional needs a captured indexed profile/person ID")
        name = (profile.get("basic_profile") or {}).get("name", "")
        if normalized(name).casefold() != normalized(reference.name).casefold():
            raise ValueError("Professional name and captured person identity do not match")
        original = [
            page
            for page in checked
            if (page.get("actor") or {}).get("crustdata_entity_id") == reference.person_id
            and (page.get("actor") or {}).get("actor_type") == "person"
            and page.get("post_type") == "original"
        ]
        byline = (
            reference.author_quote
            and reference.name.casefold() in reference.author_quote.casefold()
            and re.search(r"\b(by|author|written)\b", reference.author_quote, re.I)
            and any(
                normalized(reference.author_quote) in normalized(p.get("excerpt", ""))
                for p in checked
            )
        )
        if reference.event_date and not any(
            (p.get("publication_date") or "").startswith(reference.event_date) for p in checked
        ):
            if not any(reference.event_date in p.get("excerpt", "") for p in checked):
                raise ValueError(
                    "Event date must be explicit in captured source, not retrieval time"
                )
        extra.update(
            {
                "authorship": "indexed_original_post"
                if original
                else "captured_byline_needs_review"
                if byline
                else "unconfirmed",
                "profile_url": public_profile_url(profile),
                "authored_sources": [
                    {"artifact_id": p["artifact_id"], "url": p.get("url")}
                    for p in checked
                    if p in original
                    or (
                        byline
                        and normalized(reference.author_quote) in normalized(p.get("excerpt", ""))
                    )
                ],
                "timeline": role_timeline(
                    profile, reference.role_company_id, reference.role_title, reference.event_date
                ),
            }
        )
    else:
        if not reference.domain or not any(
            on_domain(c.url, reference.domain) for c in reference.citations
        ):
            raise ValueError("Third-party publisher domain must match the captured source")
    return {**reference.model_dump(), **extra}


def validate_coverage(args, state):
    coverage = Coverage.model_validate(args)
    if not set(coverage.requirement_ids) <= {
        r["id"] for r in state.get("brief", {}).get("requirements", [])
    }:
        raise ValueError("Coverage must map to existing requirements")
    ops = {
        r.get("operation_id")
        for r in captures(state["messages"])
        if r.get("api_path")
        in {
            "/web/search/live",
            "/web/enrich/live",
            "/person/search",
            "/person/enrich",
            "/social_post/search",
        }
    }
    if not set(coverage.operation_ids) <= ops:
        raise ValueError("Coverage cannot invent attempted operations")
    refs = {r["id"]: r for r in state.get("references", [])}
    if any(
        rid not in refs or refs[rid]["kind"] != coverage.branch for rid in coverage.reference_ids
    ):
        raise ValueError("Coverage reference IDs must belong to this branch")
    if coverage.status in {"attempted", "blocked", "sufficient"} and not coverage.operation_ids:
        raise ValueError("Attempted coverage needs recorded research operations")
    if coverage.status == "sufficient" and not coverage.reference_ids:
        raise ValueError("Sufficiency needs relevant scoped references, not just a search")
    if coverage.status == "sufficient":
        usable = [
            refs[rid]
            for rid in coverage.reference_ids
            if (coverage.branch == "customer" and refs[rid].get("customer_owned_account"))
            or (
                coverage.branch == "professional"
                and refs[rid].get("authorship") not in {None, "unconfirmed"}
            )
        ]
        if not all(
            any(req in ref["requirement_ids"] for ref in usable) for req in coverage.requirement_ids
        ):
            raise ValueError(
                "Sufficiency must cover each listed requirement with source-grounded branch evidence, not leads"
            )
    if coverage.status in {"blocked", "attempted"} and not coverage.gaps:
        raise ValueError("Partial/blocked work must disclose missing evidence")
    return coverage.model_dump()
