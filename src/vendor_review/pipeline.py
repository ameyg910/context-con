"""Search stage contracts: brief -> candidate discovery -> v1 per candidate -> comparison.

`V1Runner` is the seam for the single-vendor evidence agent ("v1"). Its implementation lives
elsewhere; this module only fixes the request/response shape, persists every completed
evaluation so a restart never repeats it, and compares results deterministically.

Comparison rules (ours, deliberately conservative):
- A must-have counts only when v1 marked it `supported` with at least one evidence record.
- `contradicted` on a must-have disqualifies the vendor for recommendation.
- `cannot_verify` is never treated as support; it becomes a question for the vendor.
- No recommendation is made if no vendor has every must-have supported.
"""

from __future__ import annotations

import hashlib
import json
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from vendor_review.brief import BuyerBrief

Verdict = Literal["supported", "partially_supported", "contradicted", "cannot_verify"]


# ---------- discovery ----------


class Candidate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    domain: str = ""
    crustdata_company_id: int | None = None
    why_relevant: str = ""
    discovery_source: str = Field(default="", description="URL or API artifact that surfaced it")
    relevance: float = Field(default=0.0, ge=0, le=1)
    rank: int | None = Field(
        default=None, ge=1, description="Provider relevance order; not a score"
    )
    headquarters: str = ""
    employee_count_range: str = ""
    website: str = ""
    year_founded: int | None = None
    discovery_fit: dict = Field(
        default_factory=dict, description="Shortlist heuristic breakdown; not requirement evidence"
    )

    @property
    def key(self) -> str:
        basis = (self.domain or self.name).strip().lower()
        return hashlib.sha1(basis.encode()).hexdigest()[:12]


class Discovery(Protocol):
    def find(self, spec: "SearchSpec") -> list[Candidate]: ...


# ---------- v1 contract ----------


class RequirementQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    kind: Literal["must_have", "nice_to_have", "integration", "geography", "compliance", "budget"]
    text: str


class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid")
    url: str = ""
    artifact_id: str = ""
    passage_or_field: str = Field(description="Exact quoted passage or provider field path=value")
    publisher: str = ""
    source_date: str = Field(default="", description="Record/publication date; '' if unknown")
    retrieved_at: str = ""


class RequirementAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question_id: str
    verdict: Verdict
    summary: str
    evidence: list[Evidence] = Field(default_factory=list)
    missing: str = Field(default="", description="What would settle it, when not supported")


class RunCost(BaseModel):
    model_config = ConfigDict(extra="forbid")
    crustdata_credits: float = 0
    model_tokens: int = 0
    seconds: float = 0


class V1Request(BaseModel):
    model_config = ConfigDict(extra="forbid")
    run_id: str
    candidate: Candidate
    brief: BuyerBrief
    questions: list[RequirementQuestion]
    credit_limit: float
    seconds_limit: float


class V1Result(BaseModel):
    model_config = ConfigDict(extra="forbid")
    candidate_key: str
    status: Literal["completed", "partial", "failed", "not_connected"]
    answers: list[RequirementAnswer] = Field(default_factory=list)
    pricing_summary: str = ""
    pricing_evidence: list[Evidence] = Field(default_factory=list)
    cost: RunCost = Field(default_factory=RunCost)
    notes: str = ""


class V1Runner(Protocol):
    def evaluate(self, request: V1Request) -> V1Result: ...


class NotConnectedV1:
    """Honest placeholder until the single-vendor agent is wired in."""

    def evaluate(self, request: V1Request) -> V1Result:
        return V1Result(
            candidate_key=request.candidate.key,
            status="not_connected",
            notes="Single-vendor evidence agent (v1) is not connected in this build.",
        )


class NotConnectedDiscovery:
    def find(self, spec: "SearchSpec") -> list[Candidate]:
        # Explicitly named vendors are the buyer's own input, so they can still be evaluated.
        return [Candidate(name=v, why_relevant="Named by buyer") for v in spec.include_vendors]


# ---------- search spec ----------


class SearchSpec(BaseModel):
    """What discovery and v1 receive, derived only from the confirmed brief."""

    model_config = ConfigDict(extra="forbid")
    run_id: str
    brief_version: str
    category: str
    queries: list[str]
    semantic_query: str = ""
    search_mode: str = "hybrid"
    geography: list[str]
    include_vendors: list[str]
    exclude_vendors: list[str]
    questions: list[RequirementQuestion]
    top_k: int


def brief_version(brief: BuyerBrief) -> str:
    return hashlib.sha1(brief.model_dump_json().encode()).hexdigest()[:10]


