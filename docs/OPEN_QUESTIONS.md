# Open questions and verification register

## Local foundation update — 2026-11-22

The implementation in `context-con` now uses version-pinned direct REST, not assumed connector credentials. Supplied local credentials authenticated successfully. Own prices/grants were read from the free account metadata routes; real identify/enrich/web-search/fetch calls and a native free-tier Gemini tool loop succeeded. Actual selected-route contract details and prices are in [CONTRACTS](build/CONTRACTS.md); measured results, failures, costs and remaining gaps are in [VALIDATION](build/VALIDATION.md).

This resolves local foundation authentication and selected REST schema/pricing gaps only. It does not resolve the historical people/social/batch/live/MCP conflicts below. The user requires free-tier Gemini and an optional local fallback, with no reliance on the small local model for research quality. `gemini-3.1-flash-lite` is the live-verified default; `gemini-3.8-flash` is documented as free-tier eligible but its attempted generation checks failed. API billing tier cannot be forced by a per-request free flag; no account/billing changes were made. No commit/push was performed, per the user's current instruction.

**2026-11-22 Idea C update:** subsequent bounded live probes are documented in [FarEye findings](../output/probes/fareye-20261122/REVIEWED_FINDINGS.md) and [project44 findings](../output/probes/project44-20261122/REVIEWED_FINDINGS.md). The original research-phase access/event assumptions below are historical. See [IDEA_C_ARCHITECTURE.md](IDEA_C_ARCHITECTURE.md) for the current proposal. Open issues from the second probe: connector HTML truncation and fallback parity; customer page-reader/direct-HTTP version conflicts; current SKU/business mapping; underlying security evidence; outcome methodology; full INR cost and buyer validation. The available data did not settle these questions.

As of **2026-11-19**. This register intentionally distinguishes a documented feature from a feature accessible to the eventual hackathon key. No authenticated data/account checks were made. The sole service-protocol probe was an unauthenticated MCP initialize request; it returned 401 and performed no tool/data operation.

## Highest-priority organizer questions

These are **questions to confirm**, not statements about ContextCon rules. No official event brief, judging rubric or organizer-provided entitlement sheet was supplied or verified.

| Priority | Question | Why it affects the project | Safe planning assumption |
| --- | --- | --- | --- |
| P0 | What credentials, credits, expiration and dollar/credit rates are provided? Is there a per-team/per-key monthly cap? | Establishes the real run budget and demo headroom | No credits available until confirmed; no paid calls during research |
| P0 | Which indexed, live, contact, batch, watch and beta endpoints are enabled? Which premium fields are included? | Contact/live/technology/verification can change feasibility | Core indexed path; optional features degrade gracefully |
| P0 | Can we obtain the authenticated MCP catalog/resources and tool schemas without running billable tools? | Needed for exact MCP integration and parity assessment | Public resource names only; no invented callable tool names |
| P0 | Are customer-facing derived reports, public demo profiles, saved fixtures and exported deliverables allowed under the event agreement? | Export docs restrict redistribution; a commercial service is not automatically allowed | Show minimal evidence and do not assume raw-data resale rights |
| P0 | Must the demo fetch live data during judging? Are indexed snapshots and labeled event replays acceptable? | Real job changes will not reliably occur within 12 hours | Label all cached/indexed/simulated evidence distinctly |
| P1 | What constitutes the business workflow being replaced, and what are the judging weights? | Determines whether research-only output or a downstream reviewed action is sufficient | Optimize a concrete useful deliverable |
| P1 | What is the exact build window, team limit and policy for prior code, existing official skills and LLM/framework costs? | Affects scope and differentiation | Treat 12 hours as the user's planning constraint, not a verified event rule |
| P1 | Is a demo tenant, supported sample dataset or nonbillable sandbox provided? | Enables meaningful validation without spending unpredictable credits | No sandbox assumed |
| P1 | Is technical support available for enabling fields or recovering a quota/rate issue during judging? | Gated features may otherwise block a demo | Keep an accessible fallback |

