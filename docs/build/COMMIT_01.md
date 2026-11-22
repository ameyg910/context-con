# Commit 01 — interactive LangGraph agent with real Crustdata tools

## Deliverable

A developer can start a local chat, ask about a real company, observe validated Crustdata tool activity, receive a grounded answer, ask a follow-up in the same thread and resume that conversation after restarting. This is the runnable research foundation, **not the completed vendor-assessment product**.

Implement in the next chat. This turn prepared documents only. Local framework/dependency installation and implementation are now authorized by the user for this milestone. No deployment, account creation, external messages, recurring watches or unbounded paid runs.

## Implementation sequence

1. Inspect repository status and existing files. Create an isolated application package such as src/vendor_review, preserving historical probes.
2. Set up minimal Python dependencies for LangGraph, chosen provider, HTTP/configuration/validation and durable local checkpoints. Pin tested versions; do not install unrelated frameworks.
3. Configure secrets securely. Proposed local names such as CRUSTDATA_API_KEY and model-provider variables are application configuration, not claims about existing environment contents. Provide a secret-free .env.example and ignore real secrets, runtime captures and checkpoint databases.
4. Implement the model/tools conditional LangGraph loop from LANGGRAPH_ARCHITECTURE.md, local CLI, stable thread ID, new-session/exit controls, tool progress and final responses.
5. Implement typed, allowlisted Crustdata tools with validated inputs and compact results. Verify official exact requests and prices before coding.
6. Persist conversation and operation/evidence/cost records. Enforce finite per-turn and cumulative session limits.
7. Add meaningful deterministic checks and run a bounded real smoke test with configured credentials. Distinguish mock validation from live success.
8. Document exact setup/run/resume commands based on the actual implementation, all limitations and smoke-test costs.
9. Review staged files, exclude secrets/runtime payloads, and create the requested first implementation commit in the correct repository. Do not push remotely.

## Initial tools

Required foundation: account credit/access metadata plus company identify, selected company enrichment, web search and public-page fetch. These cover a complete first conversational lookup. Keep adapters extensible for indexed people search/enrichment and indexed social-post search in the next increment. Do not implement every Crustdata family before making chat work.

Sources:
- [Account access](https://docs.crustdata.com/general/permissions.md), [credits](https://docs.crustdata.com/general/credits.md).
- [Company identify](https://docs.crustdata.com/company-docs/identify/introduction.md), [enrichment](https://docs.crustdata.com/company-docs/enrichment/reference.md).
- [Web search](https://docs.crustdata.com/web-docs/search/reference.md), [fetch](https://docs.crustdata.com/web-docs/fetch/introduction.md).

Use documented bearer authentication and verify version header (research snapshot: x-api-version 2025-11-01). Actual account grants supersede generic prices/rates. Avoid guessing from connector names or older API variants.

## Acceptance

- One documented local command starts interactive chat.
- A genuine LangGraph model/tool loop executes real API requests; no hardcoded company answers.
- At least two conversational turns preserve the selected company/context.
- A bounded real query returns source URLs or API artifact/field provenance; failures are explained.
- Restart with the same thread retains prior conversation; new thread remains separate.
- Tool activity, actual returned credit charges, failures and remaining budget are inspectable.
- Model/tool loops stop at limits; a lowered cumulative limit cannot be bypassed by another turn.
- Schema/permission failure is not retried indefinitely; secrets are redacted.
- Fresh clone setup is documented. No dashboard is required.
- Commit reports exact checks performed, observed live cost and remaining gaps. If credentials block a live check, say so; do not report it as passed or fabricate a result.

## Suggested commit message

feat: add interactive LangGraph agent with bounded Crustdata tools

## Important access observation

The assistant connector previously accessed indexed company/people/social and web tools. Live professional-network retrieval, contact enrichment, technographics and batch verification were disabled. These are dated observations, not guaranteed current grants. Do not depend on them. The local API credential/model provider setup remains to be verified.

## Scope of paid validation

Use a small explicit smoke-test allowance (proposed initial Crustdata ceiling: 10 credits, configurable and cumulative). Also cap model tokens/calls and time; record monetary costs when authoritative prices are known. Do not run broad searches or use the entire account balance. Check permissions first and stop on configuration/authorization failures.
