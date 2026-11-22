# Chat intake and top-k company discovery — validation, 2026-11-22

## What exists

- **Web UI** (`vendor-review-web`, FastAPI): the chat intake asks follow-up questions. A live "Buyer brief" panel shows the requirements and a completeness ring. "Start vendor search" stays disabled until required fields are filled, then opens an approval dialog before anything is spent.
  - Restored from the `harshal` GitHub Desktop stash; the stash itself is kept.
  - The chat intake lives in `chat_intake.py`, so V1's `intake.py` is unchanged.
- **Discovery** (`src/vendor_review/discovery.py`, plug-in `DISCOVERY=vendor_review.discovery:CrustdataDiscovery`):
  1. Writes a short product-focused query from the brief: category, purpose and up to 4 must-haves. Budget, integration product names, locations and deployment are left out of retrieval.
  2. Reads canonical `basic_info.employee_count_range` labels from the documented-free `/company/search/autocomplete`. Labels are never guessed. The live labels included `myself only` and `501-1000`.
  3. Runs one ranked `/company/search` (hybrid) for a pool of `DISCOVERY_POOL` results (default 12), with free hard filters:
     - size at least `DISCOVERY_MIN_EMPLOYEES` (default 51)
     - `year_founded =<` the current year minus `DISCOVERY_MIN_AGE_YEARS` (default 3)
  4. Reranks the pool locally by a transparent **discovery fit** and keeps the top k (default 4). The score is: 0.5 × must-have/category term coverage in the indexed description, 0.25 × size, 0.15 × age, and 0.10 × a mention of the buyer's region.
     - It is a shortlist heuristic, not requirement evidence. V1 decides support.
