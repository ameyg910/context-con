# Customer corroboration and professional research — milestone validation, 2026-11-22

Status: **implemented; deterministic tests pass; a model-assisted run on the saved captures is partial.** One customer reference (Girteka) and one customer-scoped R1 finding were registered from a recovered customer-owned passage. No professional reference was registered. No branch is sufficient; both ended blocked at the model token limit.

No commit, push, deployment, account, watch, contact-data collection or outreach was performed.

## What each kind of evidence shows

| Kind | What it shows | Status for this milestone |
| --- | --- | --- |
| Deterministic tests | Validators, extraction, graph control flow, ledger and report rendering on **synthetic fixtures**, using real LangGraph/SQLite machinery | 98 passed |
| Saved-capture replay | `read_evidence` and the validators applied to real saved captures, with no new spend | **Done.** The Girteka capture was re-read locally and `project44` found in readable article text |
| Model-assisted review | Gemini choosing tools and registering references or coverage against real captures | **Done, partial:** thread `project44-references-replay` (see below) |
| New live acquisition | New paid Crustdata calls | One `/social_post/search`, 0.50 credits returned |

The end-to-end customer/professional graph test (`test_full_customer_and_professional_graph_records_both_branches`) uses synthetic HTTP and model fixtures. It is **not** live success.

## Earlier live runs, reported in the handoff and not re-verified here

The handoff for this milestone describes two runs in a different checkout (`Z:\Projects\context-con`). Their logs, `runtime/ledger.sqlite` and `checkpoints.sqlite` are **not present** in this checkout (`C:\contextCon\contextCon New\context-con`). Searching this machine found no copy, so the figures below are as reported, not re-checked:

- `corroboration-validation`: company identify, people search, profile enrichment, indexed post retrieval and original-post filtering returned results. Reported spend: 2.43 credits.
- `project44-references-demo`: resolved project44 and Girteka, obtained a professional lead and fetched pages. It then **stopped at the durable model-token reservation limit** before reference registration, findings and coverage were complete. Reported spend: 2.83 credits.
- Combined reported spend: **5.26 of a 6-credit validation allowance**, leaving 0.74. A new thread or checkout does not replenish that allowance, so the local `.env` here is capped at `SESSION_CREDITS=0.74` / `TURN_CREDITS=0.74`. Any substantial further paid validation needs an explicit new allowance.

### Girteka article

`https://www.girteka.eu/information-is-key-to-effective-supply-chain-management/` (artifact `6e970d1e3fb34f72bae7021b592b9a99`) was reportedly captured. Its first 8,000-character excerpt was dominated by cookie-consent text and did not contain "project44".

**No admissible passage from it has been recovered.** The capture is unavailable here, so `read_evidence(focus="project44")` could not be run against it. Nothing in this milestone claims the article supports anything. The new extraction (below) is designed for exactly this failure, but it has been demonstrated only on a synthetic page with the same structure.

A previously guessed project44 case-study URL returned a page-not-found page. That failure stays a failure. Pages flagged `possible_not_found` are rejected as reference evidence, and a test covers this.

## Review fixes made in this milestone

1. **Findings overwrote each other.** Findings were keyed only by requirement, so a customer or professional finding replaced the vendor-document finding for the same requirement. They are now keyed by requirement and evidence class (vendor/primary, customer, professional, third-party), and the report shows each one separately.
2. **Customer ownership and vendor mention could come from different passages.** A vendor-hosted quote naming the vendor plus an unrelated quote from the customer's own site used to count as a customer-owned account. Now one customer-domain passage must itself name the vendor. Each citation records its publisher (customer domain, vendor domain or other) and whether it names the vendor. Findings may cite only those customer-owned sources.
3. **Indirect relationships.** Each reference records whether the relationship is direct, indirect (integrator, partner, downstream beneficiary, supplier) or unknown. An indirect customer reference is reported but cannot make the customer branch sufficient. Relationships must also fit the reference kind: for example, a customer reference cannot be a "vendor employee".
4. **Professional authorship is per source.** Each citation is classed as an indexed original post by the same person ID, a captured byline needing review, a repost, a post by another author or a non-person actor. A byline is matched against every saved passage, not only the latest excerpt. Findings may cite only authored sources. The event-date basis is recorded (indexed publication date, or date text in a passage, which needs review).
5. **Budget-stop reporting.** A model token overrun after the call, which is how the earlier demo stopped, used to end the turn without recording branch status. It now records the same `budget_stop` as other enforced limits: unfinished branches become `blocked`, with the stop reason, the prior status and rationale kept, and gaps listed. The HTML summary also states that research stopped at an enforced limit.
6. **Extraction and focused reading.** Pages are now parsed by `page_text`, which `fetch_page` compaction and `read_evidence` share:
   - Consent and cookie-manager overlays are dropped. They are matched by element id, class or aria-label, never by body wording, so an article about cookies keeps its text. Navigation, footers, iframes and SVG are also dropped.
   - An `<article>` or `<main>` region with substantial text is preferred.
   - `read_evidence(focus=...)` returns every exact, non-overlapping focus window as a citable passage. Each window carries its offsets and keeps the original retrieval date.
   - A focus match found only inside removed consent markup (for example, a cookie-vendor list) is reported with the `focus_only_in_removed_boilerplate_review_required` flag and is **not** citable.
   - Quality flags from any reading of a capture are kept, never cleared.
   - The raw HTML in the ledger is never modified.

