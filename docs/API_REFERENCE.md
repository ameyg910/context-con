# Crustdata API reference for agent planning

Reviewed **2026-11-19** against [llms.txt](https://docs.crustdata.com/llms.txt), guides and their embedded OpenAPI. Version: `2025-11-01`. Examples below are **documentation-grounded request examples, never executed**. Response descriptions list relevant structure, not a complete JSON schema. Example identifiers are illustrative public documentation identifiers, not guaranteed current matches. Read [OPEN_QUESTIONS.md](OPEN_QUESTIONS.md) before implementing disputed features.

## Shared transport, authorization and errors

Base URL: `https://api.crustdata.com`. Use `Authorization: Bearer YOUR_API_KEY`, `x-api-version: 2025-11-01`, and `Content-Type: application/json` for JSON bodies. `GET` endpoints use query/path parameters. Keys belong on a backend. [Official introduction](https://docs.crustdata.com/openapi-specs/2025-11-01/introduction.md)

Example full request, for reference only:

```bash
curl --request POST 'https://api.crustdata.com/company/identify' \
  --header 'Authorization: Bearer YOUR_API_KEY' \
  --header 'x-api-version: 2025-11-01' \
  --header 'Content-Type: application/json' \
  --data '{"domains":["retool.com"]}'
```

Source: [Company Identify](https://docs.crustdata.com/company-docs/identify/introduction.md). JSON examples in later sections are the body for their named endpoint, with these same headers.

Modern errors generally have `error: {type, message, metadata}`; some gateway authentication failures use a flat `message`. Older introductory examples use `description` or person `reason`. Preserve the actual HTTP/body rather than assuming one universal envelope. `402 insufficient_credits` can mean account balance or a per-key cap; stop until remedied. `403` can deny endpoint access or selected fields; retrying unchanged input will not fix it. `429` requires pacing/backoff using `X-RateLimit-Reset` seconds and jitter. Respect `Retry-After` where present, especially batch concurrency. [Best practices](https://docs.crustdata.com/openapi-specs/2025-11-01/best-practices.md)

Capture `X-Request-Id`, `X-Credits-Used`, and rate headers when present. Usage endpoints explicitly omit `X-Credits-Used`; Agent Search streaming reports its final charge in the event body. [Credits](https://docs.crustdata.com/general/credits.md), [usage](https://docs.crustdata.com/general/usage.md), [Agent Search billing](https://docs.crustdata.com/agent-search-docs/overview.md#search-states-and-the-charge)

## Indexed filter grammar and field discipline

Leaf: `{"field":"headcount.total","type":"=>","value":100}`. Group: `{"op":"and","conditions":[...leaves or groups...]}`. `or` expresses alternatives. Do not send `column`, SQL, Mongo operators, `>=`, or `<=` in place of the documented grammar. The comparison spellings are `=>` and `=<`. [Company operators](https://docs.crustdata.com/company-docs/search/reference.md#filter-operator-reference)

| Operators / feature | Support and caveats | Sources |
| --- | --- | --- |
| `=`, `!=`, `<`, `=<`, `>`, `=>`, `in`, `not_in` | Core indexed predicates; value types follow the field | [Company](https://docs.crustdata.com/company-docs/search/reference.md), [person](https://docs.crustdata.com/person-docs/search/reference.md), [job](https://docs.crustdata.com/job-docs/search/reference.md), [social](https://docs.crustdata.com/social-post-docs/indexed-search/reference.md) |
| `(.)`, `[.]` | Fuzzy all-word versus exact contiguous phrase. Use `[.]` for precise products/brands; fuzzy short terms overmatch | [Job matching](https://docs.crustdata.com/job-docs/search/reference.md#filter-operators) |
| `contains`, `not_contains`, `(!)` | Company aliases/negation; do not port across products without checking their allowlist | [Company](https://docs.crustdata.com/company-docs/search/reference.md), [person text semantics](https://docs.crustdata.com/person-docs/search/reference.md#free-text-fields-match-a-phrase) |
| `is_null`, `is_not_null` | Company/person/job allow omitted or null value. Social requires explicit `"value":null`. Blank and missing are distinct in several datasets | [Company](https://docs.crustdata.com/company-docs/search/reference.md#null-checks-is_null-and-is_not_null), [job](https://docs.crustdata.com/job-docs/search/reference.md), [social](https://docs.crustdata.com/social-post-docs/indexed-search/reference.md) |
| `all_of`, `has_all` | Person/social nested-array behavior; company `has_all` only on specified technology/SIC lists. Person normal `and` generally means same nested element; repositories/articles are exceptions | [Person nesting](https://docs.crustdata.com/person-docs/search/reference.md#nested-array-matching-all_of-and-has_all), [social nesting](https://docs.crustdata.com/social-post-docs/indexed-search/reference.md#nested-array-matching-all_of-and-has_all), [company](https://docs.crustdata.com/company-docs/search/reference.md#has_all-on-nested-list-fields) |
| `geo_distance`, `geo_exclude`, `geo_polygon` | Only designated geo fields; radius uses place or `[lat,lng]`, positive distance and units. Polygon needs 3–1,000 points. No arbitrary address field support | [Company](https://docs.crustdata.com/company-docs/search/reference.md), [person](https://docs.crustdata.com/person-docs/search/reference.md), [job](https://docs.crustdata.com/job-docs/search/reference.md), [social](https://docs.crustdata.com/social-post-docs/indexed-search/reference.md) |

Autocomplete returns dataset-specific values; use them verbatim. Searchable, sortable, groupable, autocomplete-enabled and selectable are **different allowlists**. Person free-text `=`/`in` can mean phrase matching, whereas `basic_profile.headline =` matches a whole headline. Company `in` lists above 100 values change case behavior. The field references are authoritative for these exceptions. [Person reference](https://docs.crustdata.com/person-docs/search/reference.md), [company reference](https://docs.crustdata.com/company-docs/search/reference.md)

## 1. Company APIs

### POST /company/search

**Input:** at least one of `filters` or `search`; optional `fields`, `sorts`, `limit`, `cursor`. Filter-only limit 1–1,000/default 20. Ranked limit 1–100/default 20. `search` needs a nonempty `query` and accepts `mode: hybrid|lexical|semantic` (default hybrid). Ranked search rejects `sorts`. **Response:** `{companies, next_cursor, total_count}`; IDs are retained, totals can be null. Ranked totals are always null. **Base cost:** 0.03/result plus premium groups; **30 RPM**. [Guide](https://docs.crustdata.com/company-docs/search/introduction.md), [reference](https://docs.crustdata.com/company-docs/search/reference.md), [OpenAPI](https://docs.crustdata.com/api-reference/company-apis/search-companies-with-indexed-fields-only.md)

```json
{
  "filters": {"field":"basic_info.primary_domain","type":"=","value":"retool.com"},
  "fields": ["crustdata_company_id","basic_info.name","basic_info.primary_domain"],
  "limit": 5
}
```

Ranked variant:

```json
{"search":{"query":"software companies","mode":"hybrid"},"fields":["crustdata_company_id"],"limit":2}
```

Ranked search reranks the first 100 candidates; remaining pages retain retrieval order, up to 1,000 candidate positions. Cursor lifetime is 20 minutes from initial search, not renewed. Keep query/mode/filters/version fixed; authorized fields and page size can change on ranked pages. Filter-only pagination requires stable filters/sorts/fields. Search reference says omission returns all fields, while API operation says premium groups require explicit selection or free entitlement: **always supply fields and do not assume a universal no-fields price.** [Pagination](https://docs.crustdata.com/company-docs/search/reference.md#ranked-pagination), [operation pricing](https://docs.crustdata.com/api-reference/company-apis/search-companies-with-indexed-fields-only.md)

### POST /company/identify

**Input:** exactly one array of `domains`, `names`, `professional_network_profile_urls`, `crustdata_company_ids`; max 25 values. Optional `exact_match`. **Response:** top-level array of `{matched_on, match_type, matches:[{confidence_score, company_data}]}`. **Cost:** 0.2 per matching identifier, once per duplicate input within a request; no-match free. **30 RPM**. [Guide/schema](https://docs.crustdata.com/company-docs/identify/introduction.md), [OpenAPI](https://docs.crustdata.com/api-reference/company-apis/identify-a-company-from-name-domain-id-or-profile-url.md)

```json
{"domains":["retool.com"],"exact_match":true}
```

A name can return multiple candidate companies. Check domain and confidence before choosing. Handle empty `matches` and the documented possible 404. Other pages call this endpoint free, conflicting with its dedicated guide and pricing: budget 0.2 until account pricing resolves it.

### POST /company/enrich

**Input:** same one-of identifiers/max 25; optional `fields`, `exact_match` (default null/auto). Without `fields`, only `basic_info`. **Response:** identification envelope, with detailed `matches[].company_data`. **Cost:** 2/company, +2 for populated requested technographics; gated social-post add-on +5 when posts return. **15 RPM**. [Guide](https://docs.crustdata.com/company-docs/enrichment/introduction.md), [field/schema reference](https://docs.crustdata.com/company-docs/enrichment/reference.md), [OpenAPI](https://docs.crustdata.com/api-reference/company-apis/get-full-company-enrichment.md)

```json
{"domains":["stripe.com"],"fields":["basic_info","headcount","funding","hiring"],"exact_match":true}
```

Sections include locations/taxonomy/revenue/SEO/web traffic/competitors/people/news/reviews/public launches/market intel. Field-level grants can remove or deny sections. Growth windows differ from search. Detailed fields are summarized in [CRUSTDATA_CAPABILITIES.md](CRUSTDATA_CAPABILITIES.md). Unmatched input normally has `matches:[]`; specs also define 404. [Enrich reference](https://docs.crustdata.com/company-docs/enrichment/reference.md)

## 2. Person APIs

### POST /person/search

**Structured input:** required `filters`; optional `fields`, `sorts`, `limit`/`count` (1–1,000/default 20), `cursor`, `post_processing` (`exclude_profiles`, `exclude_names`), `preview`, `return_query`, `explain`. **Response:** `{profiles, next_cursor, total_count}`; some queries add `remarks`. **30 RPM**. Base 0.03/result; no-fields requests are documented as 0.23/result because default experience and education add charges. [Guide](https://docs.crustdata.com/person-docs/search/introduction.md), [reference](https://docs.crustdata.com/person-docs/search/reference.md), [OpenAPI](https://docs.crustdata.com/api-reference/person-apis/search-people-using-filters-and-sorting.md)

```json
{
  "filters":{"field":"experience.employment_details.current.title","type":"=","value":"CEO"},
  "fields":["basic_profile.name","basic_profile.current_title"],
  "sorts":[{"field":"crustdata_person_id","order":"asc"}],
  "limit":5
}
```

**Semantic beta input:** the guide separately documents `search.query`, `search.mode`, top-level `mode: managed|exact`, `search.query_syntax: plain|boolean`, and optional search explanations. Boolean syntax requires lexical retrieval plus exact recall. Query limit is 131,072 characters/about 32k tokens. `fit` (`strong|possible|weak`) applies to a reranked head of at most 200; cursor traversal stops after 10,000, with a lower-confidence tail. Counts include `total_count_relation: eq|gte`. These fields are absent from the restrictive public OpenAPI request model; confirm the current contract before implementation. [Semantic guide](https://docs.crustdata.com/guides/person-semantic-search.md)

```json
{
  "filters":{"field":"basic_profile.location.country","type":"=","value":"United States"},
  "search":{"query":"engineers building distributed data systems","mode":"hybrid"},
  "mode":"exact",
  "fields":["basic_profile.name","basic_profile.current_title"],
  "limit":5
}
```

The semantic example composes fields documented in that guide; it has not been validated against a live key. Normal filters and semantic prompts have different recall guarantees. Preview search is premium-gated (`403` without access), and its cost should be confirmed; do not assume it inherits free enrich-preview pricing. `return_query` is accepted but the reference says no top-level query is returned, despite older spec text. [Preview/reference](https://docs.crustdata.com/person-docs/search/reference.md#preview-mode)

`contact.has_business_email` is a filterable/returned availability boolean, not a contact value or guaranteed fill prediction. A false flag can still be followed by a successful Contact Enrich. [Search contact schema](https://docs.crustdata.com/api-reference/person-apis/search-people-using-filters-and-sorting.md)

### POST /person/enrich

**Input:** required `professional_network_profile_urls` (max 25); optional `fields`, gated `preview`. Default groups: `basic_profile`, `social_handles`. **Response:** array of `{matched_on, match_type, match_status, matches:[{confidence_score, person_data}]}`. `match_status` is matched/not_found/redacted. **15 RPM**. [Guide](https://docs.crustdata.com/person-docs/enrichment/introduction.md), [reference](https://docs.crustdata.com/person-docs/enrichment/reference.md), [OpenAPI](https://docs.crustdata.com/api-reference/person-apis/enrich-person-profiles-from-cached-dataset.md)

```json
{
  "professional_network_profile_urls":["https://www.linkedin.com/in/dvdhsu/"],
  "fields":["basic_profile","social_handles","experience","education"]
}
```

**Cost:** 1 base; requested developer data +1, populated research profiles +2, populated social posts +5. Experience/education/skills/professional-network context belong to base enrich rather than search's premium schedule. All add-ons together imply up to 9, although some guide summaries say up to 4 by omitting social posts. Gated enrich `preview:true` is documented at zero credits, ignores `fields`, and cannot combine with `enrich_realtime`; without the grant it returns 400. The public stable request table does not fully define `enrich_realtime`: use separately documented live routes only after access/schema confirmation. [Enrich pricing/preview](https://docs.crustdata.com/person-docs/enrichment/introduction.md), [reference](https://docs.crustdata.com/person-docs/enrichment/reference.md)

Contact fields belong to `/person/contact/enrich`; do not copy old combined profile/contact examples. `assessment` is explicitly requested and gated; a cached authenticity tier is distinct from a fresh batch verification report. [Contact guide](https://docs.crustdata.com/person-docs/contact/enrich.md), [assessment](https://docs.crustdata.com/person-docs/enrichment/reference.md#assessment-fields)

### POST /person/identify

**Input:** exactly one of `professional_network_profile_urls`, `emails`, `research_profile_urls`; max 25. Only Google Scholar author URLs with a `user` parameter are supported for research lookup. **Response:** array in input order, with `matched_on`, `match_type`, `match_status`, `matches` (0–1), confidence and a basic person identity. **Cost:** 1/matched identifier; redacted/unmatched free. **30 RPM**, account enablement required. [Guide](https://docs.crustdata.com/person-docs/identify/introduction.md), [OpenAPI](https://docs.crustdata.com/api-reference/person-apis/identify-people-from-profile-urls-emails-or-google-scholar-profile-urls.md)

```json
{"emails":["abhilash@crustdata.com"]}
```

`business_emails` is rejected here; batch accepts that alias. Profile/Scholar matches are exact; email resolution may be inferred from name and company domain with lower confidence. **Personal-email support conflicts across official pages; use batch for a proposal that requires it and obtain confirmation.** Do not add person IDs merely because one error message mentions them; they are not in the guide's supported-input table.

### POST /person/contact/enrich

**Input:** exactly one of profile-URL array or `business_emails` array, max 25. Optional `fields`, `verified`. Contact-only fields; no profile groups. **Response:** person match envelope containing `person_data.contact`. Email lists contain `{email,status}` with deliverable/catch_all/invalid/unknown, phones have both string and structured forms. **Enterprise**, **15 RPM**. [Guide](https://docs.crustdata.com/person-docs/contact/enrich.md), [OpenAPI](https://docs.crustdata.com/api-reference/person-apis/enrich-only-person-contact-data-from-cached-dataset.md)

```json
{
  "professional_network_profile_urls":["https://www.linkedin.com/in/dvdhsu/"],
  "fields":["contact.business_emails"],
  "verified":true
}
```

Business/personal/phone tiers cost 1/2/2 respectively; verified business emails add 0.5 when at least one survives. No base charge. Omission requests all three contact tiers (5, or 5.5 with verification). `contact.phone_numbers_info` bills the phone tier once, even if also requesting phone strings. `contact.websites` is documented at zero currently and must be explicit. `verified` affects business emails only and may return catch-all addresses. Null/no-contact billing should be confirmed against account-specific prices and fill semantics. [Contact pricing and fields](https://docs.crustdata.com/person-docs/contact/enrich.md)

## 3. Autocomplete and filter enumerations

| POST endpoint | Required / optional | Response and limits | Cost / RPM | Official source |
| --- | --- | --- | --- | --- |
| `/company/search/autocomplete` | `field`, `query`; optional `limit` | `suggestions` of indexed values/counts; empty query allowed; limit 1–100/default 20 | Free / 300 | [Guide](https://docs.crustdata.com/company-docs/autocomplete/introduction.md), [schema](https://docs.crustdata.com/api-reference/company-apis/get-autocomplete-suggestions-for-company-search-fields.md) |
| `/person/search/autocomplete` | Same keys | `suggestions`; values have counts; empty query allowed; limit 1–100/default 20 | Free / 300 | [Guide](https://docs.crustdata.com/person-docs/autocomplete/introduction.md), [schema](https://docs.crustdata.com/api-reference/person-apis/get-autocomplete-suggestions-for-person-search-fields.md) |
| `/job/search/autocomplete` | Same keys | `suggestions`; limit 1–100/default 20; empty query allowed; free-text duplicates possible | Free / 30 in guide | [Guide](https://docs.crustdata.com/job-docs/autocomplete/introduction.md), [schema](https://docs.crustdata.com/api-reference/job-apis/autocomplete-values-for-a-job-search-field.md) |
| `/professional_network/search/autocomplete` | `field`, nonblank `query`; optional `limit` | Live vocabulary; field enum industry/region/title/school; limit 1–50/default 20 | Free / RPM not stated in general table; gated | [Schema](https://docs.crustdata.com/api-reference/person-apis/get-suggestions-for-live-search-filter-values.md) |

Example bodies in the same order:

```json
{"field":"basic_info.industries","query":"tech","limit":5}
```
```json
{"field":"experience.employment_details.current.title","query":"VP","limit":5}
```
```json
{"field":"title","query":"Software","limit":5}
```
```json
{"field":"industry","query":"tech","limit":3}
```

Person/job guide observations say extra `filters` can be ignored, not applied; never use autocomplete counts as filtered audience counts. Indexed values and live values differ. Downloadable static enumerations are also linked for [companies](https://docs.crustdata.com/company-docs/filter-values.md) and [people](https://docs.crustdata.com/person-docs/filter-values.md); these are documentation assets, not invented API routes.

## 4. Job APIs

### POST /job/search

Required JSON body; `{}` is accepted. Optional `filters`, `cursor`, `limit` (0–1,000/default 20), `sorts`, `fields`, `aggregations`. **Response:** `{job_listings, next_cursor, total_count, aggregations?}`; totals may be null. **Cost:** 0.03/job; aggregation-only `limit:0` has no returned-row credits. **30 RPM**, all plans. [Guide](https://docs.crustdata.com/job-docs/search/introduction.md), [reference](https://docs.crustdata.com/job-docs/search/reference.md), [OpenAPI](https://docs.crustdata.com/api-reference/job-apis/search-the-indexed-job-dataset.md)

```json
{
  "filters":{"field":"company.basic_info.primary_domain","type":"=","value":"stripe.com"},
  "fields":["crustdata_job_id","job_details.title","job_details.url","content.description","metadata"],
  "sorts":[{"field":"crustdata_job_id","order":"asc"}],
  "limit":5
}
```

Documented aggregation schema: `type:count`, or `type:group_by` with `field`, `agg:count`, and optional `size` (1–1,000/default 100). Example:

```json
{
  "filters":{"field":"job_details.category","type":"=","value":"Engineering"},
  "limit":0,
  "aggregations":[{"type":"group_by","field":"company.basic_info.company_id","agg":"count","size":10}]
}
```

`company.basic_info.company_id` is an indexed alias; returned company IDs use `crustdata_company_id`. Grouped company buckets carry company metadata. Pagination keeps filters/sorts/fields fixed; dedupe by `crustdata_job_id`. Timestamp ranges have indexing/lifecycle caveats, not a guaranteed live vacancy feed; check the [lifecycle and date semantics](https://docs.crustdata.com/job-docs/search/reference.md#dataset-freshness-and-lifecycle). Some unsupported fields/geocoding errors are documented as 500, so distinguish schema failures from retryable outages. Employment-type examples differ in casing across pages; discover actual stored values.

## 5. Social post APIs

### POST /social_post/search

Required body; `{}` accepted. Optional filters, cursor, limit 0–1,000/default 20, sorts and fields. **Response:** `{posts, next_cursor, total_count}`. Default date-posted descending; stable cursors require unchanged query. **0.5/post**, free limit-zero counts, **30 RPM**, all plans. [Guide](https://docs.crustdata.com/social-post-docs/indexed-search/introduction.md), [reference](https://docs.crustdata.com/social-post-docs/indexed-search/reference.md), [OpenAPI](https://docs.crustdata.com/api-reference/social-post-apis/search-the-social-post-dataset.md)

```json
{
  "filters":{"field":"text","type":"[.]","value":"data warehouse"},
  "fields":["share_urn","share_url","text","date_posted","actor","engagement"],
  "limit":5
}
```

Relevant fields: post URNs/URL, text/date/type, actor/reposter, engagement, reactors, comments, mentions, hyperlinks, document/article/poll and metadata. Select `actor.location` as a whole; `actor.location.city` is filterable but not selectable. `content_type` and `materialized_at` are filter-only. `has_video` and video/image attachment classifications are currently documented as unreliable. Do not equate reacting with buying intent. [Field and current-behavior reference](https://docs.crustdata.com/social-post-docs/indexed-search/reference.md)

## 6. Web APIs

### POST /web/search/live

Required `query` (max 5,000 characters). Optional `sources`, `location` (ISO-2), `site` (max 500 chars), `start_date`/`end_date` (Unix seconds, end greater), `human_mode`, `page` (1–15/default 1). **Response:** `{success, query, timestamp, results, metadata}`; metadata includes total/failed/empty pages. **1 credit/page**, **10 RPM**, self-serve supported. [Guide](https://docs.crustdata.com/web-docs/search/introduction.md), [reference](https://docs.crustdata.com/web-docs/search/reference.md), [OpenAPI](https://docs.crustdata.com/api-reference/web-apis/web-search.md)

```json
{"query":"Crustdata funding","sources":["news"],"page":1}
```

`page:N` aggregates N pages and costs N; more than one page requires exactly one source. Source enum: web/news/scholar-articles/scholar-articles-enriched/scholar-author/ai/social. Parse by `source`; paper citations are numbers, author citations objects, and `ai` uses `content`/`references`. `site` only affects web/news, and date filters do not apply to every source. Search timestamp is milliseconds. A summary is not primary evidence; fetch its cited pages. [Source contracts](https://docs.crustdata.com/web-docs/search/reference.md#sources)

### POST /web/enrich/live

Required `urls` (1–10 protocol-prefixed URLs), optional `human_mode:false`. **Response:** top-level array of `{success,url,timestamp,title,content}` with nullable fields/error entries. **1 credit/page**, **10 RPM**, self-serve supported. [Guide](https://docs.crustdata.com/web-docs/fetch/introduction.md), [OpenAPI](https://docs.crustdata.com/api-reference/web-apis/web-fetch.md)

```json
{"urls":["https://crustdata.com"],"human_mode":false}
```

Match by URL rather than position and inspect each item even on HTTP 200. Returns HTML, not a guaranteed rendered SPA/article/PDF. Fetch timestamp is seconds. Bot protection can still fail. Do not invent a `/web/fetch/live` route.

## 7. Batch APIs

Batch access is documented as enterprise. Submit responses contain `batch_id` and `status`; poll **GET `/batch/{batch_id}`**, or supply documented `webhook_url` on submission. Completion files are generally gzipped JSONL, with five-day signed URLs. Async records do not universally have synchronous match envelopes. [Company batch guide](https://docs.crustdata.com/company-docs/enrichment/batch.md), [person batch guide](https://docs.crustdata.com/person-docs/enrichment/batch-enrich.md), [status schema](https://docs.crustdata.com/api-reference/batch-apis/get-the-status-and-download-urls-for-a-batch-job.md)

| POST endpoint | Required input; optional controls | Limit / cost / submission RPM | Relevant output and caveat | Official reference |
| --- | --- | --- | --- | --- |
| `/batch/company/search` | `filters` group; optional sorts, fields, max_results, limit_per_page, webhook_url | 10,000 results; company search price; 30 RPM | Company records; max_results above cap clamped; limit/page/preview ignored | [Schema](https://docs.crustdata.com/api-reference/batch-apis/submit-a-batch-company-database-search-job.md), [guide](https://docs.crustdata.com/company-docs/search/batch-search.md) |
| `/batch/person/search` | Same controls in person vocabulary | 10,000; person search price; 30 RPM | Person records; no public batch semantic-query contract established | [Schema](https://docs.crustdata.com/api-reference/batch-apis/submit-a-batch-person-database-search-job.md), [guide](https://docs.crustdata.com/person-docs/search/batch-search.md) |
| `/batch/company/enrich` | Exactly one company identifier type; optional fields, webhook_url, chunk_size | 10,000 identifiers; company enrich price; 30 RPM | Enriched company records; defaults retained in addition to requested fields | [Schema](https://docs.crustdata.com/api-reference/batch-apis/submit-a-batch-company-enrichment-job.md), [guide](https://docs.crustdata.com/company-docs/enrichment/batch.md) |
| `/batch/person/enrich` | professional_network_profile_urls; optional fields, webhook_url, chunk_size | 10,000; person enrich price; 30 RPM | Enriched people; chunk_size 10–1,000/default 100 | [Schema](https://docs.crustdata.com/api-reference/batch-apis/submit-a-batch-person-enrichment-job.md), [guide](https://docs.crustdata.com/person-docs/enrichment/batch-enrich.md) |
| `/batch/person/contact/enrich` | profile URLs **and nonempty fields**; optional verified, webhook_url, chunk_size | 300; same contact tiers/add-on; 5 RPM | Output shape depends on field naming style; higher documented fill rate, typically 2–3 minutes | [Schema](https://docs.crustdata.com/api-reference/batch-apis/submit-a-batch-person-contact-enrichment-job.md), [guide](https://docs.crustdata.com/person-docs/contact/batch.md) |
| `/batch/person/identify` | Exactly one of emails, business_emails, profile URLs; optional webhook_url | 300; 1/match; RPM not independently listed | Per-input match records; invalid-email row errors; `fields` rejected | [Schema](https://docs.crustdata.com/api-reference/batch-apis/submit-a-batch-person-identify-reverse-email-lookup-job.md), [guide](https://docs.crustdata.com/person-docs/identify/introduction.md) |
| `/batch/person/verify` | profile URLs; optional webhook_url | 10; 10/verdict; 5 RPM | Verdict data, confidence, flags, reasoning, coverage and citations; missing verdict omitted/free | [Schema](https://docs.crustdata.com/api-reference/batch-apis/submit-a-batch-person-verification-job.md), [guide](https://docs.crustdata.com/person-docs/verification/batch.md) |
| `/batch/job/search` | crustdata_company_ids integer array; optional fields, webhook_url | 10 companies; 0.03/job; 30 RPM | All their indexed jobs; no arbitrary filters/max_results; string IDs list rejected | [Schema](https://docs.crustdata.com/api-reference/batch-apis/submit-a-batch-job-listings-search-job.md), [guide](https://docs.crustdata.com/job-docs/search/batch-search.md) |

**Example request bodies**, in table order; each comes from or narrows the linked guide's request vocabulary:

```json
{"filters":{"op":"and","conditions":[{"field":"headcount.total","type":">","value":1000}]},"max_results":2,"fields":["basic_info.name","headcount.total"]}
```
```json
{"filters":{"op":"and","conditions":[{"field":"experience.employment_details.current.title","type":"(.)","value":"engineer"}]},"max_results":2,"fields":["basic_profile.name","basic_profile.current_title"]}
```
```json
{"domains":["stripe.com"],"fields":["basic_info.name","headcount.total"]}
```
```json
{"professional_network_profile_urls":["https://www.linkedin.com/in/dvdhsu/"],"fields":["basic_profile.name","basic_profile.current_title"]}
```
```json
{"professional_network_profile_urls":["https://www.linkedin.com/in/dvdhsu/"],"fields":["contact.business_emails"],"verified":true}
```
```json
{"emails":["abhilash@crustdata.com"]}
```
```json
{"professional_network_profile_urls":["https://www.linkedin.com/in/rishabhhq/"]}
```
```json
{"crustdata_company_ids":[6036032]}
```

Batch contact accepts either modern `contact`/`contact.*` names or legacy `business_email`/`personal_contact_info` names, never a mixture. Modern records are `{original_identifier, internal_id, data:{crustdata_person_id, contact}}`; legacy records are `{professional_network_url, person_id, business_email, personal_contact_info}`. Neither is the synchronous match envelope. `chunk_size` is 10–1,000/default 100 where supported by the submit schema. [Contact batch contract](https://docs.crustdata.com/person-docs/contact/batch.md), [submit schema](https://docs.crustdata.com/api-reference/batch-apis/submit-a-batch-person-contact-enrichment-job.md)

Verification results include `data.verdict`, confidence, reasoning, flags, coverage and citations (`url`, `title`, `cited_text`). Verdicts: clearly_genuine/probably_genuine/cannot_verify/probably_fabricated/clearly_fabricated/reclassified_employment/non_person. Coverage can reveal missing posts or unresolved coworkers. This API is separately enabled. [Verification output](https://docs.crustdata.com/person-docs/verification/batch.md)

### Batch status and listing

| GET endpoint | Parameters / example request | Response / restrictions | Official source |
| --- | --- | --- | --- |
| `/batch/{batch_id}` | Required job ID; `GET /batch/53ab686b-c054-496b-8baf-baff5ecc85cf` | pending → processing → completed/failed; details include entity/action/counts/timestamps/error, `download_url`, `download_urls`, and contact fill_counts when applicable | [Status](https://docs.crustdata.com/api-reference/batch-apis/get-the-status-and-download-urls-for-a-batch-job.md) |
| `/batch/` | Optional status, limit 1–100/default 20 (clamped), cursor; `GET /batch/?status=completed&limit=2` | `{jobs,next_cursor,has_more}`; summaries omit download links; preserve the documented trailing slash | [List](https://docs.crustdata.com/api-reference/batch-apis/list-batch-jobs-for-the-authenticated-account.md) |

Polling/metadata are not the per-record charge; work bills at completion. Exact status/list RPM and metadata billing should be confirmed because the general rate table does not separately list these routes. Credit gates can account for committed running work; do not equate a successful submission with a free completed job. [Credit commitments](https://docs.crustdata.com/general/credits.md#batch-jobs)

Concurrency: two independent live/standard pools, **five active jobs each by default**. Cap = highest endpoint RPM in that pool divided by six, constrained to 5–30. Pending/processing jobs count; jobs active for over 24 hours stop counting. Live pool includes contact, identify and verify; standard includes indexed person/company search/enrich and job search. Account-pool or platform-wide capacity failures return 429/Retry-After; a preflight concurrency rejection does not bill. [Concurrency rules](https://docs.crustdata.com/general/rate-limits.md#batch-job-concurrency)

## 8. Watch APIs

### Creation contracts

| POST endpoint | Required body | Price per newly delivered record, indexed tier | Official source |
| --- | --- | --- | --- |
| `/watch/company/search` | filters, config, notifications | 2/company | [Company discovery](https://docs.crustdata.com/watcher-docs/company/discovery.md), [create schema](https://docs.crustdata.com/api-reference/watch-apis/create-a-discovery-watch.md) |
| `/watch/person/search` | Same, person vocabulary | 0.5/person | [Person discovery](https://docs.crustdata.com/watcher-docs/person/discovery.md) |
| `/watch/job/search` | Same, job vocabulary | 0.5/job | [Jobs](https://docs.crustdata.com/watcher-docs/job/watch.md) |
| `/watch/social_post/search` | Same, social vocabulary | 2/post | [Social](https://docs.crustdata.com/watcher-docs/social-post/discovery.md) |
| `/watch/person` | entities, track, config, notifications | 5/changed person at 30-day freshness | [Person entity](https://docs.crustdata.com/watcher-docs/person/entity.md), [create schema](https://docs.crustdata.com/api-reference/watch-apis/create-an-entity-watch.md) |
| `/watch/company` | Same; company identifiers can mix inside entities | 5/changed company, 30-day only | [Company entity](https://docs.crustdata.com/watcher-docs/company/entity.md) |

Optional `fields` selects delivered record data. `config.trigger` is `{type:"interval",every_hours:N}` with integer N ≥ 1. Config also supports max_results_per_run (1–10,000/default 25), preferred_hour (UTC 0–23), expires_at (YYYY-MM-DD), payload_delivery_type (inline/link). More than 1,000 requires link mode. `notifications:[]` is a valid pull-only mode. Create returns full watch definition/id/status/timestamps/usage counters; first execution establishes baseline. [Create discovery](https://docs.crustdata.com/api-reference/watch-apis/create-a-discovery-watch.md), [entity](https://docs.crustdata.com/api-reference/watch-apis/create-an-entity-watch.md)

Example company discovery body:

```json
{
  "filters":{"field":"headcount.total","type":"=>","value":200},
  "config":{"trigger":{"type":"interval","every_hours":24},"max_results_per_run":25},
  "notifications":[]
}
```

Example person entity body:

```json
{
  "entities":{"professional_network_profile_urls":["https://www.linkedin.com/in/sherryrobinson"]},
  "track":{"field":"experience.employment_details.current","type":"added"},
  "config":{"trigger":{"type":"interval","every_hours":24},"max_results_per_run":100},
  "notifications":[]
}
```

Company entity variant: `entities:{"domains":["stripe.com"]}` and `track:{"field":"headcount.total","type":"changed"}` with the same config/notifications. Entity `changed` applies to scalars, `added` to arrays, comparisons trigger false→true; optional `keys` define identity for additions only. [Entity tracking](https://docs.crustdata.com/watcher-docs/company/entity.md#what-you-can-track)

### Management and run history

Replace `{dataset}` only with supported discovery datasets (company/person/job/social_post), or entity datasets (company/person). `{id}`/`{watch_id}` placeholders denote the saved watch ID, not a company/person ID. Management is 10 RPM per watch path budget. No watch was created or tested during this research.

| Method / path | Input, response and caveat | Official source |
| --- | --- | --- |
| `GET /watch/{dataset}/search` | Optional status/limit/offset; bare array of discovery definitions/counters | [List discovery](https://docs.crustdata.com/api-reference/watch-apis/list-your-discovery-watches.md) |
| `GET /watch/{dataset}/search/{id}` | Required ID; one owned definition | [Get discovery](https://docs.crustdata.com/api-reference/watch-apis/get-one-discovery-watch.md) |
| `PATCH /watch/{dataset}/search/{id}` | Only status/config/notifications mutable; repeat config.trigger in config patches | [Update discovery](https://docs.crustdata.com/api-reference/watch-apis/pause-resume-or-reconfigure-a-discovery-watch.md) |
| `DELETE /watch/{dataset}/search/{id}` | Terminal cancellation, idempotent 204 | [Cancel discovery](https://docs.crustdata.com/api-reference/watch-apis/cancel-a-discovery-watch.md) |
| `POST /watch/{dataset}/search/{id}/test` | Optional count 1–25, notification_endpoint, deliver; sample of current matches, free; deliver:false returns without sending | [Test discovery](https://docs.crustdata.com/api-reference/watch-apis/send-a-test-notification-from-a-discovery-watch.md) |
| `GET /watch/{dataset}` | Optional status/limit/offset; bare entity-watch array | [List entity](https://docs.crustdata.com/api-reference/watch-apis/list-your-entity-watches.md) |
| `GET /watch/{dataset}/{id}` | One entity-watch definition | [Get entity](https://docs.crustdata.com/api-reference/watch-apis/get-one-entity-watch.md) |
| `PATCH /watch/{dataset}/{id}` | status/entities/config/notifications; track/fields immutable; newly added entities silently baselined | [Update entity](https://docs.crustdata.com/api-reference/watch-apis/edit-the-watched-list-pause-or-reconfigure-an-entity-watch.md) |
| `DELETE /watch/{dataset}/{id}` | Terminal cancellation, idempotent 204 | [Delete entity](https://docs.crustdata.com/api-reference/watch-apis/delete-an-entity-watch.md) |
| `POST /watch/{dataset}/test` | Unsaved track/fields → sample envelope; count 1–25, optional deliver:false; notification_endpoint required if delivering | [Preview entity](https://docs.crustdata.com/api-reference/watch-apis/preview-a-notification-before-creating-an-entity-watch.md) |
| `POST /watch/{dataset}/{id}/test` | Optional public notification_endpoint, fields, count 1–25, deliver; metadata.test true; free | [Test entity](https://docs.crustdata.com/api-reference/watch-apis/send-a-test-notification-from-an-entity-watch.md) |
| `GET /watch/{dataset}/{watch_id}/runs` | Required watch ID; cursor/limit pagination of recent runs | [List runs](https://docs.crustdata.com/api-reference/watch-apis/list-a-watchs-runs.md) |
| `GET /watch/{dataset}/{watch_id}/runs/{run_id}/summary` | Counts, activity log, delivery attempts and records | [Run summary](https://docs.crustdata.com/api-reference/watch-apis/get-one-run-with-the-records-it-delivered.md) |

Examples: `PATCH /watch/person/123` with `{"status":"paused"}`; `PATCH /watch/company/search/123` with `{"config":{"trigger":{"type":"interval","every_hours":24},"max_results_per_run":25}}`; `POST /watch/person/123/test` with `{"count":2,"deliver":false}`. IDs are placeholders. Unsaved person preview example (`POST /watch/person/test`), based on its linked schema:

```json
{"track":{"field":"basic_profile.current_title","type":"changed"},"fields":["basic_profile"],"count":1,"deliver":false}
```

Run-history routes omit the discovery `/search` segment. A summary stores record envelopes under `notifications[].payload.notifications[]`; delivered channel payloads distinguish discovery `results` from entity changes/record structures. Link mode uses `metadata.payload_delivery`; parse its type because file-write failures can fall back inline. NDJSON links last five days and run-summary reads can refresh them. Inline chunks can split at about 1 MB/100 records; persist notification IDs for deduplication. Entity webhook signatures use HMAC-SHA256 with `x-crustdata-signature`; secret provisioning/retries need confirmation. [Run summary](https://docs.crustdata.com/api-reference/watch-apis/get-one-run-with-the-records-it-delivered.md), [payload delivery](https://docs.crustdata.com/watcher-docs/payload-delivery.md), [entity test signatures](https://docs.crustdata.com/watcher-docs/person/entity.md#smoke-test-your-webhook)

### Watch restrictions and freshness prices

- Indexed discovery creation rejects baseline sets above 500,000. Cross-dataset narrowing can cover at most one million company IDs. Joins support existence, not cross-dataset counting/negative existence; lifetime dedupe suppresses re-entry. [Join contract](https://docs.crustdata.com/watcher-docs/cross-dataset-filters.md)
- Discovery first runs are free samples up to five and mark existing matches handled. Entity first runs are free snapshots/sample with empty changes. Empty subsequent runs are free. [Company discovery](https://docs.crustdata.com/watcher-docs/company/discovery.md), [person entity](https://docs.crustdata.com/watcher-docs/person/entity.md)
- Person entity tiers: 30/14/7/3/1-day freshness cost 5/10/20/50/150 per changed person. Company entity supports 30 days only. Schedule frequency is independent of data freshness. [Person tiers](https://docs.crustdata.com/watcher-docs/person/entity.md#data-freshness), [company](https://docs.crustdata.com/watcher-docs/company/entity.md)
- Live discovery uses `config.is_realtime:true`, required `realtime_filters`, optional top-level `narrowing_filters`, no indexed `filters` and no custom sorts. It costs **150/new record**, all datasets, and every_hours must be ≥24. Discovery rejects refresh_frequency_days as input. Mode/filter changes require a new watch. [Company live rules](https://docs.crustdata.com/watcher-docs/company/discovery.md#realtime-watches), [person](https://docs.crustdata.com/watcher-docs/person/discovery.md#realtime-watches), [jobs](https://docs.crustdata.com/watcher-docs/job/watch.md#realtime-watches), [social](https://docs.crustdata.com/watcher-docs/social-post/discovery.md#realtime-watches)

### Live discovery filter families

These describe **watch creation**, not a verified body for direct live search. Live trees permit a restricted AND shape and OR alternatives on one field, not arbitrary nested indexed logic. Additional indexed constraints belong in the allowed narrowing block. [Realtime watch contract](https://docs.crustdata.com/watcher-docs/company/discovery.md#realtime-watches)

| Dataset | Main supported criteria | Distinct restrictions and narrowing | Official field tables |
| --- | --- | --- | --- |
| Person | Current/past titles and employers; seniority; current employer size/industry/HQ country; person country/state/city; tenure; headline/summary; names; school; selected signals | Tenure only at documented bucket edges; signal flags accept true only; recently_posted/mentioned_in_news are live-watch-only. At most 10,000 people before narrowing. Narrowing: person or company, one block | [Person realtime fields](https://docs.crustdata.com/watcher-docs/person/discovery.md#filter-fields-the-live-person-search-accepts) |
| Company | Industry/HQ/country/size; Fortune rank; headcount and followers at bucket edges; annual growth/department headcount; revenue bounds; leadership-change flag; funding | HQ with included country is restricted; city/state are not live fields. **Any funding field makes the realtime_filters tree funding-only and answered by the company index**; move other criteria to narrowing. At most 10,000 before narrowing. Narrowing: company only | [Company realtime fields](https://docs.crustdata.com/watcher-docs/company/discovery.md#filter-fields-the-live-company-search-accepts) |
| Job | Title/description keyword; workplace/employment type; geography; employer industry/name/network ID | One keyword expression; fixed workplace/employment enums; name resolution can cover multiple companies, at most 300 employers per condition. No match-count cap at creation. Narrowing: company only | [Job realtime fields](https://docs.crustdata.com/watcher-docs/job/watch.md#filter-fields-the-live-job-search-accepts) |
| Social post | Text, five relative date windows, author industry; downstream actor type/company URL and classification category/intent | Date lower bounds: now-24h/now-7d/now-1M/now-3M/now-1y. No creation match-count cap. Narrowing: person or company, one block | [Social realtime fields](https://docs.crustdata.com/watcher-docs/social-post/discovery.md#filter-fields-the-live-post-search-accepts) |

For person tenure, supported lower edges are 0/1/3/6/11 and upper edges 0/2/5/10; start dates use whole-year date math with age semantics, not arbitrary dates. Live watch employment enums include full_time/part_time/contract/temporary/intern/volunteer/other. Obtain exact supported department/seniority values from the linked tables; do not substitute ordinary indexed values without checking. Company funding's indexed execution is a material freshness exception to the “realtime” label.

Live job fields outside the accepted list, such as category/salary/experience-level criteria, cannot be recovered by narrowing the not-yet-indexed posting; only its employer can be narrowed. [Job narrowing rules](https://docs.crustdata.com/watcher-docs/job/watch.md#what-goes-in-narrowing_filters)

## 9. Agent Search API, beta

| Route | Required input and example | Response / behavior | Official source |
| --- | --- | --- | --- |
| `POST /agent/searches` | `{"query":"The founders of Crustdata"}`; query 1–10,000 chars, no NUL, no extra keys; optional Idempotency-Key header | New search 202 with search_id/state; same key+query gives existing search/200; differing query gives 409 | [Start](https://docs.crustdata.com/api-reference/agent-search-apis/start-an-agent-search.md) |
| `GET /agent/searches/{search_id}` | Required ID; `GET /agent/searches/SEARCH_ID` | State/query/created_at/output/credits_used/error; first terminal read can bill | [Read](https://docs.crustdata.com/api-reference/agent-search-apis/read-an-agent-search.md) |
| `GET /agent/searches/{search_id}/events` | Required ID; optional `after` sequence or Last-Event-ID; Accept can request SSE | JSON `{search_id,events}` or stream; resume after cursor | [Events](https://docs.crustdata.com/api-reference/agent-search-apis/read-the-events-of-an-agent-search.md) |
| `POST /agent/searches/{search_id}/cancel` | Required ID; no invented cancellation options | Stops running search; cancellation costs zero | [Cancel](https://docs.crustdata.com/api-reference/agent-search-apis/cancel-an-agent-search.md) |

Output contains optional person/company/job tables with constraints, dynamically chosen columns and rows, row values and per-constraint assessments/evidence/field paths. The column keys are **not a fixed CRM schema**. States succeeded/failed/cancelled are terminal; running and future queued are not. SSE can also start via POST Accept:text/event-stream; terminal `search.finished.data.search` has the final search object. Disconnecting is not cancelling. [Overview/output contract](https://docs.crustdata.com/agent-search-docs/overview.md)

Access requires Agent Search **and all three search endpoints**, not merely the requested dataset. Runs can take tens of seconds to minutes; the guide's 19–39-second tests are examples, not an SLA. Six starts/minute; shared 300 RPM for reads/events/cancel; stream concurrency can return Retry-After:5. Balance must cover 8 credits per uncharged search including the new one; this is an admission check, not the price. Costs split into agent_cost/search_cost/enrich_cost/contact_cost/total_cost; first terminal read or completed stream charges once. Failed/cancelled/empty searches cost zero. **A GET is therefore not universally nonbillable.** No documented request-level maximum-cost setting. [Overview](https://docs.crustdata.com/agent-search-docs/overview.md), [rate rules](https://docs.crustdata.com/general/rate-limits.md)

## 10. Account APIs

All six routes below are documented free and read-only; none was called. Every request still requires bearer/version headers. Account permissions can be narrowed per API key and by fields; an enabled product does not imply all premium fields.

| GET route | Parameters / example | Relevant response | RPM / source |
| --- | --- | --- | --- |
| `/account/endpoints` | Optional path exact match, category case-insensitive, status enabled/disabled; `?path=/company/enrich` | api_version, token_limit_rpm, endpoints with status, fields.enabled/disabled, effective_rate_limit_rpm, base_credits, premium_filters/fields/modes | 300; [guide](https://docs.crustdata.com/general/permissions.md), [schema](https://docs.crustdata.com/api-reference/account-apis/list-endpoint-permissions-and-rate-limits.md) |
| `/account/credits` | No body; `GET /account/credits` | account.credits, recurring_credits, frequency/refresh date; optional wallets/topups | 300; [guide](https://docs.crustdata.com/general/credits.md), [schema](https://docs.crustdata.com/api-reference/account-apis/get-account-credit-balance.md) |
| `/account/usage/summary` | start/end, group_by, bucket and filters; `?group_by=day,product&bucket=1h` | Aggregated requests/credits/errors/results; component grouping changes metrics | Shared 60; [schema](https://docs.crustdata.com/api-reference/account-apis/get-a-usage-summary.md) |
| `/account/usage/events` | Time/usage filters, limit 1–500/default 100, cursor, hide_free; `?limit=10` | events, next_cursor, has_more; individual charge components | Shared 60; [schema](https://docs.crustdata.com/api-reference/account-apis/list-usage-events.md) |
| `/account/usage/events/{request_id}` | Required request ID; `GET /account/usage/events/REQUEST_ID` | Request body/query/path, redacted headers, response error and charge data | Shared 60; [schema](https://docs.crustdata.com/api-reference/account-apis/get-one-usage-event.md) |
| `/account/usage/errors` | Time window, api_key_ids/endpoints and error-group filters per schema; `?start=2026-11-18&end=2026-11-19` | Groups of failures; request/account/server/no_results kinds | Shared 60; [schema](https://docs.crustdata.com/api-reference/account-apis/list-usage-errors.md) |

Usage windows default to seven days ending at coming midnight UTC, at most 12 months old, start inclusive/end exclusive. Dimensions include day/product/endpoint/component/api_key_id/client_surface/client_platform/status_class. Some daily component combinations/status filters require hourly bucket fallback. Client platform can be grouped but not filtered. Treat the usage guide's “company identify is free” hide_free example as a documentation conflict, not proof of zero cost. [Usage guide](https://docs.crustdata.com/general/usage.md)

## 11. Known routes with gated or incomplete public schemas

These paths are explicitly named in official docs. Their existence, listed prices and defaults are documented, but the gated linked guide bodies redirected to a sign-in page during this review. **Do not invent requests/responses or reuse indexed schemas.** No working example can responsibly be supplied until access is granted.

| Route (POST where stated in introduction) | Publicly documented capability / list price / default RPM | Schema evidence / limitation |
| --- | --- | --- |
| `/company/professional_network/search/live` | Fresh company search; 2/company; 10 RPM | [API introduction](https://docs.crustdata.com/openapi-specs/2025-11-01/introduction.md), [gated guide](https://docs.crustdata.com/company-docs/search/live-search.md) |
| `/person/professional_network/search/live` | Fresh people search; 2/profile; 10 RPM | [Introduction](https://docs.crustdata.com/openapi-specs/2025-11-01/introduction.md), [gated guide](https://docs.crustdata.com/person-docs/search/live-search.md) |
| `/person/professional_network/enrich/live` | Fresh profile retrieval; 7/profile; 10 RPM | [Introduction](https://docs.crustdata.com/openapi-specs/2025-11-01/introduction.md), [gated guide](https://docs.crustdata.com/person-docs/enrichment/live-enrich.md) |
| `/job/professional_network/search/live` | Jobs for one company; 2/result; 10 RPM | [Introduction](https://docs.crustdata.com/openapi-specs/2025-11-01/introduction.md), [gated guide](https://docs.crustdata.com/job-docs/search/live-search.md) |
| `/social_post/professional_network/search/live` | Live keyword posts; 1/post +5 per 100 reactors +5 per 100 comments, per post; 10 RPM | [Pricing](https://docs.crustdata.com/general/pricing.md), [gated search](https://docs.crustdata.com/social-post-docs/search/introduction.md) |
| `/social_post/professional_network/enrich/live` | Recent posts by person/company; same live-post pricing; 10 RPM | [Pricing](https://docs.crustdata.com/general/pricing.md), [gated enrich](https://docs.crustdata.com/social-post-docs/enrichment/introduction.md) |
| `/dev_platform/enrich` | Developer platform data; 1/result; 15 RPM | [Pricing](https://docs.crustdata.com/general/pricing.md), [gated guide](https://docs.crustdata.com/person-docs/dev_platform/introduction.md); method/body not established by a public dedicated reference here |
| `/employee_review/enrich` | Employee reviews; 1/company; 15 RPM | [Pricing](https://docs.crustdata.com/general/pricing.md), [CLI capability](https://docs.crustdata.com/for-agents/cli.md); dedicated schema not found in index |
| `/batch/company/professional_network/search/live` | Up to 1,000 companies; 2/company; 5 RPM | [Company batch guide](https://docs.crustdata.com/company-docs/search/batch-search.md) |
| `/batch/person/professional_network/search/live` | Up to 1,000 profiles; 2/profile; 5 RPM | [Person batch guide](https://docs.crustdata.com/person-docs/search/batch-search.md) |
| `/batch/person/professional_network/enrich/live` | Up to 300 profiles; 7/profile; 5 RPM | [Person batch guide](https://docs.crustdata.com/person-docs/enrichment/batch-enrich.md) |
| `/batch/job/professional_network/search/live` | Live listings for up to 10 companies; 2/result; 5 RPM | [Job batch guide](https://docs.crustdata.com/job-docs/search/batch-search.md), [pricing](https://docs.crustdata.com/general/pricing.md) |
| `/batch/social_post/professional_network/enrich/live` | Batch recent-post retrieval; live-post rates; 5 RPM | [Pricing](https://docs.crustdata.com/general/pricing.md), [rate list](https://docs.crustdata.com/general/rate-limits.md); public input cap/schema not verified |

Gated company/person live access is enterprise/add-on; social live and specialist access also require grants. Web live is the documented self-serve exception. Shared live autocomplete has its own verified public schema above. Watcher realtime filter syntax is not proof of the direct live endpoint request body.

## 12. Credit model and budget examples

Standard list prices, not dollar amounts or a quote for a hackathon key. Per-account permissions prices override list prices; watcher prices come from the builder/team, not `/account/endpoints`. [Pricing](https://docs.crustdata.com/general/pricing.md), [account-price schema](https://docs.crustdata.com/general/permissions.md#how-to-read-the-prices)

| Search premium group | Person filter / receive per returned result | Company filter / receive per returned result |
| --- | --- | --- |
| Base | 0.03 / included | 0.03 / included |
| Experience, education, skills | 0.1 / 0.1 each | N/A |
| Certifications, honors, professional network | 0.2 / 0.2 each | N/A |
| Summary | response only 0.2 | N/A |
| Basic developer data / repositories | 0.8 / 0.8 or 2.5 / 2.5; higher unit for repository group | N/A |
| Research profiles | 0.2 / 0.2 | N/A |
| Taxonomy | N/A | 0.1 / 0.1 |
| Followers, headcount, funding, hiring, software reviews, maps | N/A | 0.2 / 0.2 each |
| Technographics | N/A | 1 / unavailable in search response |

Source: [premium search prices](https://docs.crustdata.com/general/pricing.md#premium-fields-in-search), with endpoint-specific examples in [person search](https://docs.crustdata.com/person-docs/search/introduction.md) and [company search operation](https://docs.crustdata.com/api-reference/company-apis/search-companies-with-indexed-fields-only.md). A group is charged once per side however many of its paths are requested; null premium groups are documented as not billed. Sorting is free. Fields can be granted free on particular accounts.

**Illustrative arithmetic, not measured spend:** 20 base-only person results cost 0.6. Filter and receive experience on all 20: `20 × (0.03+0.1+0.1) = 4.6`. Enrich five selected profiles at base: +5. Fetch three public pages: +3. Total 12.6, excluding any optional contacts, other premium filters, provider/model costs and retries. A 10-record daily discovery delivery costs 1,500 at the published live watcher tier; the same count of indexed company notifications costs 20. These comparisons motivate selective retrieval, not a production cost guarantee.

Purchased credits normally expire after 12 months; granted credits can have custom expiry. Per-key monthly caps reset on the first UTC day of a month. Account balances are shared across keys; negotiated prices and key restrictions must be checked later. [Credits](https://docs.crustdata.com/general/credits.md)

## 13. MCP and dashboard boundaries

MCP server: `https://install.crustdata.com/mcp`, OAuth or `Authorization: Bearer` for programmatic clients. Its exact live tool catalog is an authenticated MCP resource, **not a REST endpoint we can derive**. Read `crustdata://catalog` then tools/query-builder/fields/patterns/cost/dry-run before coding. Public resource index and workflow summaries are in [CRUSTDATA_CAPABILITIES.md](CRUSTDATA_CAPABILITIES.md). [Official MCP](https://docs.crustdata.com/for-agents/mcp.md)

Dashboard Data Export has **no API**, distinct CSV/JSONL behavior, access roles and export terms. Do not invent `/export`, scheduling, CRM-write or outbound-email routes. [Export contract](https://docs.crustdata.com/export-docs/data-export.md)
