# Agent architecture choices for ContextCon

**2026-11-22 addendum:** for the selected Idea C workflow and subsequent real-data findings, read [IDEA_C_ARCHITECTURE.md](IDEA_C_ARCHITECTURE.md) and the [project44 reviewed probe](../output/probes/project44-20261122/REVIEWED_FINDINGS.md). The comparison below is the original research snapshot; later authorization and observed connector behavior are described in those newer references.

Research date: **2026-11-19**. This is a design comparison, not an installation or implementation plan already executed. Crustdata contracts come from its official docs; architectural recommendations below are our engineering judgments.

## Separate data access from orchestration

Direct REST and MCP are **access mechanisms**. Tool calling, state machines, LangGraph and multi-agent systems organize the work. They can be combined: a state machine can expose REST-backed tools to one model, and a LangGraph node can call MCP. Crustdata's own Agent Search is a separate hosted research API, not a synonym for our agent architecture. [REST contract](https://docs.crustdata.com/openapi-specs/2025-11-01/introduction.md), [MCP](https://docs.crustdata.com/for-agents/mcp.md), [Agent Search](https://docs.crustdata.com/agent-search-docs/overview.md)

## Comparison

| Approach | Strength | Main cost or risk | Best workflow fit | 12-hour judgment |
| --- | --- | --- | --- | --- |
| Direct API calls | Explicit schemas, result caps, prices and error handling; easy to inspect exact requests | Must write/validate request adapters and pagination; live schemas are gated | All bounded company/person/job workflows; CRM audits | Strong default for predictable paths |
| Crustdata MCP | Existing search/enrich composition and catalog guidance; interactive authentication; fewer custom adapters | Exact tools/resources need authenticated discovery; client behavior, projections and credit handling must be verified | Interactive research, account/expert/partner briefs | Fast if access is working at the start; avoid making unknown tools critical |
| One model with simple tool calling | Converts a user brief to a small selection of typed operations and synthesizes a report | Loops, broad searches, invented fields, duplicate enrichment or unsupported claims | Inbound prep, competitor briefs, a small sourcing request | Good when calls and result volume are tightly bounded |
| Explicit state machine plus focused model steps | Deterministic order, visible failure recovery, spending gates and review states | Some manual control-flow work; persistence must be designed | Staffing packets, CRM correction, event-to-expansion briefs | Recommended for the top projects |
| LangGraph | Shared state, explicit nodes/edges, persistence, streaming and human interrupts | Framework learning/setup and checkpoint design can consume the event; not automatic dedupe or free retries | Long-running batches, watcher processing, resumable research | Use only if the team already knows it or durable branching is essential |
| Multiple specialized agents | Independent research contexts and bounded parallel work; specialist review can focus on evidence | Duplicate data spending, inconsistent identities, larger prompts and failure coordination | Larger competitive/market research with genuinely independent branches | Usually excessive for five-account demos; defer until single-agent evidence quality is measured |

