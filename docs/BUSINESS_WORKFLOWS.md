# Ten service workflows AI agents could automate

Research date: **2026-11-19**. These are **proposed businesses and application workflows**, not existing Crustdata products, validated demand, or proven revenue forecasts. Each uses documented data capabilities and names the external inputs it still needs. Crustdata supplies research data; the application supplies scoring, decisions, document generation and any business-system writes. No workflow was implemented or run.

Shared execution pattern: accept a narrow client brief → validate criteria and permissions → retrieve bounded records → resolve identity → enrich only selected records → attach dated evidence → generate a client deliverable → request review before any external action. Store observed facts separately from an agent's hypothesis. Prices and access depend on the actual key; use [API_REFERENCE.md](API_REFERENCE.md) and [OPEN_QUESTIONS.md](OPEN_QUESTIONS.md).

## W1. Staffing agency business-development researcher

**Buyer and value:** a specialist staffing firm paying researchers to find employers with relevant hiring demand. Sell a prioritized account packet, with a reason to approach each employer, rather than a generic scraped contact list. Value hypothesis: reduce time spent finding demand and researching hiring managers.

**Required data:** client specialty, geography and excluded accounts; job titles/descriptions, posting dates, employer IDs/domain/size; target hiring leaders and professional URLs. Funding/headcount and optional business emails add context. Internal placement history and actual recruiter relationships are client inputs.

**Agent steps:**

1. Translate the specialty into precise job/category/description filters; use autocomplete for indexed values.
2. Search a bounded recent posting window and aggregate by employer; deduplicate reposts/IDs.
3. Enrich the top 5–10 companies and resolve the correct operating entity.
4. Find likely hiring leaders by current employer and function; keep the role-match explanation.
5. Rank demand using job evidence and client fit; draft a service-specific approach with citations.
6. Optionally create a job/company discovery feed later; baseline is not a historical lead export.

**Deliverables:** ranked employer sheet, source job links/date, demand explanation, 1–2 likely buyer profiles per account, and an outreach draft for review.

**Technical challenges:** closed jobs can remain indexed; multiple listings need not equal open budget; headquarters differs from job location; person/company joins require correct IDs. A “five new roles” rule needs application counts/aggregations, not a cross-dataset watcher predicate. Contact and live listings may be gated.

**12-hour slice:** one staffing niche, one geography, five employer packets and a traceable ranking. Show recent indexed evidence; don't promise vacancy freshness beyond timestamps.

