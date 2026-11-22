# Foundation validation — 2026-11-22

All implementation changes are in `Z:\Projects\context-con`. The original AI-Agent research/probes were preserved. No commit, push, deployment, account creation, messages or watches were performed. The user's current instruction supersedes the build pack's proposed commit step.

## Deterministic checks

Commands, run from the destination repository:

```powershell
.\.venv\Scripts\python -m pytest -q
.\.venv\Scripts\python -m ruff check src tests
.\.venv\Scripts\python -m ruff format --check src tests
.\.venv\Scripts\python -m pip check
```

Tests use **synthetic model/HTTP fixtures**, actual LangGraph control flow and SQLite checkpoints. They cover typed allowlisting and exact bodies/headers; actual versus unknown credit accounting; cumulative and per-turn credit/call/token limits; lowering a durable session limit; independent threads; SQLite reopen; multiple requested tools; endless model-loop termination; permission/schema/HTTP failures without retries; pending dispatch reuse without reissue; deadline rejection of late model tool calls; secret redaction in artifacts/messages; public-page input constraints; response quality/truncation; citation-origin rejection; local structured actions; free-tier-only Gemini configuration and process locking. Partial/failed captures and no-match results are explicitly distinguished from successful evidence.

The final test/check results are recorded below after the last implementation changes. The installed LangSmith dependency emits Python 3.14 deprecation warnings for `asyncio.iscoroutinefunction`; these are warnings, not failed checks, and external tracing is disabled.

Dependencies are pinned in `pyproject.toml` and `requirements.lock`. Tested Python is 3.14.6 on Windows. A fresh isolated `.venv` was created and dependencies installed; the editable package command succeeded after using a workspace temp directory to avoid a setuptools/sandbox brace-path issue. Initial sandbox DNS failures required a network-enabled package installation. `pip check` reports no broken requirements. No other Python/platform compatibility claim is made.

## Actual REST smoke

Executed `vendor-review --thread live-validation --smoke` with the supplied local key, separately from tests. Official REST schemas were checked before implementation; see [CONTRACTS](CONTRACTS.md). Raw captures and request IDs remain in ignored local databases, not Git.

| Actual operation | Outcome | Returned credits |
| --- | --- | ---: |
| Account permissions | Enabled routes, field grants, effective RPM and own prices obtained | 0, documented free |
| Account credits | Valid account balance obtained; full balance intentionally omitted from this report | 0, documented free |
| Identify `crustdata.com` | Match returned, `crustdata_company_id=6036032` | 0.2 |
| Enrich selected ID, basic fields | Indexed company fields returned | 2 |
| One-page web search | URLs/snippets returned, including opaque redirect leads | 1 |
| Fetch `https://www.crustdata.com/` | Page content returned, qualified by extraction/final-URL limitations | 1 |
| **REST smoke total** | Four paid tools succeeded | **4.2** |

Each paid charge above was read from `X-Credits-Used`, not inferred from a balance difference or mock. Account metadata omitted that header and is recorded as documented free. No retries were issued.

## Gemini primary path — actual native tool calling

After the user's clarification, this build permits only the documented free-tier models `gemini-3.1-flash-lite` and `gemini-3.8-flash`; no paid-model fallback or billing setup is available. **`gemini-3.1-flash-lite` is the verified default.** Official [pricing](https://aistudio.google.com/docs/pricing) documents free input/output for these models. Billing tier belongs to the key's project; the application cannot force Free Tier with a per-request flag. The user states they have no paid Gemini credit; no billing account was created/changed and no invoice was inspected.

Live commands used thread `free-gemini-check` with a deliberately lowered **0.2-credit cumulative Crustdata allowance**:

```powershell
$env:MODEL_PROVIDER = 'gemini'
$env:MODEL_NAME = 'gemini-3.1-flash-lite'
$env:SESSION_CREDITS = '0.2'
.\.venv\Scripts\vendor-review --thread free-gemini-check --prompt 'Use identify_company once for crustdata.com. Return the actual company name, company ID and artifact ID. Do not use other tools.'
# Separate process: restart and follow up using the persisted checkpoint.
.\.venv\Scripts\vendor-review --thread free-gemini-check --prompt 'Continue from our saved conversation. Which company and exact company ID did the API identify? Cite the saved artifact ID. Do not call tools.' --prompt 'Without further tools, tell me whether that company lookup alone verifies customer deployments. Keep the company context.'
```

Observed: the model requested a native `identify_company` call, the adapter made the real request, and the model returned **Crustdata (YC F24), ID 6036032**, citing artifact `8ea851df79794e89a65c8b7af198b67a`. After a separate-process restart, it retained the same identity and artifact. The next turn correctly stated that the lookup alone does **not** verify customer deployments and distinguished provider-indexed descriptions from independent corroboration. No additional paid tools were called in these follow-ups. The session stayed at **0.2 credits spent, 0 remaining**.

Gemini reported token usage for all four successful model calls: **718 + 1442 + 1602 + 1800 = 5562 tokens**. The first two were recorded before zero Free Tier rates were configured and remain unpriced in their original ledger records; the later calls record USD 0 **at configured free-tier rates**, not an observed invoice. No successful earlier cloud generation is claimed.

