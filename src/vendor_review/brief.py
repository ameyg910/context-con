"""Buyer brief: the structured context the intake chat collects before any vendor search.

The brief is our internal record, not an organizer or Crustdata schema. Everything in it comes
from the buyer's own words (or the loaded client profile); the intake model may only restate
what the buyer said, never invent requirements, budgets or vendors.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

BudgetPeriod = Literal["one_time", "monthly", "annual", "per_shipment", "per_user_month", "unknown"]
Criterion = Literal["cost", "feature_fit", "integration", "scale", "support", "compliance", "speed"]


class Budget(BaseModel):
    model_config = ConfigDict(extra="forbid")
    min_inr: float | None = Field(default=None, ge=0)
    max_inr: float | None = Field(default=None, ge=0)
    period: BudgetPeriod = "unknown"
    flexible: bool = False
    no_fixed_budget: bool = Field(
        default=False, description="Buyer explicitly said there is no fixed budget"
    )
    note: str = ""

    @property
    def stated(self) -> bool:
        return self.no_fixed_budget or self.max_inr is not None or self.min_inr is not None

    def label(self) -> str:
        if self.no_fixed_budget:
            return "No fixed budget"
        if not self.stated:
            return "Not stated"
        lo, hi = self.min_inr, self.max_inr
        rng = (
            f"₹{lo:,.0f}–₹{hi:,.0f}"
            if lo is not None and hi is not None
            else f"up to ₹{hi:,.0f}"
            if hi is not None
            else f"from ₹{lo:,.0f}"
        )
        period = "" if self.period == "unknown" else " " + self.period.replace("_", " ")
        return rng + period + (" (flexible)" if self.flexible else "")


class BuyerBrief(BaseModel):
    """What the buyer needs. Required fields gate the search; the rest sharpen it."""

    model_config = ConfigDict(extra="forbid")
    service_category: str = Field(
        default="", description="Kind of service/software sought, e.g. transport management system"
    )
    use_case: str = Field(default="", description="Problem to solve, in the buyer's words")
    must_haves: list[str] = Field(default_factory=list, description="Non-negotiable requirements")
    nice_to_haves: list[str] = Field(default_factory=list)
    budget: Budget = Field(default_factory=Budget)
    geography: list[str] = Field(
        default_factory=list, description="Regions/cities/lanes the service must cover"
    )
    scale: str = Field(default="", description="Volumes: shipments/month, warehouses, users")
    integrations: list[str] = Field(default_factory=list, description="Systems it must connect to")
    deployment: str = Field(default="", description="Cloud/on-prem, data residency, etc.")
    compliance: list[str] = Field(default_factory=list, description="e.g. GST e-invoicing, DPDP")
    timeline: str = Field(default="", description="When it must be live")
    deal_breakers: list[str] = Field(default_factory=list)
    include_vendors: list[str] = Field(default_factory=list, description="Vendors to consider")
    exclude_vendors: list[str] = Field(default_factory=list, description="Vendors to skip")
    priorities: list[Criterion] = Field(
        default_factory=list, description="Comparison criteria, most important first"
    )
    top_k: int = Field(default=4, ge=1, le=10, description="How many vendors to evaluate deeply")


REQUIRED: dict[str, str] = {
    "service_category": "What kind of service or software you need",
    "use_case": "The problem it should solve",
    "must_haves": "At least one must-have requirement",
    "budget": "A budget range (or confirmation there is no fixed budget)",
    "geography": "Where the service must operate",
}

RECOMMENDED: dict[str, str] = {
    "scale": "Expected volume",
    "integrations": "Systems it must integrate with",
    "priorities": "How to weigh vendors against each other",
    "timeline": "Go-live timeline",
}


def missing_required(brief: BuyerBrief) -> list[str]:
    missing = []
    for name in REQUIRED:
        value = getattr(brief, name)
        if name == "budget":
            if not value.stated:
                missing.append(name)
        elif not value:
            missing.append(name)
    return missing


def missing_recommended(brief: BuyerBrief) -> list[str]:
    return [name for name in RECOMMENDED if not getattr(brief, name)]


def completeness(brief: BuyerBrief) -> float:
    total = len(REQUIRED) * 2 + len(RECOMMENDED)
    got = (len(REQUIRED) - len(missing_required(brief))) * 2
    got += len(RECOMMENDED) - len(missing_recommended(brief))
    return round(got / total, 2)


LIST_FIELDS = {
    name
    for name, field in BuyerBrief.model_fields.items()
    if field.annotation is not None and str(field.annotation).startswith("list")
}


def merge_brief(brief: BuyerBrief, patch: dict) -> BuyerBrief:
    """Apply a model- or user-supplied patch. Lists are unioned (case-insensitive), scalars
    replaced only when the patch has a non-empty value, so a sloppy patch cannot erase data.
    Explicit removals go through `remove` lists: {"remove": {"must_haves": ["..."]}}."""
    data = brief.model_dump()
    removals = patch.get("remove") or {}
    for name, value in patch.items():
        if name == "remove" or name not in BuyerBrief.model_fields:
            continue
        if name == "priorities":
            if value:  # an ordering is replaced as a whole
                data[name] = list(dict.fromkeys(value))
        elif name in LIST_FIELDS:
            items = value if isinstance(value, list) else [value]
            seen = {str(x).strip().lower() for x in data[name]}
            for item in items:
                text = str(item).strip()
                if text and text.lower() not in seen:
                    data[name].append(text)
                    seen.add(text.lower())
        elif name == "budget" and isinstance(value, dict):
            data["budget"].update({k: v for k, v in value.items() if v not in (None, "")})
        elif value not in (None, "", []):
            data[name] = value
    for name, items in removals.items():
        if name in LIST_FIELDS:
            drop = {str(x).strip().lower() for x in items}
            data[name] = [x for x in data[name] if x.strip().lower() not in drop]
    return BuyerBrief.model_validate(data)