Crustdata capabilities supporting the first two rows: [API guides](https://docs.crustdata.com/llms.txt), [MCP catalog resources](https://docs.crustdata.com/for-agents/mcp.md#catalog-resources). LangGraph's documented stateful orchestration, persistence and interrupt capabilities: [official LangGraph overview](https://docs.langchain.com/oss/python/langgraph/overview). Multi-agent context separation, routing and subagent patterns: [official LangChain multi-agent documentation](https://docs.langchain.com/oss/python/langchain/multi-agent). The workflow fit and effort judgments are ours, not vendor performance claims.

## Recommended minimal architecture

A small application controller should own the state and spending policy. The model interprets the brief, evaluates evidence and writes the deliverable; deterministic code validates filters, chooses exact endpoint contracts, caps pages, reconciles IDs and handles failures. This is a proposal for later implementation.

1. **Accept and constrain.** Capture buyer intent, mandatory criteria, geography, exclusions and maximum result volume.
2. **Check access.** Read account permissions/prices and credit balance when a later task authorizes account use. Select an accessible variant, rather than repeatedly trying a gated endpoint.
3. **Plan.** Produce an internal operation plan referencing known endpoint adapters; reject unknown field paths before a request.
4. **Discover.** Search with explicit fields and a small cap; preserve cursor/query fingerprints.
5. **Resolve.** Normalize identities and choose exact matches, leaving ambiguous entities for review.
6. **Enrich.** Fetch detail for selected entities only, cache by identity/version/fields/freshness policy.
7. **Corroborate.** Search/fetch a bounded set of public evidence; attach source and timestamp to facts.
8. **Synthesize.** Generate a structured client deliverable; missing data becomes unknown, not an invented fact.
9. **Review or finish.** Show deliverable, source trail, credit summary and any proposed external actions.

Account checks, billing and stable query requirements come from [permissions](https://docs.crustdata.com/general/permissions.md), [credits](https://docs.crustdata.com/general/credits.md), [best practices](https://docs.crustdata.com/openapi-specs/2025-11-01/best-practices.md), and the [company pagination contract](https://docs.crustdata.com/company-docs/search/reference.md). No checks were executed in this research task.

## Proposed state and tool boundaries

This table is an **application-owned design**, not Crustdata JSON fields or MCP tool names.

| State / record | What it stores | Purpose |
| --- | --- | --- |
| Research brief | Client criteria, exclusions, hard/soft rules, output format | Keep scope stable |
| Operation ledger | Endpoint/version, normalized parameters, status, request ID, batch/search IDs | Recover without blindly resubmitting work |
| Budget ledger | Allowed records, estimated charge, actual charge, reserved async work | Bound spending across the whole run |
| Identity map | Local client ID, Crustdata ID, domain/profile URL, match type/confidence | Avoid cross-company/person contamination |
| Evidence records | Source URL, relevant text/fact, source/refresh/retrieval dates and caveats | Support claim-level citations |
| Work queue | Bounded selected entities, pagination checkpoints and retries | Resume partial work |
| Deliverable | Observations, inferences, missing data, next actions | Keep recommendation separate from fact |

Potential model-facing operations should be few and constrained, such as “find indexed jobs for these criteria” or “enrich these selected company IDs.” These are conceptual wrappers. Do not name them as real MCP tools until `tools/list` and catalog resources establish the exact names/input schemas. [MCP discovery guidance](https://docs.crustdata.com/for-agents/mcp.md#catalog-resources)

## Direct REST design

Use endpoint-specific adapters for search/company/person/contact/jobs/social/web, not one universal JSON forwarder. Validate the known request allowlists and keep output transformations separate from provider response objects. A required field in one family may be invalid in another: synchronous identify uses `emails`; contact lookup uses `business_emails`; batch jobs use distinct controls. [Person identify](https://docs.crustdata.com/person-docs/identify/introduction.md), [contact](https://docs.crustdata.com/person-docs/contact/enrich.md), [batch search](https://docs.crustdata.com/company-docs/search/batch-search.md)

Maintain one paced queue per effective rate budget and two batch concurrency pools. A model should not independently retry 402/403 or treat unsupported-field 500s as transient outages. Retry only known retryable failures and cap attempts. Do not assume all POSTs support idempotency headers; Agent Search explicitly does, while general search/enrichment/batch writes need their own safe reconciliation policy. [Rate limits](https://docs.crustdata.com/general/rate-limits.md), [errors](https://docs.crustdata.com/openapi-specs/2025-11-01/best-practices.md), [Agent Search idempotency](https://docs.crustdata.com/agent-search-docs/overview.md#repeat-a-start-safely)

## MCP design and verified catalog limits

The public server guide describes this sequence: read `crustdata://catalog`, load tools/fields/query-builder, compose script calls, use result shaping and bounded pagination, then validate via the documented dry-run resource. It names `project`, `compact`, `paginate`, and `parallelMap` as result helpers. Their signatures were not available without authentication. [MCP guide](https://docs.crustdata.com/for-agents/mcp.md)

Before a future implementation depends on MCP, inspect:

- Actual callable tools and input/output schemas, and which are visible under the hackathon account.
- Which operations a dry run validates and whether it ever performs retrieval; the public guide describes zero-credit testing, not all its semantics.
- Mapping between helper limits and actual backend pagination/cost, especially parallel calls and large outputs.
- Error, cancellation, timeout, batch-job and watcher support; parity with REST is not established by the public catalog index.

Official plugin patterns already include search→enrich, identity→enrich, bulk processing and account/candidate/meeting/outreach work. They accelerate a demonstration but don't differentiate a generic agent. Plugin email-drafting recipes require a separate Gmail integration, and warm-path recipes are not proof of private-graph access. [Plugin skill catalog](https://docs.crustdata.com/integrations/codex.md#skills)

## When simple tool calling is enough

For W5 inbound briefs, expose a bounded company lookup, selected enrichment and public evidence retrieval. The model can make a few choices and write a brief while a controller owns limits. For W7 competitor research or W10 partners, a fixed input list often makes a deterministic loop simpler than autonomous planning.

Proposal: start with 3–5 records, an explicit field projection and a maximum number of evidence pages. If the model reaches a limit, return a useful partial deliverable and explain what remains. A structured tool schema does not prove the model's chosen company, field or inference is correct; validate all three.

## When a state machine is preferable

W1 staffing and W2 modernization naturally have discover→select→enrich→corroborate→deliver stages. W3 champion tracking adds receive-event→authenticate/dedupe→diff→research→review. W8 CRM audit adds validate-input→resolve→propose-corrections→human-review. Each benefits from a visible incomplete/partial/access-denied state.

For watchers, maintain notification/run IDs and an event inbox. Ignore free baseline/test samples when generating actionable “changed” tasks. Acknowledge receipt independently from slow research; exact retry/ack policy still needs vendor confirmation. Expired links can be refreshed through run summaries. [Person baseline/test behavior](https://docs.crustdata.com/watcher-docs/person/entity.md), [payload and chunking](https://docs.crustdata.com/watcher-docs/payload-delivery.md)

## LangGraph adoption threshold

LangGraph is appropriate if the demo requires persisted pause/resume, a review interruption, multiple conditional research branches or recovering a long batch. A graph can represent the stages above and checkpoint operation IDs so a restarted node doesn't create duplicate jobs. Its persistence is not an automatic provider idempotency guarantee. [Official overview](https://docs.langchain.com/oss/python/langgraph/overview)

For a team learning it during a 12-hour event, a plain state enum plus persisted run records is likely faster. That is a judgment about this event's scope, not a benchmark. No framework was installed.

## Multi-agent adoption threshold

Useful later pattern: one coordinator resolves identities and allocates a shared budget, then bounded workers research independent accounts; one reviewer checks factual support. Workers share the identity/evidence ledger and cannot enrich the same record independently without reconciliation. Specialized contexts can help a large W6/W7 market scan, but five-account research usually needs ordinary concurrent API requests rather than multiple autonomous model loops.

Avoid “sales agent + recruiter agent + research agent” solely for presentation. Measure whether a second agent improves source accuracy or coverage enough to justify extra calls and latency. [Official multi-agent patterns](https://docs.langchain.com/oss/python/langchain/multi-agent)

## Hosted Agent Search alternative

Agent Search accepts a natural-language query, searches person/company/job datasets and returns constraint evidence. It can replace a portion of discovery planning, but it cannot be assumed to produce a fixed deliverable schema or respect an undocumented spending ceiling. It requires all three dataset-search permissions and the beta grant. A final read or completed SSE stream can charge; store its search ID and idempotency key. [Agent Search](https://docs.crustdata.com/agent-search-docs/overview.md)

Best proposed fit: W4 complex shortlist or W6 thesis discovery when constraints are difficult to express. Prefer direct search for known precise filters, for lower and more predictable data costs. Do not make a beta hosted agent the only route to the hackathon demo.

## Recommended architecture by workflow

| Workflow | First version | Later reason to add orchestration |
| --- | --- | --- |
| W1 Staffing leads | Direct indexed jobs/company/person APIs, state machine, one model | Resume recurring batches and review exceptions |
| W2 Modernization | Direct technology/job APIs, state machine | Parallel account research with shared budget |
| W3 Champion expansion | Event/replay inbox plus explicit state machine | Durable watcher processing and approval pauses |
| W4 Recruiter shortlist | One model with constrained search/enrich tools | Multiple role-specific branches or verification jobs |
| W5 Inbound brief | Simple tool calling or existing MCP composition | SLA queues and CRM review integration |
| W6 Investment research | Fixed research stages, bounded optional Agent Search | Larger independent sector/company branches |
| W7 Competitive intelligence | Fixed entity loop with evidence extraction | Scheduled comparisons and specialist review |
| W8 CRM audit | Deterministic identity pipeline plus exception reviewer | Batch recovery, change approval and rollback |
| W9 Expert sourcing | Small tool-calling researcher with identity checks | Multiple publication/topic branches |
| W10 Partners | Bounded company search and evidence scoring | Team review and recurring territory research |

All assignments are proposals. The common requirement is a reviewable service output and a source trail; the number of agents is not the product's value.