- Discovery tools are dispatch-only: they are not offered to the V1 model. Every call goes through the same account pricing, ledger and credit caps as V1.
- Contract: [company search reference](https://docs.crustdata.com/company-docs/search/reference.md) and [autocomplete](https://docs.crustdata.com/company-docs/autocomplete/introduction.md). Filter operators `in`, `=<` and an `op: and` group are documented. Results carry no relevance score.

## Trial user (synthetic; real Gemini intake and real Crustdata calls)

The trial user was a mid-size Indian 3PL with 6 multi-client warehouses wanting a WMS:
- Must-haves: multi-tenant operations, per-client billing, barcode/RF scanning, wave/batch picking, GST e-invoicing.
- Integrations: Tally, SAP Business One, Shopify, Unicommerce.
- Budget ₹1.5–3 lakh per month (flexible); data hosted in India; live in 4 months.

Intake took three user answers to reach a 93%-complete brief. Geography kept the three states but dropped "India".

| Run | Query / filters | Result | Credits |
|---|---|---|---|
| 1 (before the fix) | Long query built from the whole brief; no filters; 4 results | iQuore (11–50, 2022), Simext (11–50, 2005), Waretic (2–10, 2026), Deliver WMS (2–10, 2025) | 0.12 |
| 2 (after the fix) | Short query; size ≥51; founded ≤2023; **pool 4** (allowance limit) | SphereWMS (51–200, 2001, US), Palms WMS (51–200, 2001, Karnataka), JASCI (51–200, 2015, US), Invar Systems (51–200, 2005, US) | 0.12 + free autocomplete |

| 3 (full design, new 1-credit allowance) | Fixed short query; size ≥51; founded ≤2023; **pool 12**, reranked | SphereWMS (fit 0.48, US), Palms WMS (0.45, Karnataka), Brilliant Info System (0.45, Pune; provider rank #11), JASCI (0.42, US) | 0.36 |

Run 3 pool, in provider order:
- JASCI
- Palms
- SphereWMS
- Apport (DK)
- Invar
- QStock
- Microlistics (AU)
- Logimax (201–500)
- Foxfire
- SAGA (BR)
- Brilliant (IN)
- AC2 WAVE (SG)

What run 3 shows:
- All 12 are WMS specialists founded 1985–2015, so the filters work.
- Fit scores cluster between 0.36 and 0.48. Must-have coverage is low everywhere, between 0.125 and 0.375, because indexed descriptions are short marketing text. The 0.10 region signal therefore decides several places; both Indian HQs entered the top 4 through it.
- Brilliant's description is thin. Ties are broken by provider rank.
- Large or broad vendors (multi-product or enterprise suites) did not appear. Semantic search over company descriptions favours pure-play WMS firms.
- Discovery gives a sound **shortlist of real candidates**, not a proven "best 4". V1's evidence review is what can separate them.

Run 2 removed the tiny and brand-new firms. It is **not yet a full validation of "best 4"**:
- The pool was 4, so reranking only reordered the same four companies.
- All four fall in the 51–200 band, so larger vendors may rank lower in retrieval and need the default pool of 12.
- Run 2 also exposed a query glitch ("vendor for and to manage"). It is fixed and covered by a test, but that fix has not been rerun live.

## V1 connected to the search flow (built; live run pending an allowance)

- `src/vendor_review/v1runner.py` (`V1_RUNNER=vendor_review.v1runner:V1Agent`) runs the real V1 LangGraph agent for each shortlisted company:
  - It writes one buyer message stating every question and constraint, then builds V1's brief from it. V1's own grounding and readiness checks pass with no model intake step and no invented wording. Missing constraints stay explicit "unknown".
  - Each vendor gets its own thread, ledger session and Crustdata cap: `SEARCH_CREDITS / k`, never more than `SESSION_CREDITS`.
  - Findings map back to answers conservatively. Vendor-documented findings count as `supported` only with an exact captured passage, and that attribution is kept in the summary. Each vendor also gets its own HTML dossier.
- Vendors are evaluated **in parallel** (`V1_PARALLEL`, default 4). Each worker has its own SQLite connections and API client. With 1 worker, a crash stops the run immediately; completed vendors are never re-run.
- "Evaluate N vendors with V1" (`POST /api/sessions/{sid}/search/evaluate`) evaluates an existing shortlist without repeating discovery. The run 3 shortlist can therefore be evaluated without paying for discovery again.
- V1 step-repeat bug: fixed. The model now sees a `completed_this_turn` list of earlier steps, so trimming context after a save no longer makes it restart.
- Tests: 124 pass, including a full scripted V1 run for one candidate and a parallelism test. These are synthetic fixtures, not live validation.

## Live V1 run on the run 3 shortlist (20-credit Crustdata allowance)

**Attempt history, all live:**
1. All four reviews failed with Gemini free-tier `429 RESOURCE_EXHAUSTED`. The provider's message gave the limit as 15 generate requests per minute; four agents exceeded it.
2. After adding a shared pacer, the retry exposed an adapter bug: a reused preflight key returned a cached result without loading account access, so every paid tool was refused. It spent 0 credits.
3. Next, model-quality failures: rejected citations, schema errors and heading quotes. Exhausted per-thread token and tool limits left 0 saved findings across all four vendors.

**Fixes, all covered by tests (137 pass):**
- Shared model pacing at 12 requests per minute, plus one bounded retry on a provider 429.
- A fresh preflight key per attempt.
- Per-finding saving: valid findings are kept and rejected ones are returned with reasons.
- A free `find_passages` tool that returns verbatim sentences from captured pages, skipping menu headings.
- A validator rule that a heading is not a statement of capability.
- Slimmer page views in the model context, and a byte/3 token reservation.
- A fetch-first prompt.
- `completed_this_turn` progress, so the model doesn't repeat finished steps.
- New attempt threads for worn-out vendors: they carry captures and findings forward and are capped at the vendor's remaining allowance, with at most 3 attempts.
- A free closing turn that records explicit `cannot_verify` for any unanswered requirement.

**Free replay check:** the fixed V1 ran over saved captures with a 0-credit cap. Brilliant got 13/13 findings (3 vendor-documented, 2 partial, 8 cannot verify), SphereWMS 13/13, Palms 11/13.

**Final run:** all four reviews completed, and every requirement has an explicit verdict. Results were re-mapped from the saved V1 states under the heading rule.

| Vendor | Critical requirements supported | Supported, with exact vendor quote | Credits (all attempts) |
|---|---|---|---|
| Brilliant Info System | 3/10 | multi-client operations, per-client billing, barcode/RF scanning; wave/batch picking partial | 3.2 |
| SphereWMS | 0/10 | its only "supported" claim cited a menu heading, now treated as cannot verify | 4.2 |
| Palms WMS | 0/10 | nothing admissible on the captured pages | 4.2 |
| JASCI Software | 0/10 | no vendor page was ever fetched; searches only | 4.2 |

- Comparison: **"Cannot verify that any vendor meets every must-have."** Closest is Brilliant, 3/10 critical requirements supported. No supplier recommendation is made.
- Not verified for any vendor: GST e-invoicing, the Tally, SAP Business One, Shopify and Unicommerce integrations, coverage of the buyer's states, client portal, dock scheduling and pricing.
- V1 spend: **15.8 of the 20-credit allowance**; 4.2 remain. Gemini was free tier.
- Most credits went on searches and failed attempts before the fixes. Each vendor's per-thread cap held throughout.

## Why three vendors got weak results, and the fixes (built; live rerun not yet funded)

**Diagnosis, from the ledger and captures:**
- JASCI never had a vendor page read: 21 search attempts, most refused or returning redirect links, and both fetches refused.
- SphereWMS's only fetch was a help-site table of contents.
- Palms' product page on the parent domain (technoforte.co.in) was rejected as "wrong domain".
- Brilliant succeeded because its own product pages were read directly.
- **58 of 77 saved search results (75%) were opaque `google.com/goto?` links.**
- V1 used **no** people or post data in these runs: the prompt deferred both branches unless budget remained, and none did.

**Fixes (141 tests pass):**
- **Pre-fetch.** Before the model starts, the adapter resolves identity, fetches the vendor's home page and its two most relevant linked product, integration or pricing pages, skipping blog, careers and legal pages. About 3.2 credits, all through the priced, ledgered client.
- **Related official domains.** Admitted only when listed by Crustdata, or both linked from the vendor's own page and named in its indexed name or description. This would admit Palms' Technoforte page; it would not admit social or partner links.
- Redirect search results are dropped, and the prompt allows at most one search.
- **People pass.** If at least 1.2 credits remain: one Crustdata people search (limit 2) plus one original-post read. A professional reference is registered only for an authored post relevant to a requirement.
- A refused preflight (allowance used up) no longer aborts the review. Local review of captures and the closing turn still run.

**Free check on saved data:**
- On Brilliant's home page, the pre-fetch would pick `warehouse-management.html` and `e-commerce-integration.html`.
- Palms' Crustdata description names Technoforte, so the related-domain rule applies once `onpalms.com` is fetched and shows the link. That link is not yet confirmed.

## Demo trial: shipping aggregator for an Indian D2C brand (20-credit allowance)

**Run 1, live: 0.36 discovery + 15.72 V1.**
- Discovery returned mostly US, Canadian and European shipping tools. Only 2 of the 12 were Indian, because the query had no market and the region signal never matched "Pan-India".
- The top 4 were Logistyx, Easyship, Descartes ShipRush and Shipmozo. Easyship led with 3/10; the verdict named it the leading candidate, with no recommendation.
- Shipmozo's review captured its home, features and channel-integration pages, but hit the 20-tool-call cap after 24 free `find_passages` lookups. Its `record_findings` call was refused, so the review saved nothing.

**Fixes (147 tests pass):**
- Free local lookups (`find_passages`, `read_evidence`) are recorded but no longer use up tool-call caps.
- `find_passages` accepts `requirement_ids` for one batched lookup.
- The buyer's market is turned into a country: "Pan-India" or Indian states map to India; ambiguous mixes get no country.
- The query names that market, and the pool is local-first: about 2/3 of slots filtered to companies HQ'd in the market country (documented `locations.country` ISO-3 filter), the rest global. Same total results and price.
- The region score matches the country; region weight raised to 0.2.

**Discovery rerun, live, 0.36 credits:** all 8 unique companies are Indian shipping aggregators: Pickrr, Prozo, Shyplite, Shipmozo, eShipz, ShipGlobal.in, RapidShyp and Ecomgistics. The global half duplicated 4 local results. V1 has not been rerun on this shortlist; the allowance has about 3.6 credits left.

**Final verdict page** (`/verdict#<session>`):
- Built deterministically from the saved comparison and V1 evidence: verdict banner, scorecard, numbered next steps, evidence by vendor and caveats.
- The next steps cover demo shortlist, common gaps, per-vendor questions, pilot pass/fail checks, written quotes when no pricing is verified, onboarding timeline, and exclusions for contradictions.
- The app opens it automatically when an evaluation you are watching finishes. Finished runs show an "Open final verdict" button.

## Spend and limits

Crustdata spend for the milestone is now 6.00 of the 6-credit allowance:
- earlier validation: 5.76
- discovery runs: 0.12 + 0.12

The user then approved a **new 1-credit allowance**. Run 3 used 0.36 of it, so **0.64 remains**. The `web-live-discovery` launch config caps each thread at 1 credit; total use across threads is tracked here. V1 is still "not connected" in the web flow, so no evaluation or recommendation is produced.

Checks: 117 tests pass (synthetic fixtures; not live proof). Ruff lint and format pass. Visual QA was done only through the in-app browser during the trial.
