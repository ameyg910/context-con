# Model scope confirmation — 2026-11-22

- Benchmark: project44 v1.0.0.
- Canonical input SHA-256: `ccad7ba4171e847d968bc0fd8782a82df5d2cf6a7048bae815eedaf660086185`.
- Configured model: `gemini-3.1-flash-lite` (documented free-tier Gemini path).
- Outcome: actual model acknowledgement received; all 8 question IDs and 12 check IDs present, stages retained, canonical check instructions preserved verbatim.
- Model acknowledged missing buyer constraints, distinction between attributed vendor claims and independent verification, deferred customer/professional work, and no vendor approval/security verdict.
- Final confirmation: one model call, 2978 reported tokens, zero tool calls, zero observed Crustdata credits. An earlier short acknowledgement was refined to prevent loss of check details; its raw record remains local. No research acquisition or vendor API test ran in this task.
- Canonical checks explicitly allow later bounded live read-only Crustdata research. The confirmation-only mode disables research tools; that boundary does not prohibit live acquisition in subsequent benchmark runs.
- Raw local final acknowledgement: `.local/benchmarks/project44/project44-confirm-6a985b0f-confirmation.json`; persisted thread `project44-confirm-6a985b0f`. It is ignored runtime data, not a committed credential/capture bundle.

This records agreement about task scope, not evidence truth or an end-to-end benchmark pass. Full project44 data gathering, report quality, semantic support, timing/cost and later corroboration branches remain to be evaluated. Historical answers in reference.json were not included in the prompt.

Verification: 61 deterministic tests passed, including benchmark coverage/stage checks, reference-answer exclusion and confirmation without research dispatch. Ruff lint/format and dependency checks passed. No commit/push/deployment/outreach/account/watch was performed.
