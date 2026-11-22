"""Crustdata ranked company search as the candidate-discovery step (read-only, bounded).

Contract (official docs, checked 2026-11-22):
https://docs.crustdata.com/company-docs/search/reference.md#ranked-search
- POST /company/search with `search: {query, mode}`; mode is hybrid (default), lexical or semantic.
- Ranked `limit` is 1-100; `sorts` are rejected; `filters` are hard constraints applied before
  retrieval. Operators include `in`, `not_in`, `=>`, `=<` (not `>=`/`<=`).
- Response `{companies, next_cursor, total_count}`; ranked `total_count` is null. Results are in
  relevance order. **No relevance score is returned.**
- 0.03 credits per result plus premium groups. Only non-premium `basic_info` and `locations`
  fields are requested or filtered here; account prices from /account/endpoints still govern.
- Canonical `basic_info.employee_count_range` labels are read from the documented-free
  POST /company/search/autocomplete (https://docs.crustdata.com/company-docs/autocomplete/introduction.md),
  never guessed.

Selecting the "best" candidates:
1. A short product-focused query (the long brief made small startups that echo its wording win).
2. Free hard filters: a minimum company size and a minimum age, so tiny or brand-new firms do
   not take the slots. Both are configurable and disclosed.
3. A larger pool is retrieved, then reranked locally by a transparent discovery-fit score
   (brief-term coverage in the indexed description, size, maturity, region mention), and the
   top k are kept. The score is a shortlist heuristic, not evidence that a company meets any
   requirement; the single-vendor evidence review decides that.
"""

from __future__ import annotations

import json
import math
import os
import re
import time
import uuid
from datetime import date
from typing import Literal

from pydantic import Field, field_validator

from vendor_review.schemas import StrictInput

FIELDS = [
    "crustdata_company_id",
    "basic_info.name",
    "basic_info.primary_domain",
    "basic_info.website",
    "basic_info.description",
    "basic_info.employee_count_range",
    "basic_info.year_founded",
    "locations.country",
    "locations.headquarters",
]


class CompanySearch(StrictInput):
    query: str = Field(min_length=3, max_length=1000)
    mode: Literal["hybrid", "lexical", "semantic"] = "hybrid"
    hq_countries: list[str] = Field(
        default_factory=list,
        max_length=5,
        description="Optional HQ-country hard filter (ISO-3 code or full name). Buyer service "
        "geography is NOT an HQ filter; use only when the buyer asks for local vendors.",
    )
    employee_ranges: list[str] = Field(
        default_factory=list,
        max_length=20,
        description="Allowed canonical employee_count_range labels (from autocomplete)",
    )
    founded_on_or_before: int | None = Field(default=None, ge=1800, le=2100)
    limit: int = Field(default=4, ge=1, le=25)

    @field_validator("hq_countries", "employee_ranges")
    @classmethod
    def short_values(cls, values):
        if any(not v.strip() or len(v) > 60 for v in values):
            raise ValueError("Filter values must be short nonempty labels")
        return [v.strip() for v in values]


class CompanyAutocomplete(StrictInput):
    field: Literal["basic_info.employee_count_range", "basic_info.company_type"]
    query: str = Field(default="", max_length=100)
    limit: int = Field(default=100, ge=1, le=100)


DISCOVERY_TOOLS = {
    "search_companies": (
        CompanySearch,
        "POST",
        "/company/search",
        "Ranked company search for candidate discovery. Results are leads, not evidence.",
    ),
    "company_autocomplete": (
        CompanyAutocomplete,
        "POST",
        "/company/search/autocomplete",
        "Canonical indexed values for a company field (documented free).",
    ),
}
# Documented free POST endpoints. A returned charge above zero still blocks further paid dispatch.
DOCUMENTED_FREE = {"/company/search/autocomplete"}


def company_search_body(value):
    if isinstance(value, CompanyAutocomplete):
        return {"field": value.field, "query": value.query, "limit": value.limit}
    body = {
        "search": {"query": value.query, "mode": value.mode},
        "fields": FIELDS,
        "limit": value.limit,
    }
    conditions = []
    if value.hq_countries:
        conditions.append({"field": "locations.country", "type": "in", "value": value.hq_countries})
    if value.employee_ranges:
        conditions.append(
            {
                "field": "basic_info.employee_count_range",
                "type": "in",
                "value": value.employee_ranges,
            }
        )
    if value.founded_on_or_before is not None:
        conditions.append(
            {"field": "basic_info.year_founded", "type": "=<", "value": value.founded_on_or_before}
        )
    if len(conditions) == 1:
        body["filters"] = conditions[0]
    elif conditions:
        body["filters"] = {"op": "and", "conditions": conditions}
    return body