New tests: `tests/test_corroboration_review.py` (13) and the benchmark version test in `tests/test_benchmarks.py`.

## Benchmark

project44 is now **v1.1.0** (`benchmarks/project44/brief.json`):

- R3's stage is now `customer_corroboration`.
- Both branches are marked `enabled_read_only`.
- A new check, **G13**, requires recorded coverage for both branches, scope-limited statements and explicit gaps.
- All R1–R8 questions, G1–G12 and the missing buyer inputs are unchanged, and a test asserts this.

v1.0.0 is preserved byte-for-byte as `brief.v1.0.0.json` (`--benchmark-version 1.0.0`). `reference.json` (historical answers) is still never loaded into agent prompts, and the tests check that its distinctive values are absent from both versions' prompts. The v1.1.0 confirmation prompt is 7,903 characters, under the 8,000-character message limit.

## Checks run

These were run in this checkout after the last code change:

- `pytest -q`: 97 passed. The only warnings are LangSmith deprecation warnings under Python 3.14.
- `ruff check src tests`: passed.
- `ruff format --check src tests`: 24 files already formatted.
- `pip check`: no broken requirements.
- `git diff --check`: clean.
- Secret and runtime-artifact review:
  - `.env` and `.local/` are ignored.
  - No modified or untracked file contains a Crustdata, Gemini or Google key pattern.
  - No ledger, checkpoint, capture or report file is tracked.
  - Redaction now also covers the `AQ.`-prefixed Google key format, in addition to the exact configured values.

**Visual browser QA is not claimed.** `file:` preview was blocked earlier and no workaround was attempted. The HTML was checked structurally by tests only.

## Remaining work

1. Copy the original `.local` captures into this checkout, or work in the original checkout. Then replay the Girteka artifact with `read_evidence(focus="project44")` and record whether an admissible customer-owned passage exists. Spend nothing on this replay.
2. With an explicit new allowance, finish one representative customer reference and one professional reference from live evidence, plus coverage for both branches. Report the actual returned charges.
3. Cross-check the people and post request schemas against the OpenAPI files (`person.yaml`, `social_post.yaml`).

## Run on saved captures, `project44-references-replay` (added after the captures were restored)

The captures were then copied into this checkout's `.local/`. The ledger confirms the earlier spend: `corroboration-validation` 2.43, `project44-references-demo` 2.83.

- **Thread copy.** `project44-references-demo` had stopped at its durable 100,000-token model limit. Its saved state (33 messages, all captures, original retrieval dates) was copied into a new thread. The original checkpoint is unchanged. The copy has its own free-tier model-token limit and a Crustdata cap of the remaining 0.74 credits. This is disclosed as saved-capture replay, not a fresh end-to-end run.
- **Girteka.** `read_evidence(focus="project44")` on artifact `6e970d1e...`:
  - Consent and navigation boilerplate removed: 12,089 readable characters out of 34,323.
  - One exact window found. It is a quote on girteka.eu that names project44: "With our latest solution developed with project44, we can provide information about the exact truck location, ETA, and other details in real-time..."
  - Publication date: not in the passage.
- **Agent actions (real Gemini calls).**
  - Registered REF1 (customer, girteka.eu, period unknown) and a `customer_reported` R1 finding.
  - Ran one original-post search for the saved project44 engineer lead (0.50 credits). It returned a 2025-08-13 original post about tariff tracking, which the agent correctly did not register.
  - Recorded customer coverage as `attempted`.
- **Stopped at the model token limit.** 10 model calls, 67,626 tokens. Both branches were then recorded `blocked`, with the stop reason and gaps. No buyer-facing answer was produced.
- **Total milestone spend: 5.76 of 6 credits; 0.24 left.**

Issues this run exposed:
1. **The agent repeated work.** After each successful save, the graph's context trimming hid the turn's earlier steps, so the agent restarted at step 1. This used up its token budget before professional coverage was written. Still open.
2. **An old not-found capture lacked its flag.** It is now rejected by title too. Fixed, with a test.
3. **The relationship label is model interpretation.** The agent chose `direct_customer`. An integrator/partner reading is plausible and needs human review.

Results page with the conversation and evidence matrix (local, ignored by git): `.local/reports/project44-references-replay/test-run-results.html`. The standard dossier is `latest.html` in the same folder.
