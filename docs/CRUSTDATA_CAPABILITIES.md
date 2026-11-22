# Crustdata capabilities for ContextCon

Research date: **2026-11-19**. API version documented: **2025-11-01**. This is a documentation review, not an integration test. No authenticated data calls, accounts, installs, deployments, watches, or billable searches were made. A metadata-only MCP initialization without credentials returned `401 invalid_token`; it retrieved no data.

Start here: [official documentation index](https://docs.crustdata.com/llms.txt), [platform capabilities](https://docs.crustdata.com/general/capabilities.md), [API introduction](https://docs.crustdata.com/openapi-specs/2025-11-01/introduction.md). The research corpus included the index's 111 linked pages, with detailed review of the major family guides, references and 50 public operation schemas, plus linked gated-guide checks and the public MCP catalog index. Gated guide contents and authenticated MCP schemas remain unverified.

## How to use this research

- [API_REFERENCE.md](API_REFERENCE.md): request contracts, endpoint inventory, examples, prices, restrictions.
- [BUSINESS_WORKFLOWS.md](BUSINESS_WORKFLOWS.md): ten proposed services and their deliverables.
- [AGENT_ARCHITECTURES.md](AGENT_ARCHITECTURES.md): implementation choices for later work.
- [HACKATHON_IDEAS.md](HACKATHON_IDEAS.md): five ranked, bounded projects.
- [OPEN_QUESTIONS.md](OPEN_QUESTIONS.md): unresolved access, schema, pricing, and event questions.

**Evidence labels:** **Documented** means explicitly supported by a linked official page, not tested by us. **Observed** means an HTTP result encountered during this review. **Proposal** means our workflow/design inference. **Unverified** means no usable public contract or account evidence. Documentation examples describe shapes; they do not establish coverage for a particular prospect or region.

## Platform map

| Family | Documented capability | Typical service use | Official sources |
| --- | --- | --- | --- |
| Company | Structured and ranked search; identify; enrich; autocomplete; bulk jobs | Account discovery, firmographic research, CRM cleanup, technology targeting | [Search](https://docs.crustdata.com/company-docs/search/introduction.md), [identify](https://docs.crustdata.com/company-docs/identify/introduction.md), [enrich](https://docs.crustdata.com/company-docs/enrichment/introduction.md) |
| Person | Structured and semantic search; profile enrichment; identity resolution; contact retrieval; bulk verification | Recruiting, buying groups, inbound qualification, work-history review | [Search](https://docs.crustdata.com/person-docs/search/introduction.md), [enrich](https://docs.crustdata.com/person-docs/enrichment/introduction.md), [identify](https://docs.crustdata.com/person-docs/identify/introduction.md), [contact](https://docs.crustdata.com/person-docs/contact/enrich.md), [verification](https://docs.crustdata.com/person-docs/verification/batch.md) |
| Job | Indexed listings, field selection, aggregations, autocomplete; gated live company listings | Staffing demand, hiring intelligence, market maps | [Guide](https://docs.crustdata.com/job-docs/search/introduction.md), [field reference](https://docs.crustdata.com/job-docs/search/reference.md) |
| Social post | Indexed post/author/engagement/participant search; gated live search and retrieval | Intent research, competitor communities, evidence for outreach | [Guide](https://docs.crustdata.com/social-post-docs/indexed-search/introduction.md), [reference](https://docs.crustdata.com/social-post-docs/indexed-search/reference.md) |
| Web | Live multi-source search and public HTML fetch | News validation, research evidence, company website analysis | [Search](https://docs.crustdata.com/web-docs/search/introduction.md), [fetch](https://docs.crustdata.com/web-docs/fetch/introduction.md) |
| Watch | Discovery feeds and entity change notifications, including joins across datasets | Champion changes, new hiring accounts, funding alerts | [Person entity](https://docs.crustdata.com/watcher-docs/person/entity.md), [company discovery](https://docs.crustdata.com/watcher-docs/company/discovery.md), [joins](https://docs.crustdata.com/watcher-docs/cross-dataset-filters.md) |
| Agent Search, beta | Natural-language, asynchronous person/company/job research with per-row evidence | Research concierge, complex shortlist requests | [Overview](https://docs.crustdata.com/agent-search-docs/overview.md) |
| Account | Permissions, effective RPM, account-specific prices, credits and request-level usage | Cost controls, access checks, troubleshooting | [Permissions](https://docs.crustdata.com/general/permissions.md), [credits](https://docs.crustdata.com/general/credits.md), [usage](https://docs.crustdata.com/general/usage.md) |
| Agent integrations | MCP, CLI, and workflow skills in official plugins | Interactive research and composed tool workflows | [MCP](https://docs.crustdata.com/for-agents/mcp.md), [CLI](https://docs.crustdata.com/for-agents/cli.md), [Codex plugin](https://docs.crustdata.com/integrations/codex.md) |
| Data export | Dashboard-only scheduled people/company exports | Large internal datasets and recurring research files | [Export](https://docs.crustdata.com/export-docs/data-export.md) |

## Company data: discovery versus detailed research

### Searchable and returned data

**Documented:** search works on indexed columns. Important paths include `crustdata_company_id`, `basic_info.name`, `basic_info.primary_domain`, `basic_info.company_type`, `basic_info.year_founded`, `basic_info.status`, `locations.country/state/city/headquarters`, `headcount.total`, `funding.last_fundraise_date`, `funding.last_round_type`, `funding.total_investment_usd`, and revenue estimate bounds. Taxonomy includes professional-network industries, categories, specialities, primary NAICS and SIC classifications. Followers, hiring counts/growth, software reviews, and selected growth metrics are available with permissions/pricing considerations. [Search field catalog](https://docs.crustdata.com/company-docs/search/reference.md)

Some searchable data is **not returned by company search**: `roles.*`, `competitors.company_ids`, `competitors.websites`, and `technographics.*`. For example, filtering on technology does not put the stack in the search response. Industry aliases also differ from the returned taxonomy paths. [Search field distinctions](https://docs.crustdata.com/company-docs/search/reference.md#filterable-but-not-returned)

Search accepts filters, natural-language relevance, or both. Ranked modes are `hybrid`, `lexical`, and `semantic`; ranked pagination is bounded to 1,000 candidate positions, 100 per page, with 20-minute cursors. Custom sorting belongs to filter-only search. [Ranked search](https://docs.crustdata.com/company-docs/search/reference.md#ranked-search)

### Enrichment field families

The following are documented enrichment sections; field access and record population vary. They are not a promise that every section is included by default. Default company enrichment is `basic_info`. [Enrichment schema](https://docs.crustdata.com/company-docs/enrichment/reference.md)

| Sections | Accessible information | Useful output |
| --- | --- | --- |
| `basic_info`, `locations`, `taxonomy`, `social_profiles` | Names, domains, description, founding year, company type/status, office addresses, classifications and external identifiers | Verified company card |
| `headcount` | Total, function and regional breakdowns, absolute/percentage growth | Expansion/organizational hypothesis |
| `funding`, `revenue` | Funding rounds, investors, acquisitions/milestones; estimated revenue ranges and public-market metadata | Funding and market context |
| `hiring`, `people` | Opening counts/growth, recent openings; founders, CXOs, decision makers | Buying-group and hiring research |
| `seo`, `web_traffic`, `competitors` | Organic visibility, ad-budget estimates, per-domain visitors and traffic sources, SEO competitors | Marketing research brief |
| `news`, `employee_reviews`, `software_reviews`, `reviews` | News URLs/titles/dates and review metrics/buckets | Cited developments and review signals |
| `public_launches`, `market_intel` | Product launches, makers, ratings, products and market-intelligence details | Product positioning research |
| `technographics` | Technology names/categories, detection sources and evidence | Technology-specific service targeting |
| `social_posts` | Up to ten recent authored posts, text, URLs, dates and engagement | Recent account context |

The table summarizes the [enrichment field catalog](https://docs.crustdata.com/company-docs/enrichment/reference.md#company_data-sections); it does not define individual nested objects. In particular, search growth keys such as `1m`/`12m` differ from enrichment's `mom`/`yoy`; explicitly map them. Revenue values are estimates, not audited revenue.

**Technographics:** searches can filter on names, category slugs and super-categories. Enrichment returns up to 500 technology entries, even if `total_technologies` is larger. Detection can come from web signals or job postings, with evidence and confidence; a job mention is evidence of demand, not proof of a deployed production stack. Job technographics are posting-specific, while company technographics describe the organization. [Technology guide](https://docs.crustdata.com/guides/technographics.md), [company schema](https://docs.crustdata.com/company-docs/enrichment/reference.md#technographics-fields), [job schema](https://docs.crustdata.com/job-docs/search/reference.md#technographics-filter-only)

## Person, identity, contact and verification data

### Person search and enrichment

**Documented data:** identity/name/headline/title/location, social handles, current and past employment, employer details and dates, education, skills, languages, professional-network metrics, certifications/honors, developer profiles/repositories, academic author profiles, and selected assessment fields. Search and enrich use different paths in places; do not treat the union as a single schema. [Search catalog](https://docs.crustdata.com/person-docs/search/reference.md), [enrich catalog](https://docs.crustdata.com/person-docs/enrichment/reference.md)

| Field family | Main contents and limitations | Official source |
| --- | --- | --- |
| `basic_profile`, `social_handles` | Name, current title, headline, location, summary and profile URLs; permanent URN URL is gated | [Enrich fields](https://docs.crustdata.com/person-docs/enrichment/reference.md#person_data-sections) |
| `experience` | Current/past roles, dates, company identifiers and status, career experience bands/raw total | [Search experience](https://docs.crustdata.com/person-docs/search/reference.md), [enrich experience](https://docs.crustdata.com/person-docs/enrichment/reference.md) |
| `education`, `skills`, `certifications`, `honors` | Schools, degrees, study fields, skill labels and awards; several search/response groups require grants | [Search fields](https://docs.crustdata.com/person-docs/search/reference.md) |
| `professional_network` | Connections/followers, location, open-to cards and other profile metadata where populated | [Enrich catalog](https://docs.crustdata.com/person-docs/enrichment/reference.md) |
| `dev_platform_profiles` | Developer profiles and repository context; search must explicitly request this group; repository search costs more | [Search reference](https://docs.crustdata.com/person-docs/search/reference.md) |
| `research_profiles` | Scholar author identity, affiliation, research interests, citations, h/i10 indices, publications, coauthors and refresh metadata | [Academic schema](https://docs.crustdata.com/person-docs/enrichment/reference.md#research_profiles-fields) |
| `assessment.authenticity` | Verdict and tier; explicitly requested, gated, enrich-only | [Assessment](https://docs.crustdata.com/person-docs/enrichment/reference.md#assessment-fields) |
| `social_posts` | Up to ten authored posts; gated beta add-on | [Posts add-on](https://docs.crustdata.com/person-docs/enrichment/reference.md#social_posts-fields) |

Person Search also exposes `contact.has_business_email`, an availability flag rather than the email itself. False does not guarantee that Contact Enrich cannot find an address. [Search contact schema](https://docs.crustdata.com/api-reference/person-apis/search-people-using-filters-and-sorting.md)

Job Title Normalization is a beta field, `basic_profile.normalized_title`, with `department`, `sub_department`, `matched_title`, `similarity`, and `confident`; it is a taxonomy mapping, not a verified seniority or competence assessment. [JTN guide](https://docs.crustdata.com/guides/job-title-normalization.md)

Semantic search has two distinct choices: `search.mode` selects retrieval (`hybrid`/`lexical`/`semantic`); top-level `mode` selects recall behavior (`managed`/`exact`). Managed recall can broaden explicit constraints; use `exact` for mandatory criteria. Ranked head results may have `fit` tiers. This documented beta contract is incompletely represented in the public OpenAPI request model. [Semantic guide](https://docs.crustdata.com/guides/person-semantic-search.md)

### Identity resolution and contact

Person Identify resolves one identifier type per call: profile URLs, emails, or Google Scholar URLs, up to 25 synchronously. Batch Identify supports up to 300 emails or profile URLs; it does not accept `fields`. The person guide says synchronous emails can be personal, while the batch API reference says personal resolution is batch-only. **Treat synchronous personal-email resolution as disputed.** [Identify guide](https://docs.crustdata.com/person-docs/identify/introduction.md), [batch reference](https://docs.crustdata.com/api-reference/batch-apis/submit-a-batch-person-identify-reverse-email-lookup-job.md)

Contact enrichment is a **separate enterprise-gated API**, returning business/personal emails, phone strings and structured phone details, and optionally websites. Email entries are `{email, status}` objects. `verified: true` rechecks business emails at request time, but can still return `catch_all`; it is not a delivery guarantee. Batch contact has a required field list, a 300-profile limit and a documented higher fill rate than synchronous lookup. [Synchronous contact](https://docs.crustdata.com/person-docs/contact/enrich.md), [batch contact](https://docs.crustdata.com/person-docs/contact/batch.md)

`match_status: redacted` is an intentional removal, not a transient missing record; do not retry with live retrieval to recover it. [Person enrich reference](https://docs.crustdata.com/person-docs/enrichment/reference.md#response-fields-reference)

### Work-history verification

`POST /batch/person/verify` accepts up to ten profiles and returns verdicts with confidence, reasoning, flags, coverage and source citations. It checks timeline consistency, social/coworker evidence and public-web evidence. Seven verdicts include `cannot_verify`, `reclassified_employment`, and `non_person`. This is a research assessment, not an authoritative background check or guaranteed truth. A sparse footprint can prevent verification. [Verification guide](https://docs.crustdata.com/person-docs/verification/batch.md)

## Jobs and social posts

**Jobs:** each listing has `crustdata_job_id`, `job_details` (title/category/workplace/source/employment type/URL/openings), `company` firmographics, `location`, `content.description`, and `metadata.date_added/date_updated`. Search supports sorting, cursors, projections, count/group-by aggregations and geographic filters. Filter company IDs with `company.basic_info.company_id`; returned IDs use `company.basic_info.crustdata_company_id`. A batch job fetches all listings for at most ten company IDs, rather than arbitrary job filters. Do not infer a closed-job signal or complete ATS coverage. [Guide](https://docs.crustdata.com/job-docs/search/introduction.md), [fields and lifecycle](https://docs.crustdata.com/job-docs/search/reference.md), [batch](https://docs.crustdata.com/job-docs/search/batch-search.md)

**Social posts:** indexed records include post URNs/URL/text/date/type, author or reposter identity and location, engagement counts, reactors, commenters, mentions, links, attachments and update metadata. Person/company author fields are not equally populated. Filter paths for participants can differ from returned nested paths. Large engagement arrays can dominate payloads. The reference currently flags `has_video` and video/image content classifications as unreliable, and attachment `is_not_null` checks as overmatching. These are documented observations, not behavior tested here. [Search reference](https://docs.crustdata.com/social-post-docs/indexed-search/reference.md)

## Web search and retrieval

Search sources: `web`, `news`, `scholar-articles`, `scholar-articles-enriched`, `scholar-author`, `ai`, `social`. Results are source-specific: web/news return URLs/snippets, papers can include authors/citations, author profiles have research metrics, and `ai` returns an overview with references. `site` works only for web/news; date restrictions are source-dependent. `page` means the number of pages aggregated, not a conventional offset. [Search reference](https://docs.crustdata.com/web-docs/search/reference.md)

Fetch returns server-side HTML for 1–10 public URLs. It does not promise JavaScript execution, authenticated-site access, PDF parsing, anti-bot success, or an already cleaned article. `human_mode` attempts an alternate retrieval path. Search timestamps use milliseconds and fetch timestamps seconds. [Fetch guide](https://docs.crustdata.com/web-docs/fetch/introduction.md)

## Monitoring and change delivery

Discovery watches deliver newly matching records for company, person, job or social-post searches. Entity watches compare a supplied person/company list with stored snapshots. An entity trigger can be a scalar change, array addition, or a comparison becoming true; `track` and delivered `fields` serve different purposes. [Discovery](https://docs.crustdata.com/watcher-docs/company/discovery.md), [person entity](https://docs.crustdata.com/watcher-docs/person/entity.md), [company entity](https://docs.crustdata.com/watcher-docs/company/entity.md)

- First runs establish a free baseline and deliver a sample of at most five. They do not backfill the full existing audience. An entity baseline has no changes. [Person baseline](https://docs.crustdata.com/watcher-docs/person/entity.md#how-a-watch-runs), [job baseline](https://docs.crustdata.com/watcher-docs/job/watch.md)
- Indexed discovery can combine company/person/job conditions via employer/company joins. These are existence tests, not arbitrary SQL: cross-dataset counts, growth calculations and negative existence predicates are unsupported. Records are delivered once per discovery watch even if they later leave and re-enter. [Join rules](https://docs.crustdata.com/watcher-docs/cross-dataset-filters.md)
- Delivery options are webhook, Slack, Google Chat, email, or an empty channel list with run-history reads. Inline delivery supports 1,000 records; link delivery supports 10,000, with a five-day NDJSON link and an inline fallback. [Channels](https://docs.crustdata.com/watcher-docs/company/discovery.md#delivery-channels), [payload delivery](https://docs.crustdata.com/watcher-docs/payload-delivery.md)
- Live discovery uses `config.is_realtime: true`, `realtime_filters`, and optionally `narrowing_filters`. It rejects the normal `filters` tree and runs at most daily, despite the name “realtime.” Company/person/job live watches have dataset-specific bounds; social live discovery has no creation-time match-count cap. [Company](https://docs.crustdata.com/watcher-docs/company/discovery.md#realtime-watches), [person](https://docs.crustdata.com/watcher-docs/person/discovery.md#realtime-watches), [job](https://docs.crustdata.com/watcher-docs/job/watch.md#realtime-watches), [social](https://docs.crustdata.com/watcher-docs/social-post/discovery.md#realtime-watches)

Important exception: a company realtime watch containing `funding.*` sends that funding-only filter tree to the company index, with other criteria under `narrowing_filters.company`. Do not claim every realtime funding notification is independently fetched from the web at run time. [Company funding behavior](https://docs.crustdata.com/watcher-docs/company/discovery.md#filter-fields-the-live-company-search-accepts)

## Freshness, access and economics

Indexed person/company/job/technographic datasets refresh on a documented 1–30-day cadence; social posts on 1–45 days. Index rebuilds can lag source refreshes. Use record timestamps and surface their age. `recently_changed_jobs` describes a previous role ending within 90 days of an index rebuild; a specific new-role window needs employment start-date filters. [Freshness](https://docs.crustdata.com/general/data-updates.md)

Live retrieval fetches at request time, costs more, accepts a different filter vocabulary, and often needs enterprise/add-on access. General freshness docs broadly call live enterprise-only, but web endpoint guides explicitly allow self-serve: use the endpoint-specific contract and verify account permissions. Batch jobs are described as enterprise access. [Freshness overview](https://docs.crustdata.com/general/data-updates.md), [web access](https://docs.crustdata.com/web-docs/search/introduction.md), [batch access](https://docs.crustdata.com/company-docs/enrichment/batch.md)

Costs have three dimensions: returned records, premium groups filtered/returned, and freshness tier. Search filter and response charges are independent; sorting is free. Account-specific prices/fields/RPM come from the free permissions endpoint; watcher quotes are separate. See the full cost tables in [API_REFERENCE.md](API_REFERENCE.md), with [official pricing](https://docs.crustdata.com/general/pricing.md) and [permissions](https://docs.crustdata.com/general/permissions.md) as authorities. No account entitlement or dollar-per-credit conversion was verified.

## MCP catalog and official workflow patterns

**Documented connection:** `https://install.crustdata.com/mcp`; interactive OAuth or programmatic bearer API key. The public page describes composed scripts and these catalog resources. **Observed:** unauthenticated initialization returned `401`; resource contents and the live callable-tool list were not retrieved. Do not assume REST path names equal MCP tool names. [MCP documentation](https://docs.crustdata.com/for-agents/mcp.md)

| Resource URI | Publicly documented purpose |
| --- | --- |
| `crustdata://catalog` | Rules and section index; read first |
| `crustdata://catalog/quickstart` | Composing tool calls in a script |
| `crustdata://catalog/tools` | Callable tools, purposes and costs |
| `crustdata://catalog/query-builder` | Operators and matching |
| `crustdata://catalog/results` | `project`, `compact`, `paginate`, `parallelMap` |
| `crustdata://catalog/fields` | Columns and identifiers |
| `crustdata://catalog/patterns` | Search/enrich, identify/enrich, bulk and pagination |
| `crustdata://catalog/dry-run` | Zero-credit script testing |
| `crustdata://catalog/ranking` | Bounded retrieval and ranking in code |
| `crustdata://catalog/cost` | Pricing and cheapest-path rules |
| `crustdata://catalog/full` | Complete guide |

Source for resource names and descriptions: [official MCP catalog index](https://docs.crustdata.com/for-agents/mcp.md#catalog-resources). Helper signatures, exact tool input/output schemas, watcher/Agent Search parity, and dry-run validation guarantees remain unverified. The public page additionally names a `feedback` reporting tool; no feedback was sent.

The official plugin documents eight workflow skills: account research, candidate sourcing, email enrichment, ICP building, meeting preparation, sales outreach, sales prospecting and warm-path workspaces. These establish that generic prospecting and meeting-prep flows already have official recipes; hackathon differentiation needs a narrower buyer and useful deliverable. A warm-path recipe does not establish access to a private connections graph. Gmail drafting mentioned in a skill requires a separate integration. [Official skill catalog](https://docs.crustdata.com/integrations/codex.md#skills), [official repository](https://github.com/crustdata/skills)

## Dashboard export and boundaries

Data Export has **no API**. It supports filtered company/person CSV or nested JSONL, gzipped files and schedules. The default ceiling is one million rows per run, one active run per export/two per team; team caps can differ. It rejects semantic `search.query` and custom sorts. Admins manage exports; members can view/download. Export terms explicitly restrict resale/redistribution and require internal use. Clarify the terms for any customer-facing research service rather than assuming bulk-data resale is allowed. [Export documentation](https://docs.crustdata.com/export-docs/data-export.md)

No official public contract reviewed here establishes CRM writes, email sending, calendar scheduling, private inbox access, a complete social graph, purchasing intent as a ground-truth label, financial due diligence certification, or automatic hiring decisions. Those are proposed application behavior or separate integrations, not Crustdata data capabilities.