def valid_company_search(raw):
    return (
        isinstance(raw, dict)
        and isinstance(raw.get("companies"), list)
        and all(isinstance(c, dict) for c in raw["companies"])
    )


def valid_autocomplete(raw):
    return isinstance(raw, dict) and isinstance(raw.get("suggestions"), list)


# ---------- query ----------

FILLER = re.compile(r"\b(replace|replacing|spreadsheets?|in-house|our|we|need|want|tool)\b", re.I)


def semantic_query(brief) -> str:
    """A short, product-focused description of what is being bought, built only from the brief.

    Budget, deployment, integration product names and locations are left out of the retrieval
    query: they made the long query reward companies that merely repeat those words. They are
    still used later as hard filters, reranking signals and evaluation questions.
    """
    category = brief.service_category.strip() or "software"
    caps = [m.strip() for m in brief.must_haves[:4] if m.strip()]
    text = f"{category} vendor"
    if brief.use_case:
        purpose = re.sub(r"\s{2,}", " ", FILLER.sub("", brief.use_case)).strip(" .,")
        # Removing filler can leave a dangling connector ("... and to manage"); drop it.
        connector = r"^(?:(?:and|or|to|for|with)\s+|,\s*)+"
        purpose = re.sub(connector, "", purpose, flags=re.I)[:160]
        if purpose:
            text += f". Use: {purpose}"
    if caps:
        text += ". Capabilities: " + ", ".join(caps)
    market = market_country(brief)
    if market:
        # The buyer's market (a country, not a street address) matters for location-bound
        # services such as couriers; without it, results skewed to other countries.
        text += f". Market: businesses in {market[0]}"
    return text[:600]


# Country of the buyer's market, from the brief's geography. ISO-3 codes are accepted by
# company search `locations.country` filters (documented: ISO-3 codes or full names).
COUNTRIES = {
    "india": ("India", "IND"), "united states": ("United States", "USA"), "usa": ("United States", "USA"),
    "united kingdom": ("United Kingdom", "GBR"), "uk": ("United Kingdom", "GBR"),
    "singapore": ("Singapore", "SGP"), "uae": ("United Arab Emirates", "ARE"),
    "united arab emirates": ("United Arab Emirates", "ARE"), "australia": ("Australia", "AUS"),
    "canada": ("Canada", "CAN"), "germany": ("Germany", "DEU"),
}  # fmt: skip
INDIAN_REGIONS = {
    "andhra pradesh", "assam", "bihar", "chhattisgarh", "delhi", "delhi ncr", "ncr", "goa",
    "gujarat", "haryana", "himachal pradesh", "jharkhand", "karnataka", "kerala",
    "madhya pradesh", "maharashtra", "odisha", "punjab", "rajasthan", "tamil nadu",
    "telangana", "uttar pradesh", "uttarakhand", "west bengal", "south india", "north india",
    "bengaluru", "bangalore", "mumbai", "chennai", "hyderabad", "pune", "kolkata", "pan-india",
    "pan india",
}  # fmt: skip


def market_country(brief):
    """(name, ISO-3) when every geography term points to one country; otherwise None."""
    found = set()
    for term in getattr(brief, "geography", []) or []:
        t = term.strip().lower()
        if not t:
            continue
        if t in INDIAN_REGIONS or "india" in t:
            found.add(COUNTRIES["india"])
            continue
        match = next(
            (v for k, v in COUNTRIES.items() if re.search(rf"\b{re.escape(k)}\b", t)), None
        )
        if not match:
            return None
        found.add(match)
    return found.pop() if len(found) == 1 else None


# ---------- reranking ----------

STOP = {
    "and", "or", "the", "for", "with", "a", "an", "of", "to", "in", "on", "support", "system",
    "systems", "management", "operations", "per", "from", "one", "all", "via", "based",
}  # fmt: skip


def terms(text):
    return {
        w[:-1] if w.endswith("s") and len(w) > 4 else w
        for w in re.findall(r"[a-z0-9][a-z0-9/+-]{1,}", text.lower())
        if w not in STOP
    }