**Official evidence:** [Jobs search/aggregations](https://docs.crustdata.com/job-docs/search/introduction.md), [job lifecycle](https://docs.crustdata.com/job-docs/search/reference.md#dataset-freshness-and-lifecycle), [company enrichment](https://docs.crustdata.com/company-docs/enrichment/introduction.md), [people search](https://docs.crustdata.com/person-docs/search/introduction.md), [job watcher](https://docs.crustdata.com/watcher-docs/job/watch.md).

## W2. Technology modernization opportunity analyst

**Buyer and value:** a cloud/data/security consultancy that manually identifies companies suited to a particular migration or integration offering. Sell a qualified modernization brief with a specific service wedge and the evidence behind it.

**Required data:** consultancy offering, compatible technologies, disqualifying environments and target size; company technographics, source evidence, current job descriptions, engineering leaders and public company content. Private architecture diagrams, contracts, actual spend and implementation plans are unavailable unless supplied by the client.

**Agent steps:**

1. Discover canonical technology/category values with company autocomplete.
2. Filter companies by technology and narrow commercial criteria; cap results before enrichment.
3. Enrich technographics for the best accounts; inspect detection source, confidence and freshness.
4. Search relevant employer jobs and fetch public technical/careers pages for corroboration.
5. Identify an engineering/data leader; distinguish deployed-stack evidence from hiring requirements.
6. Draft a modernization hypothesis, discovery questions and a scoped consulting offer.

**Deliverables:** five opportunity briefs with technology evidence, relevant hiring demand, likely buyer profiles, qualification gaps and suggested discovery agenda.

**Technical challenges:** technographics is a gated enrich add-on and a premium search filter; search does not return it. A job posting mentioning a competitor or desired skill is not installed-software proof. Entries cap at 500. Do not calculate fictitious savings, contract renewals or cloud spend.

**12-hour slice:** one technology pair and five accounts. Fallback: use job-description evidence with an explicit “technology hiring signal” label if stack access is unavailable.

**Official evidence:** [Technographics guide](https://docs.crustdata.com/guides/technographics.md), [search filter-only fields](https://docs.crustdata.com/company-docs/search/reference.md#technographics-filter-only), [enrich technology evidence](https://docs.crustdata.com/company-docs/enrichment/reference.md#technographics-fields), [jobs fields](https://docs.crustdata.com/job-docs/search/reference.md), [web fetch](https://docs.crustdata.com/web-docs/fetch/introduction.md).

## W3. Customer champion movement and expansion researcher

**Buyer and value:** a B2B customer-success or account-management team tracking whether a known champion has changed employers or roles. Sell an actionable expansion/replacement brief instead of a raw change alert.

**Required data:** client-provided champion profile URLs, CRM ownership, prior employer/role, relationship notes, customer/account exclusions and product fit; current employment, employer profile, relevant stakeholders and public developments. Crustdata does not know which person was the client's champion or whether they used the product.

**Agent steps:**

1. Resolve champion URLs and establish a timestamped baseline.
2. Use person entity tracking on new current employment/title change, or compare a client-approved prior snapshot with an authorized current enrichment.
3. Exclude baseline/test events and deduplicate real changes.
4. Enrich the new employer and assess ICP fit using explicit client criteria.
5. Find likely replacement/buying-group roles at old/new employers.
6. Produce an account-owner task with evidence, continuity risk, and a relationship-sensitive reintroduction draft.

**Deliverables:** champion movement brief, old/new company context, expansion hypothesis, replacement stakeholder candidates and CRM task draft.

**Technical challenges:** current employment can contain multiple roles; an end-date change alone is not a new-employer move. Indexed lag and person-watch freshness determine detection speed. Daily person tracking costs far more than 30-day tracking. A discovery watch dedupes lifetime entrants and does not model every repeated move. CRM writes and relationship history need separate systems.

**12-hour slice:** compare two clearly labeled snapshots for a few consented profiles and demonstrate a replayed event-to-brief flow. A simulated event is not proof that a real move occurred. A scheduled live change is not required for the demo.

**Official evidence:** [Person entity watch](https://docs.crustdata.com/watcher-docs/person/entity.md), [person enrichment](https://docs.crustdata.com/person-docs/enrichment/reference.md), [job-change freshness semantics](https://docs.crustdata.com/general/data-updates.md#job-change-signals), [company enrichment](https://docs.crustdata.com/company-docs/enrichment/introduction.md).

## W4. Specialist recruiter shortlist and evidence pack

**Buyer and value:** an agency or internal talent team commissioning a first-pass shortlist for a hard technical role. Sell a criterion-by-criterion evidence pack that reduces manual sourcing and explains uncertainty.

**Required data:** job description, mandatory versus preferred requirements, geographic constraints, target/excluded employers, candidate experience, skills, education and optional developer profiles/research. Candidate interest, availability, salary expectations and permission to contact are not implied by a matching profile.

**Agent steps:**

1. Convert the job into hard filters and soft semantic criteria; use exact recall when mandatory filters must hold.
2. Search a bounded audience, compare retrieval modes if needed and capture actual matched evidence.
3. Enrich 5–10 candidates, preserving full role dates and same-role versus cross-role distinctions.
4. Score each requirement supported/partial/unknown; do not treat inferred skills as demonstrated work.
5. Optionally verify up to a few questionable employment claims if the add-on is enabled, preserving `cannot_verify` and citations.
6. Generate a human-review shortlist and optional contact drafts.

**Deliverables:** candidate comparison matrix, evidence links, role-history summary, screening questions and optional verification annex.

**Technical challenges:** managed semantic recall can broaden constraints; `and` versus `all_of` changes career-history matching. Field permissions can block skills/certifications/developer data. Verification is probabilistic and sparse footprints produce uncertainty. Do not automate rejection from a fabrication score or claim a completed background check.

**12-hour slice:** one role, ten retrieved profiles, five candidate reports, explicit unknowns. Contact and verification can be omitted without breaking the core deliverable.

**Official evidence:** [Semantic search](https://docs.crustdata.com/guides/person-semantic-search.md), [nested-role matching](https://docs.crustdata.com/person-docs/search/reference.md#nested-array-matching-all_of-and-has_all), [JTN](https://docs.crustdata.com/guides/job-title-normalization.md), [person enrich](https://docs.crustdata.com/person-docs/enrichment/reference.md), [verification](https://docs.crustdata.com/person-docs/verification/batch.md).

## W5. Inbound qualification and meeting research desk

**Buyer and value:** a small sales team with limited operations support. Replace manual lead lookup and pre-call research with a compact, cited brief and recommended discovery agenda.

**Required data:** submitted company domain and optional business email/profile URL; client ICP, offering, meeting objective and existing CRM notes; company firmographics, recent funding/hiring/news, person role and relevant public posts.

**Agent steps:**

1. Identify the company from its domain; resolve the person only when identify access/input supports it.
2. Enrich selected firmographic fields, checking match confidence and record age.
3. Research one recent, relevant development using web/news sources and primary page content.
4. Compare observed facts with the client ICP; put missing criteria in “unknown.”
5. Draft a one-page brief, three discovery questions and a tentative demo angle.
6. Queue for the account owner to review; calendar/inbox/CRM actions are a separate integration.

**Deliverables:** qualification card with evidence, buyer-role context, meeting agenda and suggested follow-up questions.

**Technical challenges:** personal email may not identify an employer; name collisions can corrupt the whole brief. “Recent” news and current roles need dated evidence. Do not infer budget or buying authority from title alone. Meeting prep is already an official plugin skill, so differentiate around an industry or a measurable review workflow.

**12-hour slice:** accept a company domain plus optional profile URL, produce a one-screen brief in a single run, and show supporting sources. Company-only fallback works without person-identify/contact access.

**Official evidence:** [Company identify](https://docs.crustdata.com/company-docs/identify/introduction.md), [enrich](https://docs.crustdata.com/company-docs/enrichment/reference.md), [person identify](https://docs.crustdata.com/person-docs/identify/introduction.md), [news/web search](https://docs.crustdata.com/web-docs/search/reference.md), [official meeting-prep skill](https://docs.crustdata.com/integrations/codex.md#skills).

## W6. Investment sourcing and preliminary company research

**Buyer and value:** a small venture fund, accelerator or corporate-development research team. Automate first-pass thesis matching and prepare a sourced research memo for analyst review.

**Required data:** investment thesis, region/stage/sector constraints, excluded portfolio; company description, funding dates/rounds/investors, team/founders, headcount trend, jobs, launches, public news and competitors. Cap table, confidential financials, legal diligence and actual investability need separate evidence.

**Agent steps:** search thesis-matching companies → resolve entities → enrich a small shortlist → validate material funding/news claims with public sources → assess thesis criteria and gaps → produce an evidence-based memo with questions for the founder. Use company discovery later for new entrants, with a baseline handled separately.

**Deliverables:** thesis-fit market map, five company memos, source-linked funding/team timeline and an unanswered diligence checklist.

**Technical challenges:** estimated revenue differs from financial statements; investor lists are not necessarily round-specific; funding totals and employee growth are lagging signals. A domain can represent a subsidiary. Semantic similarity is not investment quality. This is research support, not an investment recommendation or diligence certification.

**12-hour slice:** one narrow thesis and five sourced memos; avoid automated investment scoring that implies financial certainty.

**Official evidence:** [Company search](https://docs.crustdata.com/company-docs/search/reference.md), [enrichment fields](https://docs.crustdata.com/company-docs/enrichment/reference.md), [discovery watcher](https://docs.crustdata.com/watcher-docs/company/discovery.md), [web sources](https://docs.crustdata.com/web-docs/search/reference.md).

## W7. Competitive intelligence and sales enablement desk

**Buyer and value:** a B2B product-marketing team paying for competitor tracking, battlecards and field-sales research. Automate evidence collection and explain what changed for a specific product segment.

**Required data:** client product claims, competitor domains and desired categories; company profiles, product/launch information, pricing/product pages from the public web, jobs, news and relevant authored posts. Internal win/loss data and real customer objections come from the client.

**Agent steps:** resolve a fixed competitor list → enrich relevant company/product sections → search and fetch public evidence → compare with a dated prior snapshot → group verified changes versus inferred strategy → draft a battlecard and discovery questions. Optionally watch company news/headcount/hiring changes; don't assume that catches every website edit.

**Deliverables:** dated competitive brief, change log, feature/positioning evidence table, sales talk-track drafts and unknowns.

**Technical challenges:** marketing pages are claims; social engagement is not customer adoption. Website structure and source availability change. Company enrichment fields may be sparse or gated. Exact price/features need direct source dates; no undocumented Crustdata website-change watcher should be invented.

**12-hour slice:** two competitors, one buyer segment, one comparison with claim-level citations.

**Official evidence:** [Company enrichment](https://docs.crustdata.com/company-docs/enrichment/reference.md), [social post search](https://docs.crustdata.com/social-post-docs/indexed-search/reference.md), [company entity watch](https://docs.crustdata.com/watcher-docs/company/entity.md), [web fetch](https://docs.crustdata.com/web-docs/fetch/introduction.md).

## W8. CRM identity resolution and enrichment audit

**Buyer and value:** a revenue-operations consultancy handling dirty account/contact databases. Automate proposed corrections and provide an auditable change set instead of overwriting records from uncertain matches.

**Required data:** client-provided CRM export with local IDs, domains/profile URLs/emails and current values; company/person identity matches, refreshed role/company records, optional contact status and account-specific access/prices. CRM credentials and the customer's merge policy are separate inputs.

**Agent steps:** validate and normalize identifiers → deduplicate within each identifier type → identify companies/people → separate exact, inferred, no-match and redacted results → enrich only sufficiently confident matches → produce field-level before/after suggestions → review ambiguous merges → optionally write approved changes through a separate CRM connector later.

**Deliverables:** correction CSV/JSON, duplicate candidates, identity confidence evidence, missing/stale/redacted report and rollback-ready proposed change log.

**Technical challenges:** names cannot reliably distinguish same-name people/companies; batch outputs differ by route; partial failures need per-input reconciliation. Redacted records must not be “recovered.” Different CRMs have different merge/ownership rules. Batch access and downstream redistribution terms need confirmation.

**12-hour slice:** a small synthetic/client-approved file, company identification and enrichment only, human-reviewed proposed changes. Do not claim synthetic records are real verified contacts.

**Official evidence:** [Company identify](https://docs.crustdata.com/company-docs/identify/introduction.md), [person identify](https://docs.crustdata.com/person-docs/identify/introduction.md), [batch enrichment](https://docs.crustdata.com/company-docs/enrichment/batch.md), [contact batch](https://docs.crustdata.com/person-docs/contact/batch.md), [redaction behavior](https://docs.crustdata.com/person-docs/enrichment/reference.md).

## W9. Scientific expert and advisory sourcing

**Buyer and value:** an expert-network researcher or corporate innovation team locating specialists with a specific research background and current industry relevance. Automate discovery and evidence assembly, leaving engagement and conflicts checks to humans.

**Required data:** research brief, topics, institutions, geography and exclusions; academic interests, publications/citations, current professional role and employer, optional developer work and public sources. Willingness to consult, availability, conflicts and compensation are not documented Crustdata fields.

**Agent steps:** search academic papers/authors and people research fields → resolve Scholar author URLs to person identities when enabled → enrich only confident cross-source matches → assess topic evidence/publication recency and role fit → propose expert shortlist with questions to establish suitability and conflicts.

**Deliverables:** five expert dossiers, publication links, topic-fit explanation, identity confidence and engagement questions.

**Technical challenges:** scholar and professional identities can mismatch; affiliations can be outdated; citation counts do not measure consulting quality. Research-profile access and fill vary. No private contact or availability assumptions. Article field types differ between web scholar results and enriched research profiles.

**12-hour slice:** one topic, three experts, two cited publications each; profile links are sufficient without private contact data.

**Official evidence:** [Research-profile schema](https://docs.crustdata.com/person-docs/enrichment/reference.md#research_profiles-fields), [Scholar identification](https://docs.crustdata.com/person-docs/identify/introduction.md), [web academic sources](https://docs.crustdata.com/web-docs/search/reference.md#sources), [person research filters](https://docs.crustdata.com/person-docs/search/reference.md).

## W10. Channel partner and ecosystem research

**Buyer and value:** a B2B partnerships team choosing potential implementation, integration or regional channel partners. Replace first-pass partner research with a specific fit and overlap analysis.

**Required data:** client offering, target markets, desired partner services, existing partners/exclusions; company descriptions, geography, size, technology signals, service-related roles, public case studies/partner pages, potential partnership leaders. Actual customer overlap, partner performance and existing contractual relationships require client/vendor evidence.

**Agent steps:** search service-compatible companies → identify entities → enrich firmographics and optional technology evidence → fetch service/case-study pages → find partnership leaders → classify complementary versus competing services → draft a partner qualification brief and meeting agenda.

**Deliverables:** partner shortlist, territory/service fit matrix, source evidence, diligence questions and introductory message drafts.

**Technical challenges:** company descriptions are broad; technology detection does not prove vendor certification. Public case studies are incomplete evidence of customer overlap. No documented account-overlap or private mutual-connection endpoint exists here. Names/branches can obscure which legal entity delivers services.

**12-hour slice:** one ecosystem and region, five candidates, a clear qualification matrix with unknowns.

**Official evidence:** [Company ranked search](https://docs.crustdata.com/company-docs/search/reference.md#ranked-search), [company enrichment](https://docs.crustdata.com/company-docs/enrichment/reference.md), [technology evidence](https://docs.crustdata.com/guides/technographics.md), [people search](https://docs.crustdata.com/person-docs/search/introduction.md), [public web retrieval](https://docs.crustdata.com/web-docs/fetch/introduction.md).

## Shared technical and commercial acceptance criteria

These are **proposed product criteria**, not Crustdata SLAs:

- Each material claim has a source URL, observed timestamp and uncertainty label; every generated business recommendation cites the facts that motivate it.
- Identity is resolved before cross-dataset joins; duplicates, ambiguous matches, redactions, no-results and gated fields produce useful partial deliverables.
- A bounded run has a declared result cap, selective field list and credit estimate; actual usage is reconciled from headers/usage later.
- Demonstrations label indexed, live, cached and simulated evidence clearly. A watcher sample is not a production change.
- Measure completion time and manual corrections against the original service task. Commercial value scores remain hypotheses until a buyer validates the deliverable.
- Confirm allowed customer-facing use and retention before selling derived reports or exposing raw data. The documented [dashboard export restrictions](https://docs.crustdata.com/export-docs/data-export.md#terms) are not permission to resell data through another route.
