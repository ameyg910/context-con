# Five ranked ContextCon projects

Research date: **2026-11-19**. Ranking is our **proposal**, based on service usefulness and documented Crustdata capabilities, not interviews, revenue data, event judging criteria or confirmed account entitlements. Feasibility assumes a small team, one buyer segment, one main flow, existing access to an LLM, and a strict 12-hour implementation window. No implementation has started.

## Ranking method

Score 1–5, higher better. Weights: commercial value 30%, Crustdata advantage 25%, differentiation 15%, demo potential 15%, 12-hour feasibility 15%. Commercial value means a plausible paid service task; Crustdata advantage means the platform contributes difficult-to-assemble identity/firmographic/work-history/job evidence. Differentiation is judged against the [official plugin's existing workflows](https://docs.crustdata.com/integrations/codex.md#skills), not a claim of competitor-market uniqueness.

| Rank | Project / buyer | Commercial | Crustdata advantage | Differentiation | Demo | Feasibility | Weighted / 5 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | **Staffing Demand Desk** — niche staffing agencies | 5 | 5 | 4 | 5 | 5 | **4.85** |
| 2 | **Modernization Opportunity Analyst** — specialist consultancies | 5 | 5 | 5 | 5 | 3 | **4.70** |
| 3 | **Champion Expansion Desk** — B2B account teams | 5 | 5 | 4 | 5 | 3 | **4.55** |
| 4 | **Recruiter Evidence Pack** — specialist recruiters | 5 | 4 | 3 | 5 | 4 | **4.30** |
| 5 | **Inbound Brief Desk** — small sales teams | 4 | 4 | 2 | 5 | 5 | **4.00** |

High commercial scores do not imply higher realized willingness to pay. Access can reorder the table: without technographics, #2 loses its central advantage; without usable role histories, #3/#4 weaken. #5 is a strong fallback despite lower differentiation.

## 1. Staffing Demand Desk

**Service being replaced:** a staffing researcher's job-board scanning, employer qualification, hiring-leader lookup and first-touch preparation. Related workflow: [W1](BUSINESS_WORKFLOWS.md#w1-staffing-agency-business-development-researcher).

**Demo promise:** “Give me your recruiting specialty and region; receive five companies with relevant hiring evidence, likely hiring leaders, and a specific approach.” The central object is an employer packet, not a chat transcript.

**Likely APIs:** `POST /job/search` for recent relevant postings and employer aggregations; `/company/enrich` for account context; `/person/search` and optionally `/person/enrich` for hiring leaders; `/web/search/live` and `/web/enrich/live` for corroboration. Optional `/person/contact/enrich` and `/watch/job/search` come later. [Jobs](https://docs.crustdata.com/job-docs/search/introduction.md), [company enrich](https://docs.crustdata.com/company-docs/enrichment/introduction.md), [people](https://docs.crustdata.com/person-docs/search/introduction.md), [web](https://docs.crustdata.com/web-docs/search/reference.md)

**Crustdata advantage:** jobs already include employer firmographics and identifiers, reducing entity joins; person data supplies likely hiring leaders. **Differentiation proposal:** specialize in one niche, such as data engineering staffing, with a buyer-ready evidence pack and transparent demand score.

**12-hour scope:** 30–100 indexed job rows, five companies, 1–2 leaders each, one-page packet per company, CSV/Markdown export. One direct-API state machine with a single synthesis step. No CRM write or send operation needed.

**Credit planning:** 100 returned jobs = 3 list-price credits; five base company enrichments = 10; selected people search/enrich and up to a few public pages add costs. People filters/returned experience can raise search cost. This is an illustrative component budget, not a total quote. [Job price](https://docs.crustdata.com/job-docs/search/introduction.md), [enrich price](https://docs.crustdata.com/company-docs/enrichment/introduction.md), [premium pricing](https://docs.crustdata.com/general/pricing.md)

**Demo sequence:** specialty brief → precise query explanation → employer ranking → open one packet → show job links, leader evidence and tailored pitch → change a client constraint and show why the ranking changes.

**Unresolved risks:** stale/closed postings, duplicate/reposted jobs, no documented guaranteed ATS coverage, missing leadership records, and contact grants. **Fallback:** role/profile URLs and dated indexed job evidence; omit contacts. **Success criterion proposal:** five packets whose reason-to-approach is supported by a specific relevant posting and a correctly resolved company. [Job lifecycle](https://docs.crustdata.com/job-docs/search/reference.md#dataset-freshness-and-lifecycle)

## 2. Modernization Opportunity Analyst

**Service being replaced:** technical sales research for a cloud/data consultancy. Related workflow: [W2](BUSINESS_WORKFLOWS.md#w2-technology-modernization-opportunity-analyst).

**Demo promise:** “Find companies suited to our narrowly defined integration/migration service; explain the technical signal, likely buyer and questions needed to qualify the opportunity.”

**Likely APIs:** `/company/search/autocomplete` for technology names; `/company/search` with technology and company filters; `/company/enrich` requesting technographics; `/job/search` for complementary demand; `/person/search` for leaders; public web search/fetch for corroboration. [Technology guide](https://docs.crustdata.com/guides/technographics.md), [search](https://docs.crustdata.com/company-docs/search/reference.md), [enrich evidence](https://docs.crustdata.com/company-docs/enrichment/reference.md#technographics-fields), [jobs](https://docs.crustdata.com/job-docs/search/reference.md)

**Crustdata advantage:** company technology signals, job-derived evidence and buyer identity can be assembled in one research pipeline. **Differentiation proposal:** sell one concrete service wedge, with explicit evidence grades and disqualifiers; avoid an unsupported “their stack is broken” claim.

**12-hour scope:** one service, one or two target technology signals, five accounts, a qualification matrix and a proposed discovery agenda. Use an explicit discovery→evidence→buyer→brief flow. No autonomous technical audit or actual infrastructure change.

**Credit planning:** a technology filter adds 1 per returned company above the 0.03 base, plus any other premium groups. Five company enrichments with populated technographics cost 20 at the 2+2 list price; search, people and web are additional. Company search itself never returns the stack. [Technology pricing](https://docs.crustdata.com/guides/technographics.md), [premium schedule](https://docs.crustdata.com/general/pricing.md)

**Demo sequence:** choose service profile → technology-based shortlist → inspect detection evidence → cross-check a job description → identify leader → generate a brief that clearly labels facts versus migration hypothesis.

**Unresolved risks:** field grant, source sparsity and signal interpretation; a job requirement does not prove deployment. **Fallback:** job-description-based technical demand, clearly labeled, with a reduced project promise. **Success criterion proposal:** every opportunity contains at least one technology or hiring source, a commercial fit explanation and an explicit missing qualification question.

## 3. Champion Expansion Desk

**Service being replaced:** customer-success research that notices a relationship move and prepares an expansion or replacement plan. Related workflow: [W3](BUSINESS_WORKFLOWS.md#w3-customer-champion-movement-and-expansion-researcher).

**Demo promise:** “A known champion moved; here is the new account context, the likely opportunity, the people to understand next and a relationship-aware task draft.” The client must supply relationship history.

**Likely APIs:** `/person/enrich` for current roles, optional `/watch/person` for future changes; `/company/enrich` for old/new employer context; `/person/search` for replacement roles; optional web sources and contact retrieval. [Person enrich](https://docs.crustdata.com/person-docs/enrichment/reference.md), [entity watcher](https://docs.crustdata.com/watcher-docs/person/entity.md), [company enrich](https://docs.crustdata.com/company-docs/enrichment/reference.md)

**Crustdata advantage:** employment history and entity diffs connect a specific relationship to a new account. **Differentiation proposal:** prioritize expansion relevance and owner-ready tasks, not just job-change alerts.

**12-hour scope:** three client-approved/synthetic relationship entries, two labeled profile snapshots or a labeled replay event, one generated expansion brief. A visible event inbox and state machine are more useful than a multi-agent display. Do not wait for a real job change during the event.

**Credit planning:** selective profile/company enrichment provides a predictable research budget. At published watcher tiers, five changed people cost 25 credits with 30-day freshness versus 750 with daily freshness, excluding downstream research. No-change runs and the initial baseline are free. [Watcher tiers](https://docs.crustdata.com/watcher-docs/person/entity.md#data-freshness)

**Demo sequence:** show prior relationship → receive labeled replay/change → inspect diff and source dates → show new company fit and replacement candidates → produce an account-owner task draft.

**Unresolved risks:** baseline samples are not real changes; freshness versus schedule confusion; multiple concurrent jobs; private CRM inputs and watcher permissions. **Fallback:** on-demand comparison using user-provided prior snapshots, with no recurring watch. **Success criterion proposal:** no expansion claim without client relationship context and correctly matched employment evidence.

## 4. Recruiter Evidence Pack

**Service being replaced:** first-pass specialist candidate sourcing and manual qualification notes. Related workflow: [W4](BUSINESS_WORKFLOWS.md#w4-specialist-recruiter-shortlist-and-evidence-pack).

**Demo promise:** “Turn one difficult role into a shortlist with a requirement-by-requirement evidence matrix, gaps and screening questions.”

**Likely APIs:** `/person/search` structured or semantic beta, `/person/search/autocomplete`, `/person/enrich`; optional developer/research profile groups, `/batch/person/verify` and contact enrichment. [Semantic people search](https://docs.crustdata.com/guides/person-semantic-search.md), [fields](https://docs.crustdata.com/person-docs/search/reference.md), [enrich](https://docs.crustdata.com/person-docs/enrichment/reference.md), [verification](https://docs.crustdata.com/person-docs/verification/batch.md)

**Crustdata advantage:** longitudinal roles, title normalization, developer/research evidence and identity match context support richer assessment than a generated biography. **Differentiation proposal:** pick one technical specialty and make “unknown” visible; a generic candidate agent already exists in the official plugin. [Existing sourcing skill](https://docs.crustdata.com/integrations/codex.md#skills)

**12-hour scope:** one role, ten search results, five enriched reports and human screening questions. Keep verification optional and manual-review-only. Use exact recall for mandatory filters; do not require semantic beta until contract/access is established.

**Credit planning:** five base enrichments = 5 credits. Search premium groups, developer/research add-ons and optional contacts add cost; three work-history verdicts add 30. Verification is not needed to demonstrate the core shortlist service. [Enrich pricing](https://docs.crustdata.com/person-docs/enrichment/introduction.md), [verification cost](https://docs.crustdata.com/person-docs/verification/batch.md)

**Demo sequence:** extract hard/soft criteria → show evidence-based shortlist → inspect one matching role/history → show why another candidate remains uncertain → optionally open a verification annex.

**Unresolved risks:** beta/OpenAPI schema mismatch, managed recall broadening, gated skills/repositories, stale employment and unreliable inference from sparse data. **Fallback:** structured title/employer/location filters and base work-history enrichment. **Success criterion proposal:** all mandatory filters are enforced and every suitability claim links to a matching field or source; no automatic candidate rejection.

## 5. Inbound Brief Desk

**Service being replaced:** sales-development lead qualification and pre-call preparation. Related workflow: [W5](BUSINESS_WORKFLOWS.md#w5-inbound-qualification-and-meeting-research-desk).

**Demo promise:** “Give us the inbound company and meeting goal; get one compact brief explaining fit, current context and the three best discovery questions.”

**Likely APIs:** `/company/identify`, `/company/enrich`, optional `/person/identify` and `/person/enrich`; `/web/search/live` and `/web/enrich/live`. Contacts and live company APIs are unnecessary. [Company identify](https://docs.crustdata.com/company-docs/identify/introduction.md), [enrich](https://docs.crustdata.com/company-docs/enrichment/reference.md), [person identify](https://docs.crustdata.com/person-docs/identify/introduction.md), [web](https://docs.crustdata.com/web-docs/search/reference.md)

**Crustdata advantage:** structured company/person identity supports a grounded brief with less manual lookup. **Differentiation proposal:** focus on a narrow seller/buyer vertical and a reviewable ICP score. Official meeting-prep/account-research skills already cover broad versions. [Official skill catalog](https://docs.crustdata.com/integrations/codex.md#skills)

**12-hour scope:** domain plus optional public person URL, one ICP template, one-page brief, evidence panel, no calendars or inbox integration. Simple tool calling or MCP if already accessible.

**Credit planning:** one matched company identify + one base company enrich + one web search page + two fetch pages = **5.2** list-price credits; optional person lookup/enrichment adds cost. Assumes successful matching, one company result and no paid add-ons. [Identify price](https://docs.crustdata.com/company-docs/identify/introduction.md), [company enrich price](https://docs.crustdata.com/company-docs/enrichment/introduction.md), [web prices](https://docs.crustdata.com/general/pricing.md)

**Demo sequence:** inbound submission → entity resolution → ICP evidence → recent source-backed context → useful questions and recommended next action. Show graceful handling of missing person data.

**Unresolved risks:** lower differentiation, ambiguous identities, personal email resolution and sparse recent evidence. **Fallback:** domain-only company brief with explicit unknowns. **Success criterion proposal:** a seller can use the one-page brief without redoing basic research, and every material claim is source-backed.

## Recommendation and decision gates

**Start with Staffing Demand Desk** if indexed jobs, company enrichment and people search are available. It has a concrete paid-service analogue, a visible data-to-deliverable chain, and a useful demo without contact data or waiting for a watch to fire.

Choose Modernization only after confirming technographics permission and adequate sample coverage. Choose Champion Expansion when the team has usable prior relationship data and can clearly distinguish replay from live change. Use Recruiter Evidence Pack if people data is strongest. Keep Inbound Brief Desk as the least integration-heavy fallback.

Before implementation, get organizer answers to [OPEN_QUESTIONS.md](OPEN_QUESTIONS.md): credits and endpoint grants, demonstration rules, permitted data use and whether replayed events are acceptable. Proposed local development sequence after authorization: 0–1h schema/access confirmation; 1–3h one correct data path; 3–6h useful deliverable; 6–8h evidence and partial failures; 8–10h demo interface; 10–12h rehearsal, budget check and fallback recording. This is a planning allocation, not work performed.