def range_floor(label):
    match = re.match(r"\s*(\d[\d,]*)", label or "")
    return int(match.group(1).replace(",", "")) if match else None


def fit_score(company, brief, today=None):
    """Transparent 0-1 discovery-fit heuristic from indexed fields. Not requirement evidence."""
    info = company.get("basic_info") or {}
    loc = company.get("locations") or {}
    description = (info.get("description") or "").lower()
    wanted = [brief.service_category, *brief.must_haves, *brief.nice_to_haves[:2]]
    groups = [terms(item) for item in wanted if item.strip()]
    have = terms(description)
    covered = [g for g in groups if g and len(g & have) / len(g) >= 0.5]
    brief_match = len(covered) / len(groups) if groups else 0.0
    floor = range_floor(info.get("employee_count_range"))
    scale = min(1.0, math.log10(floor) / 3) if floor and floor > 1 else 0.0  # 1,000+ -> 1
    year = info.get("year_founded")
    current = (today or date.today()).year
    maturity = min(1.0, max(0, current - year) / 10) if isinstance(year, int) else 0.0
    where = " ".join([loc.get("headquarters") or "", loc.get("country") or "", description]).lower()
    market = market_country(brief)
    terms_ = [g.lower() for g in brief.geography if g.strip()]
    if market:
        terms_ += [market[0].lower(), market[1].lower()]
    region = 1.0 if any(re.search(rf"\b{re.escape(t)}\b", where) for t in terms_) else 0.0
    weights = {"brief_match": 0.45, "scale": 0.2, "maturity": 0.15, "region": 0.2}
    parts = {"brief_match": brief_match, "scale": scale, "maturity": maturity, "region": region}
    score = sum(weights[k] * parts[k] for k in weights)
    return round(score, 4), {k: round(v, 3) for k, v in parts.items()}, weights


