"""Bounded professional index requests, public-role evidence only; no contacts or outreach."""

from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, field_validator

from vendor_review.schemas import StrictInput

PERSON_FIELDS = [
    "crustdata_person_id",
    "basic_profile.name",
    "basic_profile.current_title",
    "social_handles.professional_network_identifier.profile_url",
    "experience.employment_details.current",
    "experience.employment_details.past",
]
PROFILE_FIELDS = [
    "basic_profile.name",
    "basic_profile.current_title",
    "social_handles.professional_network_identifier.profile_url",
    "experience",
    "updated_at",
]
POST_FIELDS = ["share_urn", "share_url", "text", "post_type", "date_posted", "actor", "hyperlinks"]


def public_profile_url(profile):
    handles = profile.get("social_handles") or {}
    return (handles.get("professional_network_identifier") or {}).get("profile_url")


class PeopleSearch(StrictInput):
    company_id: int = Field(gt=0)
    employment: Literal["current", "past", "any"] = "current"
    role_keywords: list[str] = Field(default_factory=list, max_length=5)
    limit: int = Field(default=3, ge=1, le=5)

    @field_validator("role_keywords")
    @classmethod
    def bounded_keywords(cls, values):
        if any(not value.strip() or len(value) > 100 for value in values):
            raise ValueError("Role keywords must be short nonempty phrases")
        return values


class PersonEnrich(StrictInput):
    profile_url: str = Field(max_length=500)

    @field_validator("profile_url")
    @classmethod
    def professional_profile(cls, value):
        url = urlsplit(value)
        if (
            url.scheme != "https"
            or url.hostname not in {"www.linkedin.com", "linkedin.com"}
            or not url.path.startswith("/in/")
            or not url.path[4:].strip("/")
            or url.username
            or url.password
            or url.query
            or url.fragment
        ):
            raise ValueError("Use a captured public LinkedIn /in/ profile URL without credentials")
        return value


class PostSearch(StrictInput):
    person_id: int = Field(gt=0)
    phrase: str = Field(default="", max_length=150)
    limit: int = Field(default=2, ge=1, le=3)


PEOPLE_TOOLS = {
    "search_people": (
        PeopleSearch,
        "POST",
        "/person/search",
        "Find a few relevant current/former professionals at a resolved company. Indexed roles are attributed leads, not proof of buying involvement.",
    ),
    "enrich_person": (
        PersonEnrich,
        "POST",
        "/person/enrich",
        "Read one discovered professional profile and employment timeline. No email/phone/contact data.",
    ),
    "search_person_posts": (
        PostSearch,
        "POST",
        "/social_post/search",
        "Read a few indexed public posts by one discovered person; preserve author, post type and date. No reactors, comments or contact data.",
    ),
}


def people_body(value):
    if isinstance(value, PeopleSearch):
        root = "experience.employment_details" + (
            "." + value.employment if value.employment != "any" else ""
        )
        filters = {"field": root + ".company_id", "type": "=", "value": value.company_id}
        if value.role_keywords:
            filters = {
                "op": "and",
                "conditions": [
                    filters,
                    {
                        "op": "or",
                        "conditions": [
                            {"field": root + ".title", "type": "[.]", "value": word}
                            for word in value.role_keywords
                        ],
                    },
                ],
            }
        return {"filters": filters, "fields": PERSON_FIELDS, "limit": value.limit}
    if isinstance(value, PersonEnrich):
        return {"professional_network_profile_urls": [value.profile_url], "fields": PROFILE_FIELDS}
    if isinstance(value, PostSearch):
        filters = {
            "op": "and",
            "conditions": [
                {"field": "actor.crustdata_entity_id", "type": "=", "value": value.person_id},
                {"field": "actor.actor_type", "type": "=", "value": "person"},
                {"field": "post_type", "type": "=", "value": "original"},
            ],
        }
        if value.phrase:
            filters["conditions"].append({"field": "text", "type": "[.]", "value": value.phrase})
        return {"filters": filters, "fields": POST_FIELDS, "limit": value.limit}
    raise ValueError("Unknown professional request")


def filter_paths(filters):
    if "field" in filters:
        return [filters["field"]]
    return [path for child in filters.get("conditions", []) for path in filter_paths(child)]


def premium_total(entries, paths):
    """Account-specific longest prefixes, charged once per selected premium group/side."""
    selected = {}
    for path in paths:
        matches = [
            entry
            for entry in entries or []
            if path == entry["field"] or path.startswith(entry["field"] + ".")
        ]
        if matches:
            entry = max(matches, key=lambda e: len(e["field"]))
            selected[entry["field"]] = entry["credits"]
        # A selected whole section can include more narrowly priced children; reserve conservatively.
        for entry in entries or []:
            if entry["field"].startswith(path + "."):
                selected[entry["field"]] = entry["credits"]
    from decimal import Decimal

    return sum((Decimal(str(price)) for price in selected.values()), Decimal(0))


def project_professional_data(raw):
    """Retain only role/post research fields even if a provider ignores its projection."""

    def without_contacts(value):
        if isinstance(value, dict):
            return {
                key: without_contacts(item)
                for key, item in value.items()
                if key.lower()
                not in {
                    "contact",
                    "contacts",
                    "email",
                    "emails",
                    "business_email",
                    "business_emails",
                    "personal_email",
                    "personal_emails",
                    "phone",
                    "phones",
                    "phone_number",
                    "phone_numbers",
                }
            }
        if isinstance(value, list):
            return [without_contacts(item) for item in value]
        return value

    raw = without_contacts(raw)

    def keep_profile(profile):
        return {
            key: profile[key]
            for key in (
                "crustdata_person_id",
                "basic_profile",
                "social_handles",
                "experience",
                "updated_at",
                "metadata",
            )
            if key in profile
        }

    if isinstance(raw, dict) and "profiles" in raw:
        return {
            **{k: v for k, v in raw.items() if k != "profiles"},
            "profiles": [keep_profile(p) for p in raw["profiles"]],
        }
    if isinstance(raw, list):
        return [
            {
                **{k: v for k, v in row.items() if k != "matches"},
                "matches": [
                    {
                        "confidence_score": m.get("confidence_score"),
                        "person_data": keep_profile(m.get("person_data", {})),
                    }
                    for m in row.get("matches", [])
                ],
            }
            for row in raw
        ]
    if isinstance(raw, dict) and "posts" in raw:
        return {
            **{k: v for k, v in raw.items() if k != "posts"},
            "posts": [{k: v for k, v in post.items() if k in POST_FIELDS} for post in raw["posts"]],
        }
    return raw


def compact_role_records(raw):
    """Keep public identity/chronology in model context; full selected capture stays in ledger."""
    import copy

    result = copy.deepcopy(raw)

    def trim(profile):
        employment = (profile.get("experience") or {}).get("employment_details", {})
        for kind in ("current", "past"):
            if kind in employment:
                employment[kind] = [
                    {
                        key: value
                        for key, value in role.items()
                        if key
                        in {
                            "name",
                            "title",
                            "crustdata_company_id",
                            "start_date",
                            "end_date",
                            "company_status",
                        }
                    }
                    for role in employment[kind] or []
                ]
        return profile

    if isinstance(result, dict) and "profiles" in result:
        result["profiles"] = [trim(p) for p in result["profiles"]]
    if isinstance(result, list):
        for row in result:
            for match in row.get("matches", []):
                match["person_data"] = trim(match["person_data"])
    return result
