# project44 benchmark v1.1.0 (v1.0.0 preserved)

**v1.1.0** (`brief.json`, default) enables the read-only customer and professional branches: R3's stage becomes `customer_corroboration`, `research_branches` marks both branches enabled, and **G13** requires recorded coverage for both, scope-limited statements and explicit gaps. All R1–R8 questions, G1–G12 and missing buyer inputs are unchanged. **v1.0.0** is frozen byte-for-byte in `brief.v1.0.0.json` (`--benchmark-version 1.0.0`), with both branches deferred. Version-history fields are kept out of the model prompt. G11's wording is retained; under v1.1.0 it means a branch can be described as run only when its coverage was actually recorded.


Reusable synthetic benchmark recovered from the original project44 probe on 2026-11-22. It is not a real procurement brief, an autonomous success claim or a fixed current-facts answer key.

## Original questions retained

| ID | Question area | Coverage now |
| --- | --- | --- |
| R1 | Current project44/LSP44 product, SKU, contracting and buyer fit | Vendor research; resolve before fit conclusions |
| R2 (original C1) | Unified tracking API, modes, auth, webhooks, retries/idempotency and rate limits | Vendor research; runtime/lane coverage remains untested |
| R3 (original C2) | Girteka adoption, historical/current scope and comparable customer evidence | v1.1.0: customer corroboration branch (read-only); v1.0.0: pending |
| R4 (original C3) | AI agents, workflows, dated releases, entitlement, approvals and recovery | Vendor descriptions/releases now; execution verification pending |
| R5 (original C4) | 85% faster exception resolution: cohort, baseline and applicability | Vendor claim/methodology review; no assumed ROI |
| R6 (original C5) | SOC 2 Type II/ISO 27001 scope and underlying evidence | Listed assurances versus actually reviewed reports |
| R7 | Cloud/Kubernetes architecture and scope of infrastructure savings | Public-document research; external Cast AI testimony is a lead, not an audit |
| R8 | Hosting/AI subprocessors, data flows, regions, retention and training-use terms | Disclosure review, not model ownership or request-level proof |

The **12 canonical checks** in `brief.json` preserve identity/product boundaries, all five original claims, exact passages, retrieval conflicts, separate date types, origin deduplication, mode/version-specific technical rules, unresolved questions/pilot gates, missing buyer constraints, operation/cost limits, deferred branches and resistance to hardcoding historical findings.

Carrier mix, lanes, integrations/workload, actual product/SKU, security requirements, baseline/pass thresholds, commercial budget and timeline were never supplied by a real buyer. Keep asking for these or retain explicit uncertainty. Do not convert research questions into invented commercial must-haves. Customer/professional work stays in the complete benchmark even while adapters are pending. The current vendor-owned citation gate cannot admit a third-party Cast AI or customer page as independent vendor verification; surface that coverage gap rather than mislabelling the source.

## Files and leakage boundary

- `brief.json`: versioned model input, questions, checks, missing inputs and current/deferred scope.
- `reference.json`: separate historical reviewer expectations and legacy C1–C5 mapping. **Not loaded into agent prompts.** Old company IDs, findings, dates and prices are not fresh proof.
- Original reviewed record: [REVIEWED_FINDINGS.md](Z:/Projects/AI-Agent/output/probes/project44-20261122/REVIEWED_FINDINGS.md).
- Original structured assessment: [ASSESSMENT.json](Z:/Projects/AI-Agent/output/probes/project44-20261122/ASSESSMENT.json).

Raw captures, account balances and historical operational payloads were not copied into this benchmark. Historical source URLs in `reference.json` identify what the earlier reviewer used; they do not establish current availability or correctness. Live checks should follow the actually retrieved version. Frozen replay checks can separately test historical exact rules (for example webhook HTTP 500), without hardcoding them as universal current vendor behavior.

## Commands

```powershell
# Model confirms scope only: tool definitions disabled, zero Crustdata calls.
.\.venv\Scripts\vendor-review --benchmark project44 --confirm-only
# Begin interactive intake from the canonical benchmark; does not load reference answers.
.\.venv\Scripts\vendor-review --benchmark project44 --thread project44-benchmark
# Resume that conversation normally.
.\.venv\Scripts\vendor-review --thread project44-benchmark
```

Confirmation uses the configured free-tier Gemini model, model/token/deadline limits, ledger and checkpoints. Every R/G ID and scope stage must be present, and canonical checks must be preserved exactly. The output is saved under `.local/benchmarks/project44/*-confirmation.json`. This checks acknowledgement/coverage, not evidence correctness or successful research. Use a fresh confirmation thread; the default creates one automatically. A research run still needs a finite explicit allowance and actual buyer inputs/uncertainty decisions; no full project44 data-gathering run was initiated by establishing this benchmark.