def build_questions(brief: BuyerBrief) -> list[RequirementQuestion]:
    out: list[RequirementQuestion] = []

    def add(kind, text):
        out.append(RequirementQuestion(id=f"{kind[:2]}{len(out) + 1}", kind=kind, text=text))

    for item in brief.must_haves:
        add("must_have", item)
    for item in brief.integrations:
        add("integration", f"Integrates with {item}")
    if brief.geography:
        add("geography", "Operates in / covers " + ", ".join(brief.geography))
    for item in brief.compliance:
        add("compliance", f"Complies with {item}")
    for item in brief.nice_to_haves:
        add("nice_to_have", item)
    if brief.budget.stated and not brief.budget.no_fixed_budget:
        add("budget", "Published or quoted pricing fits " + brief.budget.label())
    return out


def build_spec(run_id: str, brief: BuyerBrief) -> SearchSpec:
    from vendor_review.discovery import semantic_query

    base = brief.service_category.strip()
    query = semantic_query(brief)
    return SearchSpec(
        run_id=run_id,
        brief_version=brief_version(brief),
        category=base,
        queries=[query],
        semantic_query=query,
        geography=brief.geography,
        include_vendors=brief.include_vendors,
        exclude_vendors=brief.exclude_vendors,
        questions=build_questions(brief),
        top_k=brief.top_k,
    )


# ---------- comparison ----------

CRITICAL_KINDS = {"must_have", "integration", "geography", "compliance"}


class CandidateScore(BaseModel):
    candidate_key: str
    name: str
    status: str
    must_have_supported: int
    must_have_total: int
    disqualified_by: list[str]
    unresolved: list[str]
    score: float
    credits: float


class Comparison(BaseModel):
    ranking: list[CandidateScore]
    recommendation: str
    recommended_key: str | None
    rationale: list[str]
    vendor_questions: dict[str, list[str]]


def _supported(answer: RequirementAnswer) -> bool:
    return answer.verdict == "supported" and bool(answer.evidence)


def compare(
    spec: SearchSpec, candidates: list[Candidate], results: dict[str, V1Result]
) -> Comparison:
    weights = {q.id: (3.0 if q.kind in CRITICAL_KINDS else 1.0) for q in spec.questions}
    critical = [q for q in spec.questions if q.kind in CRITICAL_KINDS]
    text = {q.id: q.text for q in spec.questions}
    rows, questions = [], {}
    for cand in candidates:
        res = results.get(cand.key)
        answers = {a.question_id: a for a in (res.answers if res else [])}
        got, dq, unresolved = 0.0, [], []
        for q in spec.questions:
            a = answers.get(q.id)
            if a and _supported(a):
                got += weights[q.id]
            elif a and a.verdict == "partially_supported" and a.evidence:
                got += weights[q.id] * 0.4
                unresolved.append(q.id)
            elif a and a.verdict == "contradicted" and q.kind in CRITICAL_KINDS:
                dq.append(q.id)
            else:
                unresolved.append(q.id)
        total = sum(weights.values()) or 1.0
        mh_ok = sum(1 for q in critical if q.id in answers and _supported(answers[q.id]))
        rows.append(
            CandidateScore(
                candidate_key=cand.key,
                name=cand.name,
                status=res.status if res else "pending",
                must_have_supported=mh_ok,
                must_have_total=len(critical),
                disqualified_by=[text[i] for i in dq],
                unresolved=[text[i] for i in unresolved],
                score=round(got / total, 3) if not dq else 0.0,
                credits=res.cost.crustdata_credits if res else 0.0,
            )
        )
        questions[cand.key] = [
            (answers[i].missing or f"Provide evidence: {text[i]}")
            if i in answers
            else f"Provide evidence: {text[i]}"
            for i in unresolved
        ][:5]
    rows.sort(key=lambda r: (-r.must_have_supported, -r.score, r.credits))
    eligible = [
        r for r in rows if not r.disqualified_by and r.must_have_supported == r.must_have_total
    ]
    rationale = []
    if not results or all(r.status in ("not_connected", "pending") for r in rows):
        rec, key = "No evaluation results yet: cannot recommend.", None
    elif eligible and critical:
        best = eligible[0]
        rec, key = f"Recommend {best.name} for a scoped pilot.", best.candidate_key
        rationale.append(
            f"{best.name} has evidence for all {best.must_have_total} critical requirements."
        )
        if best.unresolved:
            rationale.append("Still to confirm with the vendor: " + "; ".join(best.unresolved[:3]))
    else:
        top = rows[0] if rows else None
        rec = "Cannot verify that any vendor meets every must-have."
        key = None
        if top:
            rationale.append(
                f"Closest: {top.name} ({top.must_have_supported}/{top.must_have_total} critical "
                "requirements supported). Use the vendor questions before shortlisting."
            )
    return Comparison(
        ranking=rows,
        recommendation=rec,
        recommended_key=key,
        rationale=rationale,
        vendor_questions=questions,
    )


def dumps(model: BaseModel) -> str:
    return json.dumps(model.model_dump(mode="json"))
