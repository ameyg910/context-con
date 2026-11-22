"""SYNTHETIC fixtures for UI development and tests only. Never use for real answers.

Enable with  DISCOVERY=vendor_review.demo:DemoDiscovery  V1_RUNNER=vendor_review.demo:DemoV1
The UI shows a "synthetic data" banner whenever either is active. Vendor names are fictional.
"""

from __future__ import annotations

import time

from vendor_review.pipeline import (
    Candidate,
    Evidence,
    RequirementAnswer,
    RunCost,
    SearchSpec,
    V1Request,
    V1Result,
)

VENDORS = [
    ("Acme Route Cloud", "acmeroute.example"),
    ("Bharat FleetOS", "bharatfleet.example"),
    ("Cargo Lumen", "cargolumen.example"),
    ("Dakshin Logix", "dakshinlogix.example"),
    ("EastLane Systems", "eastlane.example"),
    ("Acme Route Cloud Pvt Ltd", "acmeroute.example"),  # duplicate record on purpose
]

PATTERNS = [
    ["supported", "supported", "partially_supported", "cannot_verify"],
    ["supported", "cannot_verify", "supported", "supported"],
    ["partially_supported", "supported", "contradicted", "cannot_verify"],
    ["cannot_verify", "cannot_verify", "supported", "partially_supported"],
    ["supported", "supported", "supported", "cannot_verify"],
]


class DemoDiscovery:
    synthetic = True

    def find(self, spec: SearchSpec) -> list[Candidate]:
        return [
            Candidate(
                name=name,
                domain=domain,
                why_relevant=f"SYNTHETIC: matches '{spec.category}'",
                discovery_source=f"https://{domain}/",
                relevance=round(0.9 - i * 0.08, 2),
            )
            for i, (name, domain) in enumerate(VENDORS)
        ]


class DemoV1:
    synthetic = True

    def __init__(self, delay: float = 1.2):
        self.delay = delay

    def evaluate(self, request: V1Request) -> V1Result:
        time.sleep(self.delay)
        idx = [d for _, d in VENDORS].index(request.candidate.domain) % len(PATTERNS)
        pattern = PATTERNS[idx]
        answers = []
        for i, q in enumerate(request.questions):
            verdict = pattern[i % len(pattern)]
            ev = []
            if verdict != "cannot_verify":
                ev = [
                    Evidence(
                        url=f"https://{request.candidate.domain}/docs#{q.id}",
                        passage_or_field=f"SYNTHETIC passage about: {q.text}",
                        publisher=request.candidate.name,
                        source_date="2026-10-0" + str(1 + i % 9),
                        retrieved_at="2026-11-22",
                    )
                ]
            answers.append(
                RequirementAnswer(
                    question_id=q.id,
                    verdict=verdict,
                    summary=f"SYNTHETIC {verdict.replace('_', ' ')}: {q.text}",
                    evidence=ev,
                    missing="" if verdict == "supported" else f"Vendor documentation for: {q.text}",
                )
            )
        return V1Result(
            candidate_key=request.candidate.key,
            status="completed",
            answers=answers,
            pricing_summary="SYNTHETIC: pricing on request",
            cost=RunCost(crustdata_credits=1.5 + idx * 0.4, model_tokens=12000, seconds=self.delay),
            notes="SYNTHETIC DEMO DATA",
        )