Earlier live model attempts are preserved as failures: Gemini 2.5 Pro returned model-not-found; 4 Carbon was rate-limited; 3.8 Flash returned server/API failures. Those calls reported no token usage, so their reservations remain held rather than being declared free/uncharged. Paid-only model selection is now rejected before network use. Gemini credentials did authenticate for model listing and successful 3.1 Flash-Lite generation; there is **no remaining credential blocker for the foundation's primary path**. Availability/quota for 3.8 Flash is not validated by listing it.

## Optional local-provider check

Ollama exposed installed `qwen2.5-coder:7b` and `qwen3.5:4b-q4_K_M`. No model was downloaded. The 4B model was not used as the implementation baseline. The 7B model advertised native tools but initially emitted JSON as chat text, which did not execute anything. Structured-action mode later made a real identify call in clean thread `local-demo`, costing **0.2 credits**, retained the company ID on follow-up and after restart, and recorded **6274 total reported tokens** across four calls. Its provider-inference cost has no external token charge; local compute/electricity remain unpriced.

The local model also invented a provenance URL during an earlier response. This triggered implementation of the citation-origin gate and a deterministic regression test. Current responses attach actual artifact receipts and reject generated URLs absent from tool data. Earlier failed/weak model outputs remain historical in the local checkpoint; they are not retroactively described as grounded successes. Local context is configured to 16K and response quality was inconsistent; **local inference remains optional and is not the primary evidence reasoning strategy**.

## Total observed validation cost and artifacts

Across all validation threads: **4.6 observed Crustdata credits** (4.2 REST smoke + 0.2 local-provider tool loop + 0.2 free-tier Gemini tool loop), within the original 10-credit ceiling. All other account calls were documented free. The individual validation threads were capped separately (10, 0.5 and 0.2 credits); this combined total was reviewed across the durable ledger. Application budgets are per thread, not an account-wide credit control.

Local-only transcripts: `.local/smoke.log`, `.local/free-gemini-check.log`, `.local/free-gemini-resume.log`, `.local/local-demo.log`, `.local/local-resume.log`; failed attempts are retained in the other `.local/*chat.log` files. Durable operations/artifacts live in `.local/runtime/ledger.sqlite`; conversations live in `.local/runtime/checkpoints.sqlite`. They and `.env` are ignored by Git. The smoke test's operation request IDs and charge source are inspectable through `--ledger`.

## Scope and remaining limitations

This is stage 1, not a complete vendor assessment. The customer/professional branches, independent customer corroboration, temporal/origin analysis, claim-by-claim review and complete evidence dossier remain required next stages. No actual organizer request/response adapter, event case or buyer demand/price has been invented. Search snippets and marketing are not verification. Exact final redirected URL is not available in the selected fetch contract. The citation-origin check does not establish semantic support for every model claim.

Thread isolation, interrupted pending-dispatch handling and hard limits were exercised deterministically. Successful primary-provider lookup, multi-turn context and separate-process restart were exercised live. A real process kill precisely around a billable provider dispatch was **not** performed; no exactly-once/provider cancellation guarantee is claimed. No live unauthorized/error cases were deliberately manufactured to spend credits; those cases use fixtures.

## Final check results

Final results: **38 passed** (`pytest -q`, 1.53 seconds; 17 dependency deprecation warnings); Ruff lint passed; Ruff formatting check passed (14 Python files); `pip check` reported no broken requirements; `git diff --check` passed. A content scan of all 38 candidate source/documentation files found neither supplied credential. Git ignore checks confirmed `.env`, `.local/runtime/ledger.sqlite` and `.venv/pyvenv.cfg` are excluded. All application/docs/tests remain uncommitted, as requested.

| COMMIT_01 acceptance | Evidence and boundary |
| --- | --- |
| One-command interactive chat | Installed `vendor-review --thread NAME` entry point; `--prompt` exercises the same graph noninteractively |
| Genuine LangGraph loop and real REST | Native free-tier Gemini tool request -> real identify -> returned evidence -> model answer; direct REST smoke covers all six tools |
| Two turns retain company | Real Gemini lookup plus two follow-ups retained ID 6036032 and the same artifact |
| Grounded bounded query | Returned provider field provenance and artifact IDs; citation-origin regression gate; semantic claim verification remains later scope |
| Restart and isolation | Separate-process Gemini restart passed; separate checkpointer threads and DB reopen covered deterministically |
| Activity, charges, failures and budgets inspectable | Start/finish/denial events, raw redacted artifacts, returned charge headers, local CLI ledger and recorded failed attempts |
| Limits survive more turns/lowering | Independent turn/session credit/call/token guards and lowered durable allowance tested; live Gemini follow-ups retained the exhausted 0.2-credit cap |
| Errors stop and secrets are redacted | No automatic retries; synthetic auth/schema/429/timeout and redaction tests passed; source/ignore review passed |
| Fresh setup documented | Empty virtual environment installation and editable command verified; pinned versions and exact commands in README |
| Live blockers reported | No credential blocker for verified default; 3.8 Flash generation remains unvalidated/unavailable in attempted checks; local native tooling is unreliable |
