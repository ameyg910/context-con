"""Final verdict and next-step recommendations for a finished search run.

Everything here is derived deterministically from the saved comparison and V1 results: no
model writes the verdict, so every statement traces back to a recorded answer or quote.
Recommendations are procurement next steps (questions, demos, pilot checks, quotes), never a
supplier approval or a claim that a vendor lacks something it did not publish.
"""

from __future__ import annotations

import json

from vendor_review.brief import BuyerBrief
from vendor_review.pipeline import (
    CRITICAL_KINDS,
    Candidate,
    Comparison,
    SearchSpec,
    V1Result,
)

CAVEATS = [
    "Evidence is what each vendor publishes about itself; nothing here is independently "
    "verified, tested or certified.",
    "“Cannot verify” means no admissible public evidence was found, not that the vendor lacks "
    "the capability.",
    "No vendor was contacted. Rankings use only the evidence captured during this run.",
]


def evidence_row(question, answer):
    ev = answer.evidence[0] if answer.evidence else None
    return {
        "requirement": question.text,
        "kind": question.kind,
        "summary": answer.summary,
        "quote": ev.passage_or_field if ev else "",
        "url": ev.url if ev else "",
        "retrieved_at": ev.retrieved_at if ev else "",
        "missing": answer.missing,
    }


def build_verdict(run: dict, evaluations: dict) -> dict:
    spec = SearchSpec.model_validate_json(run["spec"])
    brief = BuyerBrief.model_validate_json(run["brief"])
    candidates = {
        c.key: c for c in (Candidate.model_validate(x) for x in json.loads(run["candidates"]))
    }
    comparison = Comparison.model_validate_json(run["comparison"])
    results = {
        k: V1Result.model_validate_json(v["result"])
        for k, v in evaluations.items()
        if v.get("result")
    }
    questions = {q.id: q for q in spec.questions}

    vendors = []
    for row in comparison.ranking:
        cand = candidates.get(row.candidate_key)
        result = results.get(row.candidate_key)
        supported, partial, unverified, contradicted = [], [], [], []
        for answer in result.answers if result else []:
            q = questions.get(answer.question_id)
            if not q:
                continue
            if answer.verdict == "supported" and answer.evidence:
                supported.append(evidence_row(q, answer))
            elif answer.verdict == "partially_supported":
                partial.append(evidence_row(q, answer))
            elif answer.verdict == "contradicted":
                contradicted.append(evidence_row(q, answer))
            else:
                unverified.append(q.text)
        vendors.append(
            {
                "key": row.candidate_key,
                "name": row.name,
                "domain": cand.domain if cand else "",
                "website": cand.website if cand else "",
                "headquarters": cand.headquarters if cand else "",
                "size": cand.employee_count_range if cand else "",
                "founded": cand.year_founded if cand else None,
                "status": row.status,
                "score": row.score,
                "critical_supported": row.must_have_supported,
                "critical_total": row.must_have_total,
                "supported": supported,
                "partial": partial,
                "contradicted": contradicted,
                "unverified": unverified,
                "disqualified_by": row.disqualified_by,
                "credits": row.credits,
                "pricing_summary": result.pricing_summary if result else "",
                "questions": comparison.vendor_questions.get(row.candidate_key, []),
            }
        )

    ranked = [v for v in vendors if not v["disqualified_by"]]
    with_evidence = [v for v in ranked if v["critical_supported"] > 0 or v["partial"]]
    if comparison.recommended_key:
        best = next(v for v in vendors if v["key"] == comparison.recommended_key)
        kind, leader = "recommend", best
        headline = f"Recommended for a scoped pilot: {best['name']}"
        detail = (
            f"{best['name']} has published evidence for all {best['critical_total']} critical "
            "requirements. Confirm the open items below before signing."
        )
    elif with_evidence:
        kind, leader = "leading_candidate", with_evidence[0]
        headline = f"No vendor proven on every must-have. Leading candidate: {leader['name']}"
        detail = (
            f"{leader['name']} has evidence for {leader['critical_supported']} of "
            f"{leader['critical_total']} critical requirements, the most of any vendor. Close "
            "the gaps below with the vendors before choosing."
        )
    elif vendors:
        kind, leader = "no_evidence", None
        headline = "No vendor showed public evidence for the critical requirements"
        detail = "Treat this shortlist as leads only and gather evidence directly from vendors."
    else:
        kind, leader = "pending", None
        headline, detail = "No evaluated vendors yet", ""

    recommendations = []
    if kind == "recommend":
        recommendations.append(
            {
                "title": f"Run a scoped pilot with {leader['name']}",
                "detail": "Use the pilot checks below as pass/fail criteria before any contract.",
            }
        )
    elif kind == "leading_candidate":
        shortlist = [v["name"] for v in with_evidence[:2]]
        recommendations.append(
            {
                "title": "Shortlist for demos: " + " and ".join(shortlist),
                "detail": "Ask each to demonstrate every must-have live, on your own sample orders.",
            }
        )
    elif kind == "no_evidence":
        recommendations.append(
            {
                "title": "Widen the search or ask vendors directly",
                "detail": "Request product documentation for each must-have; public pages were silent.",
            }
        )
    critical_texts = [q.text for q in spec.questions if q.kind in CRITICAL_KINDS]
    if vendors:
        common = [
            t
            for t in critical_texts
            if all(t not in [s["requirement"] for s in v["supported"]] for v in ranked)
        ]
        if common:
            recommendations.append(
                {
                    "title": "Ask every vendor to prove these (no one published evidence)",
                    "detail": "; ".join(common[:8]),
                }
            )
    for v in ranked[:2]:
        if v["questions"]:
            recommendations.append(
                {
                    "title": f"Questions for {v['name']}",
                    "detail": " · ".join(v["questions"][:5]),
                }
            )
    if brief.must_haves:
        scale = f" at your volume ({brief.scale})" if brief.scale else ""
        recommendations.append(
            {
                "title": "Pilot pass/fail checks",
                "detail": "; ".join(
                    f"{m}{scale if i == 0 else ''}" for i, m in enumerate(brief.must_haves[:8])
                ),
            }
        )
    # Pricing counts as verified only when a budget question is supported with evidence.
    priced = any(s["kind"] == "budget" for v in ranked for s in v["supported"])
    if brief.budget.stated and not brief.budget.no_fixed_budget and not priced:
        recommendations.append(
            {
                "title": "Get written quotes",
                "detail": f"No public pricing was verified. Request quotes{(' for ' + brief.scale) if brief.scale else ''} "
                f"and compare against your budget ({brief.budget.label()}).",
            }
        )
    if brief.timeline:
        recommendations.append(
            {
                "title": "Confirm onboarding timeline",
                "detail": f"Ask each shortlisted vendor for a written plan that meets: {brief.timeline}.",
            }
        )
    for v in vendors:
        if v["disqualified_by"]:
            recommendations.append(
                {
                    "title": f"Exclude {v['name']}",
                    "detail": "Evidence contradicts: " + "; ".join(v["disqualified_by"]),
                }
            )

    return {
        "verdict": kind,
        "headline": headline,
        "detail": detail,
        "leader_key": leader["key"] if leader else None,
        "brief": {
            "service": brief.service_category,
            "use_case": brief.use_case,
            "must_haves": brief.must_haves,
            "budget": brief.budget.label() if brief.budget.stated else "",
            "timeline": brief.timeline,
            "scale": brief.scale,
        },
        "vendors": vendors,
        "recommendations": recommendations,
        "caveats": CAVEATS,
        "total_credits": round(sum(v["credits"] for v in vendors), 2),
        "rationale": comparison.rationale,
    }
