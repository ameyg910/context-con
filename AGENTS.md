# Project instructions

This project is building Idea C, **Technical Vendor Evidence Review**, for ContextCon. On 2026-11-22 the user authorized actual local implementation with **LangGraph**, beginning in a new chat with an interactive conversational agent and bounded real Crustdata API calls as the first implementation commit. Minimal required framework/dependency setup, local tests and limited live validation are within that scope. This supersedes the earlier research-only boundary. Deployment, accounts, external messages, recurring watches, remote pushes and unlimited spending remain outside scope.

## Read these references first

1. `docs/build/START_HERE.md` — self-contained handoff, selected decisions and new-chat prompt.
2. `docs/build/PRODUCT.md` and `docs/build/WORKFLOW.md` — selected idea/features and comprehensive evidence workflow with adaptive depth.
3. `docs/build/LANGGRAPH_ARCHITECTURE.md` and `docs/build/COMMIT_01.md` — required foundation architecture and immediate implementation task.
4. `docs/build/ACCEPTANCE.md` — staged checks and event constraints.

The build pack is authoritative for current scope. Sales/expert-sourcing pivots and legal-clearance scope were not selected. Do not weaken customer/professional evidence gathering to satisfy arbitrary collection quotas; keep output concise while retaining the dossier. The following references are supporting research snapshots:

- `docs/CRUSTDATA_CAPABILITIES.md` — platform/data map and public MCP catalog index.
- `docs/API_REFERENCE.md` — endpoints, request examples, prices and caveats.
- `docs/BUSINESS_WORKFLOWS.md` — ten proposed services and deliverables.
- `docs/AGENT_ARCHITECTURES.md` — access/orchestration choices.
- `docs/HACKATHON_IDEAS.md` — five ranked 12-hour proposals.
- `docs/OPEN_QUESTIONS.md` — access gaps, schema conflicts and organizer questions.

## Evidence and API rules

1. Start with https://docs.crustdata.com/llms.txt and linked official guides/OpenAPI. References were reviewed on 2026-11-19 and can drift; verify the owning source before implementation.
2. **Never invent endpoints, HTTP methods, JSON fields, enum values, prices or MCP tool names.** Verify exact request/response schemas, field permissions and pagination for the selected API version. Indexed/live/batch/MCP formats are not interchangeable.
3. Keep documented features, observed results, proposals and unverified assumptions distinct. Cite the official source URL for material capability/contract claims. Record conflicts in OPEN_QUESTIONS instead of silently guessing.
4. Pin the documented `x-api-version` (currently `2025-11-01`) and bearer authentication when later API use is authorized. Actual account permissions/prices/rate limits take precedence over general list defaults.
5. MCP resource names in the research are documented, but exact authenticated tool schemas were not retrieved. Read `crustdata://catalog` and the live tools/fields/cost/patterns resources before depending on them.

## Current action boundary

- The user has now authorized required local framework installation and bounded paid API validation for implementation. Use finite configurable limits, access checks and a per-call ledger; COMMIT_01.md proposes a 10-credit initial Crustdata smoke-test ceiling. Broader investigation needs its own configured allowance. Do not spend the account balance or create accounts, deploy infrastructure or create recurring watches.
- This chat's connector credentials are not automatically available to the local application. Verify secure local Crustdata/model configuration; never print tokens, dump environment contents or commit secrets. Model provider remains configurable; do not default to the rejected small-model setup.
- Preserve historical probes. They do not implement the new agent. Preparing the handoff did not create an application or Git commit. In the implementation chat, inspect the actual repo, implement and validate the foundation, then create the requested first implementation commit. Never bulk-commit secrets or raw captures and do not push remotely without authorization.
- Metadata/account checks documented as free still require proper authorization and credentials; no authenticated checks were performed in the research phase.
- Agent Search final GET/stream reads can charge. Person search preview is gated and must not be assumed free. Watch samples/replays are not actual changes.
- Preserve secrets and intentional redactions. Future research results must show evidence and freshness; don't infer private relationship graphs, buying intent, live vacancies or guaranteed email delivery.
- Sending messages or writing to external business systems needs user authorization. Crustdata data access alone does not provide CRM, email or calendar actions.