Official starting points for account/access questions: [permissions](https://docs.crustdata.com/general/permissions.md), [credits](https://docs.crustdata.com/general/credits.md), [pricing](https://docs.crustdata.com/general/pricing.md), [MCP](https://docs.crustdata.com/for-agents/mcp.md).

## Documentation conflicts that need explicit resolution

| ID | Conflicting or incomplete evidence | Consequence / resolution needed | Planning policy |
| --- | --- | --- | --- |
| D1 | [Person semantic guide](https://docs.crustdata.com/guides/person-semantic-search.md) documents search/mode/query_syntax; [person OpenAPI](https://docs.crustdata.com/api-reference/person-apis/search-people-using-filters-and-sorting.md) requires filters and excludes unlisted properties without modeling those beta keys | Obtain the actual semantic request schema/version and entitlement | Beta fields are guide-documented, not spec-validated; structured fallback |
| D2 | [Person identify guide](https://docs.crustdata.com/person-docs/identify/introduction.md) says synchronous `emails` accepts business/personal; [batch identify reference](https://docs.crustdata.com/api-reference/batch-apis/submit-a-batch-person-identify-reverse-email-lookup-job.md) says only batch resolves personal addresses | Confirm synchronous personal-email support and confidence/matching policy | Use batch as the documented common path for personal addresses if enabled |
| D3 | [Company identify guide](https://docs.crustdata.com/company-docs/identify/introduction.md) and [pricing](https://docs.crustdata.com/general/pricing.md) charge 0.2/match; [usage hide_free description](https://docs.crustdata.com/general/usage.md#events) and [batch job schema](https://docs.crustdata.com/api-reference/batch-apis/submit-a-batch-job-listings-search-job.md) call identify free | Clarify billing and dashboard/usage attribution | Budget 0.2; later account pricing/header wins |
| D4 | [Company search guide](https://docs.crustdata.com/company-docs/search/introduction.md) says omitted fields returns all; [operation description](https://docs.crustdata.com/api-reference/company-apis/search-companies-with-indexed-fields-only.md) says premium groups return when selected or granted free | Need default field set per account and its real price | Explicit field projection on every search |
| D5 | [Person enrich intro](https://docs.crustdata.com/person-docs/enrichment/introduction.md) and [batch enrich guide](https://docs.crustdata.com/person-docs/enrichment/batch-enrich.md) summarize max 4; [enrich reference](https://docs.crustdata.com/person-docs/enrichment/reference.md) adds social posts at +5, and [pricing](https://docs.crustdata.com/general/pricing.md) lists 1–9 | Summary excludes an add-on; confirm stacking and batch support | Budget components; do not use 4 as a universal maximum |
| D6 | [Company pricing summary](https://docs.crustdata.com/general/pricing.md) lists 2–4; [enrich reference](https://docs.crustdata.com/company-docs/enrichment/reference.md#social_posts-fields) documents gated +5 social posts | Confirm combined technographics/social pricing and grant | Base/technology/social costs tracked independently |
| D7 | [Freshness overview](https://docs.crustdata.com/general/data-updates.md) broadly gates live; [web search](https://docs.crustdata.com/web-docs/search/introduction.md) and [fetch](https://docs.crustdata.com/web-docs/fetch/introduction.md) explicitly support all plans | Avoid interpreting broad overview as a web restriction | Endpoint-specific access docs plus actual permissions |
| D8 | [Person search OpenAPI](https://docs.crustdata.com/api-reference/person-apis/search-people-using-filters-and-sorting.md) says return_query includes query; [reference](https://docs.crustdata.com/person-docs/search/reference.md) says flag is accepted but no top-level query appears | Debug output is not reliable schema | Do not parse a required query field |
| D9 | Company enrich guides show no-match 200/empty matches, while [reference/spec](https://docs.crustdata.com/company-docs/enrichment/reference.md#no-match-behavior) also defines 404 | Need resilient no-match handling | Handle both, never assume exceptions mean malformed input |
| D10 | [Job field reference](https://docs.crustdata.com/job-docs/search/reference.md) shows employment-type examples such as full_time; [cross-dataset watcher guide](https://docs.crustdata.com/watcher-docs/cross-dataset-filters.md#when-a-cross-dataset-condition-matches-nothing) warns stored value FULL_TIME | Exact value/casing and current enumeration unclear across sources | Use autocomplete/current documented enumeration and verify before saving a watch |
| D11 | [Person enrich reference](https://docs.crustdata.com/person-docs/enrichment/reference.md) mentions enrich_realtime incompatibility with preview, without a full stable public flag contract | Is this supported on current indexed enrich, or should live route be used? | No guessed flag body; use verified indexed schema |
| D12 | [Watch cross-dataset guide](https://docs.crustdata.com/watcher-docs/cross-dataset-filters.md#records-from-the-other-dataset) mentions the returned company-ID path in a follow-up job filter; [job reference](https://docs.crustdata.com/job-docs/search/reference.md#jobs-ids-a-quick-map) identifies company_id as the indexed alias | Returned and filterable paths are not safely interchangeable | Use the job field catalog's indexed alias and verify actual support |
| D13 | [Pricing](https://docs.crustdata.com/general/pricing.md) lists a company-search maps premium group; the [search field reference](https://docs.crustdata.com/company-docs/search/reference.md) and reviewed public response model do not establish its usable field schema | Which maps fields are actually available and selectable, under what grant? | Do not invent map-rating/address/phone JSON paths from the price-group name |
| D14 | [Company realtime watcher fields](https://docs.crustdata.com/watcher-docs/company/discovery.md#filter-fields-the-live-company-search-accepts) explicitly route funding-only realtime filters to the company index, despite broad realtime/live freshness descriptions | Confirm funding-source freshness and rationale for daily-tier billing | Preserve the documented indexed funding exception; no promise of web-time funding verification |

These conflicts do not invalidate the whole platform. They identify the exact contracts that need a later authenticated check or vendor response before code depends on them.

## Gated documentation and missing schemas

**Observed:** the following linked `.md` guides redirected to a Crustdata sign-in HTML page rather than returning public Markdown. A successful HTTP fetch of that HTML did not reveal the endpoint contract:

- [Live company search](https://docs.crustdata.com/company-docs/search/live-search.md)
- [Live people search](https://docs.crustdata.com/person-docs/search/live-search.md)
- [Live person enrichment](https://docs.crustdata.com/person-docs/enrichment/live-enrich.md)
- [Live company jobs](https://docs.crustdata.com/job-docs/search/live-search.md)
- [Live social keyword search](https://docs.crustdata.com/social-post-docs/search/introduction.md)
- [Live recent social posts](https://docs.crustdata.com/social-post-docs/enrichment/introduction.md)
- [Developer platform enrichment](https://docs.crustdata.com/person-docs/dev_platform/introduction.md)

Their paths/prices appear in [API introduction](https://docs.crustdata.com/openapi-specs/2025-11-01/introduction.md), [pricing](https://docs.crustdata.com/general/pricing.md) and [rate limits](https://docs.crustdata.com/general/rate-limits.md); exact direct-request and response schemas remain unverified. Watcher realtime filters do not establish the direct-live JSON format. The employee-review route lacks a dedicated public schema in the reviewed index. Do not fill these gaps from memory of old APIs.

The [public MCP page](https://docs.crustdata.com/for-agents/mcp.md#catalog-resources) identifies catalog/tools/fields/patterns/dry-run resources, but resource contents were unavailable without authentication. Confirm exact tool names, schema versions, helper signatures, input/result caps, dry-run side effects and parity with watchers/batches/Agent Search. No feedback/reporting tool call was sent. The official [skills repository](https://github.com/crustdata/skills) was visible publicly, but a GitHub tree request hit a public rate limit; individual skill implementations were not used as verified API schemas.

## Capability and operational unknowns

| Topic | What is documented | What remains unverified / next question |
| --- | --- | --- |
| Account grants | Free GET permissions lists enabled/disabled endpoints/fields and own prices | Actual event key, per-key restrictions, preview/beta grants; no account data was read. [Permissions](https://docs.crustdata.com/general/permissions.md) |
| Coverage and fill | Broad datasets and field groups | Country/industry/source completeness, missing role histories, domain/entity accuracy and contact fill for our target niche. No sample run measured it. [Capabilities](https://docs.crustdata.com/general/capabilities.md) |
| Freshness | Indexed refresh cadences and record timestamps | Source lag versus index rebuild lag, event-to-detection SLA and live retrieval failure rates; no latency/coverage guarantee established. [Data updates](https://docs.crustdata.com/general/data-updates.md) |
| Jobs | Rolling indexed postings, bounded dates, listing IDs | Immediate closed-job removal is explicitly not guaranteed; verify source coverage and repost treatment. [Lifecycle](https://docs.crustdata.com/job-docs/search/reference.md#dataset-freshness-and-lifecycle) |
| Social data | Searchable authors, reactors, comments, attachments | Completeness of engagement arrays, person-author field fill, current fix status of video/image/null issues. [Social reference](https://docs.crustdata.com/social-post-docs/indexed-search/reference.md#current-platform-behavior) |
| Email verification | Request-time business check and statuses | Catch-all deliverability, business/personal type classification, per-field billing on partial fills, actual latency. [Contact](https://docs.crustdata.com/person-docs/contact/enrich.md) |
| Work-history verification | Seven verdicts, citations and coverage | Accuracy by population, appeal/correction process, reproducibility and allowed use in hiring; no background-check assurance. [Verification](https://docs.crustdata.com/person-docs/verification/batch.md) |
| Technographics | Sources/confidence/evidence, 500-entry cap | Detection accuracy, pricing for zero results, coverage for chosen technologies, whether stack is deployed vs mentioned. [Technology guide](https://docs.crustdata.com/guides/technographics.md) |
| Watch eligibility | Field/dataset permissions checked; typed configs | Actual endpoint grants, active-watch count cap, per-account limits and price quote; management access is not assumed. [Watch create](https://docs.crustdata.com/api-reference/watch-apis/create-a-discovery-watch.md) |
| Watch delivery | Signature examples, inline chunks, five-day links/run summaries | Secret provisioning/rotation, retry schedule, acknowledgement timeout, ordering and delivery guarantee. [Person webhook test](https://docs.crustdata.com/watcher-docs/person/entity.md#smoke-test-your-webhook), [payloads](https://docs.crustdata.com/watcher-docs/payload-delivery.md) |
| Watch caps | Indexed 500k baseline; live people/company 10k; jobs/social no live creation count cap | How over-cap new matches are retained or deferred across runs; do not promise no dropped/deferred results without confirmation. [Person discovery](https://docs.crustdata.com/watcher-docs/person/discovery.md), [jobs](https://docs.crustdata.com/watcher-docs/job/watch.md) |
| Batch recovery | Job state, signed files, separate concurrency pools | General submission idempotency, cancellation, exactly-once billing, metadata endpoint RPM, long-term result retention and completion webhook signing. [Status](https://docs.crustdata.com/api-reference/batch-apis/get-the-status-and-download-urls-for-a-batch-job.md), [limits](https://docs.crustdata.com/general/rate-limits.md) |
| Agent Search | Beta endpoints, SSE, idempotency, variable final charge | Availability, predictable maximum spend, result pagination/size guarantees, retention, production SLA and contact-grant behavior. No max-cost body option is documented. [Agent Search](https://docs.crustdata.com/agent-search-docs/overview.md) |
| Autocomplete | Person/company 300 RPM; jobs guide 30; separate live vocabulary | Live autocomplete effective RPM and current per-key cap. [Rate table](https://docs.crustdata.com/general/rate-limits.md), [live schema](https://docs.crustdata.com/api-reference/person-apis/get-suggestions-for-live-search-filter-values.md) |
| Export | Dashboard only, roles, row/cadence limits, internal-use terms | Any separately contracted managed-export interface; no public export API should be inferred. [Export](https://docs.crustdata.com/export-docs/data-export.md) |
| Private business actions | Official skills describe drafting/research patterns | CRM writes, email sending, calendar actions, private connection graph, exact customer overlap and existing contracts require separate evidence/integrations. [Plugin skills](https://docs.crustdata.com/integrations/codex.md#skills) |

## Questions for commercial use

The [export docs](https://docs.crustdata.com/export-docs/data-export.md#terms) explicitly mention internal use and no resale/redistribution. The scope of the organization's API contract, derived-report permissions, client access, public demos, retention, deletion and public-profile display needs organizer/vendor confirmation. This review did not establish legal permissions or jurisdiction-specific obligations. The proposals are not authorization to sell raw records or reuse removed data.

No conversion from credits to money, guaranteed fill rate, event sponsorship entitlement or investment/hiring decision accuracy is assumed. Obtain actual terms and prices before assessing production margins.

## Later verification plan — not executed

1. Obtain the event brief and access/credit sheet; pick the project whose minimum feature set is enabled.
2. With explicit later authorization for account use, inspect free `/account/endpoints` and `/account/credits` and record actual field grants, effective RPM and prices. Free does not imply this research task used credentials.
3. Read authenticated MCP resources or obtain vendor schema exports; resolve D1–D14 before implementing dependent paths.
4. Validate saved example bodies against the exact current schemas without data retrieval where supported. Do not call a person-search preview expecting it to be free.
5. With a separately approved small credit budget, run a bounded representative sample; measure match accuracy, freshness, fill, latency and actual charge. Log field-level discrepancies rather than silently altering schemas.
6. Test partial/no-match/redacted/access-denied/insufficient-credit/rate-limit cases with fixtures before broad data retrieval. Label fixture and replay evidence in the demo.
7. Confirm data-use rights and the downstream action boundary before creating recurring watches or sending anything externally.

The user has authorized research/documentation only. This checklist records future work and does not authorize live API spending, framework installation or deployment.