class CrustdataDiscovery:
    """Discovery plug-in: free size-label lookup, one bounded ranked search, local rerank."""

    synthetic = False

    def __init__(self, settings=None, ledger=None, client=None, event=print, brief_loader=None):
        from vendor_review.config import Settings
        from vendor_review.crustdata import Crustdata
        from vendor_review.store import Ledger

        self.settings = settings or Settings.load()
        self.ledger = ledger or Ledger(
            self.settings.data_dir / "discovery-ledger.sqlite", self.settings
        )
        self.client = client or Crustdata(self.settings, self.ledger, event=event)
        self.event = event
        self.pool = int(os.environ.get("DISCOVERY_POOL", "12"))
        self.min_employees = int(os.environ.get("DISCOVERY_MIN_EMPLOYEES", "51"))
        self.min_age_years = int(os.environ.get("DISCOVERY_MIN_AGE_YEARS", "3"))
        self.mode = os.environ.get("DISCOVERY_MODE", "hybrid")
        self.last = {}

    def size_labels(self, thread, turn, deadline):
        """Canonical size buckets at or above the minimum, read from free autocomplete."""
        if self.min_employees <= 1:
            return []
        result = self.client.execute(
            "company_autocomplete",
            {"field": "basic_info.employee_count_range", "query": "", "limit": 100},
            thread,
            turn,
            f"{thread}:sizes",
            deadline,
        )
        if result.get("status") != "ok":
            raise RuntimeError(
                f"Size labels unavailable: {result.get('message') or result['status']}"
            )
        values = [s.get("value") for s in result["data"].get("suggestions", []) if s.get("value")]
        keep = [v for v in values if (range_floor(v) or 0) >= self.min_employees]
        if not keep:
            raise RuntimeError(
                "No canonical size bucket meets the minimum; refusing to guess labels"
            )
        return keep

    def find(self, spec, brief=None):
        from vendor_review.pipeline import Candidate

        thread = "discovery:" + spec.run_id
        self.ledger.session(thread)
        turn = uuid.uuid4().hex
        deadline = time.monotonic() + self.settings.turn_seconds
        if self.client.access is None:
            pre = self.client.preflight(thread, turn, deadline)
            if pre.get("status") != "ok":
                raise RuntimeError("Crustdata preflight failed: " + str(pre.get("message")))
        sizes = self.size_labels(thread, turn, deadline)
        pool = max(spec.top_k, min(self.pool, 25))
        args = {
            "query": spec.semantic_query,
            "mode": self.mode if self.mode in {"hybrid", "lexical", "semantic"} else "hybrid",
            "limit": pool,
            "employee_ranges": sizes,
        }
        if self.min_age_years > 0:
            args["founded_on_or_before"] = date.today().year - self.min_age_years
        view = brief or spec_brief(spec)
        market = market_country(view)
        share = float(os.environ.get("DISCOVERY_LOCAL_SHARE", "0.67"))
        # Local-first pool: most slots for companies headquartered in the buyer's market, the
        # rest global. Same total results, so the same price as one search of `pool`.
        plan = [("", pool, [])]
        if market and 0 < share < 1 and pool >= 2:
            local = max(1, min(pool - 1, round(pool * share)))
            plan = [(":local", local, [market[1]]), (":global", pool - local, [])]
        companies, sources, seen = [], {}, set()
        for suffix, limit, countries in plan:
            call = {**args, "limit": limit, **({"hq_countries": countries} if countries else {})}
            result = self.client.execute(
                "search_companies", call, thread, turn, f"discovery:{spec.run_id}{suffix}", deadline
            )
            self.last = {"result": result, "filters": call}
            if result.get("status") != "ok":
                raise RuntimeError(
                    f"Company search {result.get('status')}: {result.get('message') or ''}".strip()
                )
            data = result.get("data") or {}
            if data.get("truncated") or data.get("records") is None:
                raise RuntimeError("Company search capture was truncated; reduce DISCOVERY_POOL")
            for company in data["records"].get("companies", []):
                cid = company.get("crustdata_company_id")
                if cid in seen:
                    continue
                seen.add(cid)
                companies.append(company)
                sources[cid] = (
                    f"crustdata /company/search{' (HQ ' + countries[0] + ')' if countries else ''}"
                    f" · artifact {result['artifact_id']} · op {result['operation_id']}"
                )
        filters = f"size ≥{self.min_employees} employees" if sizes else "no size filter"
        if "founded_on_or_before" in args:
            filters += f", founded ≤{args['founded_on_or_before']}"
        if len(plan) == 2:
            filters += f", {plan[0][1]} of {pool} slots HQ in {market[0]}"
        out = []
        for rank, company in enumerate(companies, 1):
            source = sources[company.get("crustdata_company_id")]
            info = company.get("basic_info") or {}
            loc = company.get("locations") or {}
            score, parts, weights = fit_score(company, view)
            out.append(
                Candidate(
                    name=info.get("name") or f"Company {company.get('crustdata_company_id')}",
                    domain=(info.get("primary_domain") or "").lower().removeprefix("www."),
                    crustdata_company_id=company.get("crustdata_company_id"),
                    why_relevant=(info.get("description") or "")[:600],
                    discovery_source=source,
                    relevance=score,
                    rank=rank,
                    headquarters=loc.get("headquarters") or loc.get("country") or "",
                    employee_count_range=info.get("employee_count_range") or "",
                    website=info.get("website") or "",
                    year_founded=info.get("year_founded"),
                    discovery_fit={
                        "score": score,
                        "parts": parts,
                        "weights": weights,
                        "pool_size": len(companies),
                        "filters": filters,
                        "query": spec.semantic_query,
                    },
                )
            )
        out.sort(key=lambda c: (-c.relevance, c.rank))
        self.event(
            f"discovery {spec.run_id}: pool {len(out)}, charge {result.get('actual_credits')}"
        )
        return out


def spec_brief(spec):
    """Minimal brief view for reranking when only the spec is available."""
    from types import SimpleNamespace

    kinds = {q.kind: [] for q in spec.questions}
    for q in spec.questions:
        kinds[q.kind].append(q.text)
    return SimpleNamespace(
        service_category=spec.category,
        must_haves=kinds.get("must_have", []),
        nice_to_haves=kinds.get("nice_to_have", []),
        geography=spec.geography,
    )


def compact_company_search(raw):
    serialized = json.dumps(raw, ensure_ascii=False)
    return {
        "records": raw if len(serialized) <= 60000 else None,
        "excerpt": serialized[:60000] if len(serialized) > 60000 else None,
        "truncated": len(serialized) > 60000,
        "provenance": "Indexed company fields in relevance order; no score; discovery leads only",
    }
