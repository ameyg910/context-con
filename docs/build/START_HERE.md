# Start here — Idea C implementation handoff

Prepared 2026-11-22. The user chose **Technical Vendor Evidence Review** and explicitly requested **LangGraph**. This pack is for implementing in a new chat. No application or Git commit was created by preparing these documents.

## Read order and precedence

1. Root [AGENTS.md](../../AGENTS.md): authorization and evidence rules.
2. [PRODUCT.md](PRODUCT.md): selected problem and features.
3. [WORKFLOW.md](WORKFLOW.md): final evidence investigation and output.
4. [LANGGRAPH_ARCHITECTURE.md](LANGGRAPH_ARCHITECTURE.md): graph, tools, state and persistence.
5. [COMMIT_01.md](COMMIT_01.md): immediate implementation task and completion checks.
6. [ACCEPTANCE.md](ACCEPTANCE.md): staged verification and event requirements.
7. [API_REFERENCE.md](../API_REFERENCE.md), [CRUSTDATA_CAPABILITIES.md](../CRUSTDATA_CAPABILITIES.md), [OPEN_QUESTIONS.md](../OPEN_QUESTIONS.md): source map, historical contracts and unresolved gaps.

This pack supersedes earlier sales/expert-sourcing pivots and any suggestion to weaken evidence gathering. Preserve comprehensive evidence investigation with adaptive depth; keep presentation concise. Existing IDEA_C_FINAL.md and IDEA_C_EVENT_REQUIREMENTS.md provide context. Actual organizer formats override our internal output proposals.

## Task to execute next

Build **commit 01: an interactive local LangGraph agent that can converse and execute bounded real Crustdata API calls**. Complete that runnable foundation before implementing the full research workflow or a polished dashboard. Follow COMMIT_01.md. Do not merely produce another plan.

## Current workspace

The root contains research Markdown, assistant-captured data under output/probes, and the older claim_probe.py/Ollama experiment. That script is not the new agent and does not autonomously acquire data. Its small-model result was rejected. Preserve it as historical evidence; do not use it as a successful baseline.

Three useful probe records:
- [FarEye](../../output/probes/fareye-20261122/REVIEWED_FINDINGS.md).
- [project44](../../output/probes/project44-20261122/REVIEWED_FINDINGS.md).
- [Actual LinkedIn-derived retrieval](../../output/probes/trust-linkedin-20261122/REVIEWED_FINDINGS.md).

Observed failures: irrelevant search hits, opaque redirects, connector HTML truncation, direct fetches landing on unrelated recruiting pages, missing metadata, repeated vendor claims and inaccurate model conclusions. These must inform retrieval quality checks.

## Decisions already made

- Python and local CLI are the proposed first implementation choices; LangGraph is the user's explicit choice.
- One capable, configurable tool-calling model. No default reliance on the small local 4B model.
- First implement a conversational graph with tools and persistence; then add the full evidence workflow.
- Customer-side corroboration and relevant professional research are core product capabilities.
- No legal/vendor clearance, production technical certification or automatic fraud verdict.
- No emails/reference calls, recurring watches, accounts or deployments in the current implementation scope.
- No exclusive Crustdata-data advantage or buyer demand has been validated.
- Use official docs and actual account schemas; never invent endpoints or fields.

## Unknowns the next chat must resolve

Inspect installed dependencies/project/repository status before changing layout. Identify available model credentials by variable names/configuration, without printing values. Local Crustdata credentials have not been established: the connected assistant tool worked, but its authorization cannot be assumed reusable in local Python. Ask for secure configuration only if credentials cannot be supplied through available authorized mechanisms. Do not dump environment variables or read unrelated secrets.

The repo was not a Git repository during an earlier check. Verify again. If an organizer repository or existing destination is supplied, use it. Otherwise local Git initialization for the requested first implementation commit is reasonable within this project; preserve existing files and do not bulk-commit raw research captures or secrets. Do not push remotely without authorization.

## New-chat prompt

> Read AGENTS.md and docs/build/START_HERE.md, then implement docs/build/COMMIT_01.md. We are building Idea C, Technical Vendor Evidence Review, using Python and LangGraph. First deliver an interactive local chat agent with real bounded Crustdata tools, visible tool activity, persisted conversation and a cost ledger. Implement and test the foundation before adding the full customer/people research graph. Preserve the evidence-grounded product requirements. Inspect configuration safely; never invent API schemas or claim live success from mocked tests. Make the first implementation commit after the acceptance checks pass, and report any live checks blocked by credentials. Do not deploy, send messages, create accounts, add watches or push remotely.
