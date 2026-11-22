# Intake and preliminary vendor research — 2026-11-22

Implemented in `context-con`, extending the existing bounded LangGraph foundation. No commit, remote push, deployment, account, outreach or watch was created. Gemini remains primary and restricted to the documented free-tier model allowlist; local inference is optional.

## Delivered behavior

- Default CLI mode gathers a buyer brief, requirement IDs, priorities, acceptance criteria and six constraint categories. Missing fields and vague requirements trigger follow-up questions. Explicit unknowns remain visible. Paid research is blocked until readiness passes.
- Completeness measures answered intake categories; specificity measures declared priority/acceptance criteria. Neither score rates the vendor. Buyer grounding checks literal/normalized buyer quotes or literal values; they do not prove that a model's paraphrase preserves every nuance.
- Exact-domain identification gates dependent vendor research. Changed briefs clear the current identity/findings; immutable report snapshots preserve earlier versions.
- Existing Crustdata search/fetch tools support targeted study of relevant vendor documentation and captured links. Local tools validate and save the claim map; they are application tools, not invented provider/MCP endpoints.
- Supported findings require a captured vendor-owned URL/artifact and matching passage. Snippets, fabricated passages, wrong domains and challenge/empty pages cannot establish support. Conflicting-document status requires distinct content, not duplicate copies. Passage-origin checks do not establish semantic entailment or independent verification.
- Reports include every recorded requirement, including uncovered ones, status, exact quotes, source provenance, missing evidence and proposed validation actions. Independent verification is always explicitly pending in this stage.
- Automatic local HTML/JSON snapshots and `latest.html`; `/report` and offline `--report`. HTML escapes source/buyer content, has no scripts or remote assets and uses a restrictive CSP. Proposed pilot actions are not executed.

## Actual live checks

The named company and brief below were a **synthetic validation scenario**, not an actual buyer assignment. Model reasoning and document retrieval were real, not mocked.

1. `vendor-review-validation`: a sparse request to review Crustdata triggered follow-up questions about purpose, must-haves and constraints. No paid research executed. Early argument-format failures were preserved in the logs; explicit nested provider schemas and normalized literal grounding corrected these issues.
2. `vendor-review-live`: saved the complete buyer brief, resolved company ID 6036032, fetched official Identify documentation and saved a vendor-documented R1 finding. Actual Crustdata cost **1.2 credits**. Follow-up attempts hit the durable token limit rather than replenishing it. A Windows console encoding error occurred after checkpointing; output handling was corrected, and offline report export recovered the saved dossier.
3. Clean `vendor-review-demo`: used the corrected schema/grounding path. Captured the buyer's Python lookup use case, must-have domain-to-company-ID requirement and literal pass criterion; geography India, Python REST integration, one domain per lookup, API key authentication, unknown budget and prototype timeline. Readiness and specificity both reached 100, with unknown budget still visible. Resolved the exact vendor, fetched **two distinct official vendor pages**, and saved R1 with three accepted passages from the Identify page. The general introduction is retained in the source dossier as studied context; it is not described as independent corroboration or as a second source proving the finding.

Sources actually fetched:

- [Company Identify introduction](https://docs.crustdata.com/company-docs/identify/introduction)
- [General API introduction](https://docs.crustdata.com/general/introduction)

The clean run spent **2.2 observed credits** (identify 0.2 + two fetches at 1 each), read from returned charge headers. It recorded `vendor_documented`, `independently_verified=false`, limitations, a request outline, expected response and pass conditions. Its report is `.local/reports/vendor-review-demo/latest.html`, with timestamped HTML/JSON companions. This is evidence that the workflow executes, not certification of the vendor's technical behavior.

The initial clean run saved findings but stopped before final prose when the original foundation context bound was exceeded. Research-mode Gemini context now allows a larger bounded window, and completed structured findings carry forward without replaying prior repair attempts/pages on the next turn. A separate-process follow-up successfully restored the dossier with no further paid research and exported HTML. Its freeform generated links were rejected by the existing citation-origin gate; the structured report remains sourced from accepted captures rather than that prose.

Across this milestone, actual Crustdata spend was **3.4 credits**, within a 4.5-credit validation allowance. Combined with the foundation's 4.6 credits, total observed implementation validation spend is **8.0 credits**. No wider customer/people graph was run. Model calls used Gemini 3.1 Flash-Lite, with reported token usage and configured free-tier rates recorded in the ledger; no invoice/billing-tier API verification is claimed.

## Tests and checks

**55 tests passed**, including the prior foundation suite and new tests for intake completeness/specificity, missing constraints, buyer grounding, brief invalidation, paid-call gating, an end-to-end deterministic research graph, exact quote/artifact checks, wrong-domain/snippet/challenge rejection, duplicate-source conflict rejection, nested schema conversion, HTML escaping/structure/CSP and file snapshots. These are explicitly synthetic model/HTTP fixtures and do not replace the live checks above. Ruff lint/format and `pip check` passed.

Browser visual inspection was blocked because the browser security policy prohibits `file:` URLs. No alternate surface/server workaround was attempted. HTML structure, required table columns, escaping and absence of executable elements were checked automatically; visual browser QA remains unverified. Existing Python 3.14 dependency deprecation warnings remain non-failing.

## Remaining boundaries

Customer-owned corroboration, professional evidence, full temporal/origin analysis and semantic source review remain required later stages. The model chooses passages from bounded excerpts; raw captures remain outside context, and truncated/inaccessible material is disclosed. A page retrieved today does not establish a recent event. Unknowns must remain unknown, and search failure is not a falsehood verdict. No fixed source-count quota defines evidence sufficiency. A complete set of table rows does not mean the underlying requirements are independently verified.
