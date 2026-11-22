"""Buyer-owned brief, claim map and transparent intake completeness."""

import re
from typing import Literal

from pydantic import Field

from vendor_review.schemas import StrictInput

CONSTRAINTS = ("geography", "integrations", "scale", "security", "budget", "timeline")


class Requirement(StrictInput):
    id: str = Field(pattern=r"^R[1-9][0-9]*$")
    text: str = Field(min_length=1, max_length=800)
    buyer_quote: str = Field(min_length=1, max_length=1500)
    priority: Literal["must", "should", "question", "unspecified"] = "unspecified"
    acceptance_criterion: str = Field(default="", max_length=800)


class Brief(StrictInput):
    vendor: str = Field(default="", max_length=200)
    domain: str = Field(default="", max_length=200)
    use_case: str = Field(default="", max_length=1500)
    requirements: list[Requirement] = Field(default_factory=list, max_length=40)
    constraints: dict[str, str] = Field(
        default_factory=dict,
        json_schema_extra={"properties": {key: {"type": "string"} for key in CONSTRAINTS}},
    )
    buyer_quotes: dict[str, str] = Field(
        default_factory=dict,
        description="Exact buyer quotes supporting vendor/domain/use_case and each constraint key",
        json_schema_extra={
            "properties": {
                key: {"type": "string"} for key in ("vendor", "domain", "use_case", *CONSTRAINTS)
            }
        },
    )


def validate_brief(args, messages):
    args = dict(args)
    if not args.get("domain") and args.get("buyer_quotes", {}).get("domain"):
        value = args["buyer_quotes"]["domain"]
        args["domain"] = value.split(":", 1)[-1].strip().rstrip(".")
    brief = Brief.model_validate(args)
    human = [str(m.content) for m in messages if m.type == "human"]

    def grounded(quote):
        def normalize(text):
            return re.sub(r"\s+", " ", text).strip().strip(".?!").casefold()

        return bool(quote.strip()) and any(normalize(quote) in normalize(text) for text in human)

    for key in CONSTRAINTS:
        quote = brief.buyer_quotes.get(key, "")
        if not brief.constraints.get(key) and grounded(quote):
            brief.constraints[key] = quote.split(":", 1)[-1].strip().rstrip(".")

    for key in ("vendor", "domain", "use_case", *brief.constraints):
        value = (
            getattr(brief, key, None) if key not in brief.constraints else brief.constraints[key]
        )
        if value and not grounded(brief.buyer_quotes.get(key) or value):
            raise ValueError(f"{key} needs an exact buyer quote; do not infer constraints")
        if value and not brief.buyer_quotes.get(key):
            brief.buyer_quotes[key] = value
    if set(brief.constraints) - set(CONSTRAINTS):
        raise ValueError("Use only the documented intake constraint categories")
    if len({r.id for r in brief.requirements}) != len(brief.requirements):
        raise ValueError("Requirement IDs must be unique")
    if any(not grounded(r.buyer_quote) for r in brief.requirements):
        raise ValueError("Each requirement needs an exact buyer quote")
    if any(
        r.acceptance_criterion
        and r.acceptance_criterion.lower() != "unknown"
        and not grounded(r.acceptance_criterion)
        for r in brief.requirements
    ):
        raise ValueError("Acceptance criteria must be buyer wording, or explicitly unknown")
    return brief.model_dump()


def readiness(data):
    brief = Brief.model_validate(data or {})
    missing = [key for key in ("vendor", "domain", "use_case") if not getattr(brief, key)]
    if not brief.requirements:
        missing.append("requirements")
    missing += [key for key in CONSTRAINTS if not brief.constraints.get(key, "").strip()]
    questions = []
    if any(key in missing for key in ("vendor", "domain")):
        questions.append("Which vendor/product and official website should I assess?")
    if "use_case" in missing or "requirements" in missing:
        questions.append(
            "What are you trying to achieve, and which questions or must-have capabilities matter most?"
        )
    gaps = [key for key in CONSTRAINTS if key in missing]
    if gaps:
        questions.append(
            "What constraints apply to "
            + ", ".join(gaps)
            + "? You can explicitly say unknown or not applicable; I will retain that uncertainty."
        )
    vague = [
        r.id
        for r in brief.requirements
        if not r.acceptance_criterion or r.priority == "unspecified"
    ]
    if vague:
        questions.append(
            "For "
            + ", ".join(vague)
            + ", what is essential versus preferred, and what measurable result would count as passing?"
        )
    return {
        "ready": not missing and not vague,
        "completeness_score": round(100 * (10 - len(missing)) / 10),
        "score_meaning": "Filled intake categories, not vendor quality or confidence; explicit unknowns count as answered",
        "missing": missing,
        "specificity_gaps": vague,
        "specificity_score": round(
            100
            * sum(
                bool(r.acceptance_criterion) + (r.priority != "unspecified")
                for r in brief.requirements
            )
            / (2 * len(brief.requirements))
        )
        if brief.requirements
        else 0,
        "questions": questions,
        "unknown_constraints": [
            k
            for k, v in brief.constraints.items()
            if v.lower() in {"unknown", "unsure", "not decided"}
        ],
    }
