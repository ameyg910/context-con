"""Adapter: run the V1 single-vendor evidence agent for one discovered candidate.

The web search pipeline hands each candidate a `V1Request` (buyer brief + numbered questions +
per-vendor credit/time caps). This adapter:

1. Writes one buyer-facing message that states every question and constraint verbatim, and builds
   V1's `Brief` from it, so V1's own grounding check (`validate_brief`) passes without a model
   intake step and without inventing buyer wording.
2. Runs the V1 LangGraph research agent in its own thread with its own ledger session capped at
   the per-vendor credit limit (never more than the configured session cap).
3. Converts V1 findings back into `RequirementAnswer`s with exact quoted evidence, and exports the
   vendor's standalone HTML dossier.

Verdict mapping is deliberately conservative. Vendor documentation counts as `supported` only
with a captured exact passage; its attribution stays in the summary. Nothing here is independent
verification, a current contract or supplier approval.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import threading
import time
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from vendor_review.pipeline import (
    Evidence,
    RequirementAnswer,
    RunCost,
    V1Request,
    V1Result,
)
from vendor_review.research import heading_like


class Pacer:
    """Process-wide spacing of model calls shared by all parallel vendor reviews.

    The Gemini free tier allows a fixed number of generate requests per minute per project
    (observed: 15/min for gemini-3.1-flash-lite, from the provider's own 429 message). Parallel
    reviews share that quota, so calls are spaced to stay under it instead of failing.
    """

    def __init__(self, per_minute):
        self.interval = 60.0 / max(1, per_minute)
        self.lock = threading.Lock()
        self.next_at = 0.0

    def wait(self):
        with self.lock:
            now = time.monotonic()
            start = max(now, self.next_at)
            self.next_at = start + self.interval
        if start > now:
            time.sleep(start - now)


PACER = Pacer(int(os.environ.get("MODEL_REQUESTS_PER_MINUTE", "12")))


def rate_limited(exc):
    text = f"{type(exc).__name__} {exc}"
    return "RESOURCE_EXHAUSTED" in text or "RateLimit" in text or " 429" in text


def retry_after(exc, default=30.0):
    match = re.search(r"retry in ([0-9.]+)s", str(exc))
    return float(match.group(1)) if match else default


class PacedModel:
    """Wraps a chat model: shared pacing, and one bounded retry only for a provider 429.

    A 429 is a definite rejection (no generation, no charge), so one retry after the
    provider's advised delay is safe. Other errors are raised unchanged; the graph records
    them and never retries automatically.
    """

    def __init__(self, model, pacer=None, max_retry_wait=40.0, sleep=time.sleep):
        self.model, self.pacer = model, pacer or PACER
        self.max_retry_wait, self.sleep = max_retry_wait, sleep

    def bind_tools(self, schemas):
        return PacedModel(
            self.model.bind_tools(schemas), self.pacer, self.max_retry_wait, self.sleep
        )

    def invoke(self, messages):
        self.pacer.wait()
        try:
            return self.model.invoke(messages)
        except Exception as exc:
            delay = retry_after(exc)
            if not rate_limited(exc) or delay > self.max_retry_wait:
                raise
            self.sleep(delay + 1)
            self.pacer.wait()
            return self.model.invoke(messages)


PRIORITY = {
    "must_have": "must",
    "integration": "must",
    "geography": "must",
    "compliance": "must",
    "nice_to_have": "should",
    "budget": "question",
}
VERDICT = {
    "vendor_documented": "supported",
    "customer_reported": "supported",
    "professional_attributed": "supported",
    "third_party_reported": "supported",
    "partially_supported": "partially_supported",
    "conflicting_vendor_docs": "partially_supported",
    "conflicting_evidence": "partially_supported",
    "cannot_verify": "cannot_verify",
}
ATTRIBUTION = {
    "vendor_documented": "Vendor's own documentation states this",
    "customer_reported": "A customer-owned source reports this",
    "professional_attributed": "An attributed professional statement reports this",
    "third_party_reported": "A third-party source reports this",
    "partially_supported": "Evidence covers part of this requirement",
    "conflicting_vendor_docs": "Vendor documents disagree",
    "conflicting_evidence": "Sources disagree",
    "cannot_verify": "No admissible evidence found",
}


def buyer_message(request: V1Request) -> tuple[str, dict]:
    """Return (message text, V1 brief args). Every brief value appears verbatim in the text."""
    b, cand = request.brief, request.candidate
    lines = [
        f"Vendor: {cand.name}",
        f"Domain: {cand.domain}",
        f"Use case: {b.use_case or b.service_category}",
        "Requirements:",
    ]
    requirements = []
    for i, q in enumerate(request.questions, 1):
        lines.append(f"R{i}: {q.text}")
        requirements.append(
            {
                "id": f"R{i}",
                "text": q.text,
                "buyer_quote": q.text,
                "priority": PRIORITY.get(q.kind, "question"),
                "acceptance_criterion": "unknown",
            }
        )
    constraints = {
        "geography": ", ".join(b.geography) or "unknown",
        "integrations": ", ".join(b.integrations) or "unknown",
        "scale": b.scale or "unknown",
        "security": "; ".join([*b.compliance, b.deployment] if b.deployment else b.compliance)
        or "unknown",
        "budget": b.budget.label() if b.budget.stated else "unknown",
        "timeline": b.timeline or "unknown",
    }
    lines += [f"{key.title()}: {value}" for key, value in constraints.items()]
    brief = {
        "vendor": cand.name,
        "domain": cand.domain,
        "use_case": b.use_case or b.service_category,
        "requirements": requirements,
        "constraints": constraints,
        "buyer_quotes": {
            "vendor": cand.name,
            "domain": cand.domain,
            "use_case": b.use_case or b.service_category,
            **constraints,
        },
    }
    return "\n".join(lines), brief


def research_prompt(request: V1Request, credit_cap: Decimal) -> str:
    cand = request.candidate
    home = cand.website or f"https://{cand.domain}/"
    n = len(request.questions)
    steps = [
        f"Evaluate {cand.name} ({cand.domain}) against every requirement R1-R{n} in the saved "
        f"brief. Crustdata credits left for this vendor: {credit_cap}.",
        "1. Vendor identity and its own pages are usually already captured (see captured_sources "
        f"and identity). If identity is not resolved, identify_company {cand.domain} (kind domain); "
        f"if no vendor page is captured, fetch_page {home}.",
        "2. Call find_passages ONCE with requirement_ids for all requirements (free), then ONE "
        "record_findings call with a finding for every requirement, quoting returned sentences verbatim. vendor_documented needs a vendor or related-official-domain sentence "
        "that actually states the capability; otherwise partially_supported or cannot_verify.",
        "3. If important requirements remain unsupported and at least 1 credit is left, fetch ONE "
        "more relevant linked vendor page (integrations, pricing, features) or run at most one "
        "web_search. Then find_passages and record_findings again.",
        "4. Professional branch, only if at least 1.2 credits are left: search_people with the "
        "resolved company_id, employment current, role_keywords like implementation, solutions or "
        "product, limit 2; then search_person_posts for the most relevant person, limit 1. "
        "Register a professional reference only for an authored original post that relates to a "
        "requirement. Otherwise record professional coverage as blocked or attempted with gaps.",
        "5. Record customer coverage honestly (blocked with the gap if no customer-owned source "
        "was read). No contact data, outreach or buying-intent inference.",
        f"6. Every R1-R{n} must end with a finding; use cannot_verify with what would settle it. "
        "Never guess. Finish with a two-sentence buyer summary.",
    ]
    return "\n".join(steps)


def to_result(request: V1Request, state: dict, pages: dict, cost: RunCost, notes: str) -> V1Result:
    ids = {f"R{i}": q.id for i, q in enumerate(request.questions, 1)}
    answers = {}
    pricing = []
    for finding in state.get("findings", []):
        qid = ids.get(finding["requirement_id"])
        if not qid:
            continue
        evidence = []
        for c in finding.get("citations", []):
            page = pages.get((c["artifact_id"], c["url"]), {})
            retrieved = page.get("retrieved_at_unix")
            evidence.append(
                Evidence(
                    url=c["url"],
                    artifact_id=c["artifact_id"],
                    passage_or_field=c["quote"],
                    publisher=c.get("source_kind", "vendor_document"),
                    source_date=str(page.get("publication_date") or ""),
                    retrieved_at=datetime.fromtimestamp(retrieved, timezone.utc).isoformat()
                    if retrieved
                    else "",
                )
            )
        verdict = VERDICT.get(finding["status"], "cannot_verify")
        if verdict == "supported" and not evidence:
            verdict = "cannot_verify"
        downgraded = bool(
            verdict != "cannot_verify"
            and evidence
            and all(heading_like(e.passage_or_field) for e in evidence)
        )
        if downgraded:
            # Findings saved before the heading rule existed: a menu label is not support.
            verdict = "cannot_verify"
        label = (
            "Only a menu heading was cited, so this is not treated as support"
            if downgraded
            else ATTRIBUTION.get(finding["status"], finding["status"])
        )
        answer = RequirementAnswer(
            question_id=qid,
            verdict=verdict,
            summary=f"{label}: {finding['claim']}"[:900],
            evidence=evidence,
            missing="" if verdict == "supported" else finding.get("limitations", "")[:600],
        )
        # Vendor docs and customer/professional findings can coexist; keep the strongest.
        rank = {"supported": 3, "partially_supported": 2, "contradicted": 1, "cannot_verify": 0}
        if qid not in answers or rank[verdict] > rank[answers[qid].verdict]:
            answers[qid] = answer
        q = next(x for x in request.questions if x.id == qid)
        if q.kind == "budget":
            pricing.extend(evidence)
    for q in request.questions:
        answers.setdefault(
            q.id,
            RequirementAnswer(
                question_id=q.id,
                verdict="cannot_verify",
                summary="Not researched within this vendor's limits",
                missing="No finding was recorded before the run ended",
            ),
        )
    researched = sum(
        1 for a in answers.values() if a.summary != "Not researched within this vendor's limits"
    )
    status = (
        "completed"
        if researched == len(request.questions)
        else "partial"
        if researched
        else "failed"
    )
    budget_q = next((q.id for q in request.questions if q.kind == "budget"), None)
    return V1Result(
        candidate_key=request.candidate.key,
        status=status,
        answers=[answers[q.id] for q in request.questions],
        pricing_summary=answers[budget_q].summary if budget_q else "",
        pricing_evidence=pricing,
        cost=cost,
        notes=notes,
    )


PAGE_WORDS = (
    "product", "feature", "solution", "module", "integration", "pricing", "price", "plan",
    "3pl", "warehouse", "wms", "platform", "software", "billing", "fulfil", "inventory",
)  # fmt: skip
SKIP_WORDS = (
    "blog", "career", "job", "contact", "privacy", "terms", "login", "signin", "sign-in",
    "news", "event", "webinar", "cookie", "policy", "press", "case-stud", "download",
)  # fmt: skip
SOCIAL = {"linkedin", "facebook", "twitter", "youtube", "instagram", "google", "x", "wa", "t"}


def host_of(url):
    from urllib.parse import urlsplit

    return (urlsplit(url).hostname or "").lower().removeprefix("www.")


def related_domains(links, primary, vendor_text):
    """Hosts linked from the vendor's own page AND named in its indexed name/description.

    Example: onpalms.com links to technoforte.co.in and Crustdata's description says Palms
    "is a Technoforte Supply Chain initiative". Social and unrelated links never qualify.
    """
    found = []
    for link in links or []:
        host = host_of(link)
        label = host.split(".")[0] if host else ""
        if (
            not host
            or host == primary
            or host.endswith("." + primary)
            or label in SOCIAL
            or len(label) < 4
            or not re.search(rf"\b{re.escape(label)}\b", vendor_text, re.I)
        ):
            continue
        if host not in found:
            found.append(host)
    return found[:3]


def pick_links(links, hosts, limit):
    from urllib.parse import urlsplit

    scored = []
    for link in dict.fromkeys(links or []):
        host = host_of(link)
        if not any(host == h or host.endswith("." + h) for h in hosts):
            continue
        path = urlsplit(link).path.lower()
        if path in {"", "/"} or any(w in path for w in SKIP_WORDS):
            continue
        score = sum(w in path for w in PAGE_WORDS)
        if score:
            scored.append((-score, len(path), link))
    return [link for _, _, link in sorted(scored)[:limit]]


def unanswered(state):
    have = {f["requirement_id"] for f in state.get("findings", [])}
    return [
        r["id"] for r in (state.get("brief") or {}).get("requirements", []) if r["id"] not in have
    ]


class V1Agent:
    """V1Runner implementation backed by the real LangGraph research agent."""

    synthetic = False

    def __init__(self, settings=None, model_factory=None, client_factory=None, event=print):
        from vendor_review.config import Settings

        self.settings = settings or Settings.load()
        self.model_factory = model_factory
        self.client_factory = client_factory
        self.event = event
        self.root = self.settings.data_dir / "v1"
        self.max_attempts = int(os.environ.get("V1_MAX_ATTEMPTS", "3"))
        self.prefetch_pages = int(os.environ.get("V1_PREFETCH_PAGES", "2"))
        self.use_prefetch = os.environ.get("V1_PREFETCH", "1") != "0"
        self.root.mkdir(parents=True, exist_ok=True)

    def vendor_settings(self, credit_limit: float):
        cap = min(Decimal(str(credit_limit)), self.settings.session_credits)
        return self.settings.model_copy(
            update={
                "session_credits": cap,
                "turn_credits": cap,
                "session_tool_calls": int(os.environ.get("V1_TOOL_CALLS", "30")),
                "turn_tool_calls": 20,
                "session_model_calls": int(os.environ.get("V1_MODEL_CALLS", "24")),
                "turn_model_calls": 20,
                "session_model_tokens": int(os.environ.get("V1_MODEL_TOKENS", "200000")),
                "turn_seconds": float(os.environ.get("V1_TURN_SECONDS", "600")),
                "model_name": os.environ.get("V1_MODEL_NAME", self.settings.model_name),
            }
        ), cap

    def prefetch(self, client, thread, request, state, deadline):
        """Deterministically capture the vendor's identity and own pages before the model runs.

        Returns (messages to append, identity). Every call goes through the same priced,
        ledgered Crustdata client and the vendor's credit cap; results become ordinary tool
        captures, so the model and validators treat them exactly like its own fetches.
        """
        from langchain_core.messages import AIMessage, ToolMessage

        cand = request.candidate
        primary = cand.domain.lower().removeprefix("www.")
        identity = dict(state.get("identity") or {})
        messages, turn = [], "prefetch-" + uuid.uuid4().hex

        def call(name, args):
            key = f"{turn}-{len(messages)}"
            result = client.execute(name, args, thread, turn, key, deadline)
            messages.append(
                AIMessage(
                    content="",
                    tool_calls=[{"name": name, "args": args, "id": key, "type": "tool_call"}],
                )
            )
            messages.append(ToolMessage(content=json.dumps(result), tool_call_id=key))
            return result

        if not identity.get("resolved"):
            res = call("identify_company", {"identifier": primary, "kind": "domain"})
            rows = (res.get("data") or {}).get("records") or []
            matches = (
                rows[0].get("matches", []) if res.get("status") == "ok" and len(rows) == 1 else []
            )
            match = matches[0].get("company_data", {}) if len(matches) == 1 else {}
            actual = (
                (match.get("basic_info", {}).get("primary_domain") or "")
                .lower()
                .removeprefix("www.")
            )
            identity = {
                "resolved": bool(primary and actual == primary),
                "company_id": match.get("crustdata_company_id"),
                "domain": actual,
                "artifact_id": res.get("artifact_id"),
                "related_domains": [],
            }
        home = cand.website or f"https://{primary}/"
        res = call("fetch_page", {"url": home})
        links = []
        if res.get("status") in {"ok", "partial"}:
            links = [link for page in res.get("data") or [] for link in page.get("links", [])]
        related = related_domains(links, primary, f"{cand.name} {cand.why_relevant}")
        identity["related_domains"] = sorted(
            set(identity.get("related_domains", [])) | set(related)
        )
        for url in pick_links(links, [primary, *identity["related_domains"]], self.prefetch_pages):
            if client.ledger.summary(thread)["remaining_credits"] < 1:
                break
            call("fetch_page", {"url": url})
        return messages, identity

    def attempt(self, ledger, saver, base):
        """Pick the vendor's attempt thread: (thread, seed state or None, credits already spent).

        A thread whose durable tool/token limits are nearly used up, or whose last turn ended at
        a limit or a model failure, cannot continue. A new attempt thread is then seeded with its
        captures and saved findings. Credits spent by all attempts count against one allowance.
        """
        rows = ledger.db.execute(
            "SELECT thread, tool_calls, tokens FROM sessions WHERE thread=? OR thread LIKE ?",
            (base, base + "-a%"),
        ).fetchall()
        rows = sorted(
            rows, key=lambda r: int(r[0].rsplit("-a", 1)[1]) if "-a" in r[0][len(base) :] else 1
        )
        spent = sum(
            (Decimal(str(ledger.summary(r[0])["held_credits_including_unknown"])) for r in rows),
            Decimal(0),
        )
        if not rows:
            return base, None, spent
        latest, tool_cap, token_cap = rows[-1]
        used = ledger.summary(latest)
        values = saver.get_tuple({"configurable": {"thread_id": latest}})
        state = values.checkpoint["channel_values"] if values else {}
        worn = (
            tool_cap - used["tool_calls"] < 8
            or token_cap - used["token_usage_or_reservations"] < 60000
            or state.get("outcome") in {"budget_stop", "model_failed"}
        )
        if not worn or not state or len(rows) >= self.max_attempts:
            return latest, None, spent
        seed = {
            k: state.get(k, [] if k in {"findings", "references"} else {})
            for k in ("messages", "brief", "identity", "findings", "references", "coverage")
        }
        return f"{base}-a{len(rows) + 1}", seed, spent

    def evaluate(self, request: V1Request) -> V1Result:
        from langchain_core.messages import AIMessage, HumanMessage
        from langgraph.checkpoint.sqlite import SqliteSaver

        from vendor_review.crustdata import Crustdata
        from vendor_review.graph import build_graph, turn_input
        from vendor_review.intake import readiness, validate_brief
        from vendor_review.models import make_model
        from vendor_review.references import captured_pages
        from vendor_review.report import write_report
        from vendor_review.store import Ledger

        started = time.monotonic()
        if not request.candidate.domain:
            return V1Result(
                candidate_key=request.candidate.key,
                status="failed",
                notes="No company domain; V1 needs an exact domain to resolve identity",
            )
        settings, cap = self.vendor_settings(request.credit_limit)
        base = f"v1-{request.run_id}-{request.candidate.key}"
        ledger = Ledger(self.root / "ledger.sqlite", settings)
        connection = sqlite3.connect(self.root / "checkpoints.sqlite", check_same_thread=False)
        saver = SqliteSaver(connection)
        thread, seed, spent = self.attempt(ledger, saver, base)
        # The vendor's allowance covers ALL attempts: a new attempt thread only gets what is left.
        remaining = max(Decimal(0), cap - spent)
        settings = settings.model_copy(
            update={"session_credits": remaining, "turn_credits": remaining}
        )
        ledger.settings = settings
        client = (
            self.client_factory(settings, ledger)
            if self.client_factory
            else Crustdata(settings, ledger, event=self.event)
        )
        try:
            ledger.session(thread)
            text, brief_args = buyer_message(request)
            message = HumanMessage(content=text)
            brief = validate_brief(brief_args, [message])
            if not readiness(brief)["ready"]:
                raise ValueError("Constructed V1 brief is not ready: " + str(readiness(brief)))
            model = (
                self.model_factory(settings)
                if self.model_factory
                else PacedModel(make_model(settings))
            )
            graph = build_graph(model, client, ledger, settings, saver, self.event, review=True)
            config = {"configurable": {"thread_id": thread}, "recursion_limit": 120}
            resumed = bool(graph.get_state(config).values) or seed is not None
            if seed is not None:
                # New attempt: carry earlier captures, identity and saved findings forward.
                graph.update_state(
                    config,
                    {
                        **seed,
                        "messages": [
                            *seed["messages"],
                            AIMessage(content="Continuing this vendor review in a new attempt."),
                        ],
                        "turn": "seed",
                        "deadline": time.time(),
                        "outcome": "seeded",
                    },
                    as_node="model",
                )
            elif not graph.get_state(config).values:
                graph.update_state(
                    config,
                    {
                        "messages": [
                            message,
                            AIMessage(
                                content="Brief saved from the buyer's confirmed search brief."
                            ),
                        ],
                        "brief": brief,
                        "findings": [],
                        "identity": {},
                        "references": [],
                        "coverage": {},
                        "turn": "seed",
                        "deadline": time.time(),
                        "outcome": "seeded",
                    },
                    as_node="model",
                )
            if client.access is None:
                # A fresh key per attempt: a reused key would return the cached ledger result
                # without loading account access, and every paid tool would then be refused.
                pre = client.preflight(
                    thread, "preflight-" + uuid.uuid4().hex, time.monotonic() + 60
                )
                if pre.get("status") != "ok" or client.access is None:
                    # No paid tools (e.g. allowance used up); local review of captures still runs.
                    self.event(f"v1 {request.candidate.name}: paid tools off: {pre.get('message')}")
            current = graph.get_state(config).values
            domains = [request.candidate.domain.lower().removeprefix("www."),
                       *current.get("identity", {}).get("related_domains", [])]  # fmt: skip
            own_pages = [
                url
                for (_, url), page in captured_pages(current.get("messages", [])).items()
                if url
                and any(host_of(url) == d or host_of(url).endswith("." + d) for d in domains)
                and not set(page.get("quality", []))
                & {"fetch_failed_or_empty", "returned_host_differs"}
            ]
            if len(own_pages) < 2 and client.access is not None and self.use_prefetch:
                added, identity = self.prefetch(
                    client, thread, request, current, time.monotonic() + settings.turn_seconds
                )
                graph.update_state(
                    config,
                    {
                        "messages": [
                            *added,
                            AIMessage(content="Vendor identity and own pages pre-fetched."),
                        ],
                        "identity": identity,
                    },
                    as_node="model",
                )
            prompt = research_prompt(
                request, Decimal(str(ledger.summary(thread)["remaining_credits"]))
            )
            if resumed:
                prompt += (
                    " This resumes an interrupted review: sources captured earlier are listed in "
                    "captured_sources. Reuse them with read_evidence before any new search, never "
                    "refetch a captured URL, and keep findings already saved."
                )
            state = graph.invoke(turn_input(prompt, settings), config)
            missing = unanswered(state)
            if missing and state.get("outcome") in {"complete", "budget_stop"}:
                # Closing turn: no new retrieval is needed to say what the captured evidence
                # does or does not show. Uses only free local tools; unknowns become explicit.
                closing = (
                    "Close this vendor review using ONLY evidence already captured (no new fetch "
                    f"or search). Call find_passages once with requirement_ids {missing}, then ONE "
                    "record_findings call covering all of them. Use vendor_documented or partially_supported only when a "
                    "returned vendor sentence states it; otherwise cannot_verify with what would "
                    "settle it. Every listed requirement must get a finding."
                )
                try:
                    state = graph.invoke(turn_input(closing, settings), config)
                except Exception as exc:  # keep the first turn's saved work
                    self.event(f"v1 closing turn failed: {type(exc).__name__}")
            report = write_report(state, ledger, thread, settings)
            summary = ledger.summary(thread)
            cost = RunCost(
                crustdata_credits=summary["observed_credits"],
                model_tokens=summary["token_usage_or_reservations"],
                seconds=round(time.monotonic() - started, 1),
            )
            outcome = state.get("outcome")
            notes = f"V1 outcome: {outcome}. Dossier: {report}"
            if outcome == "budget_stop":
                notes = (
                    "Stopped at an enforced limit; unresearched requirements stay cannot_verify. "
                    + notes
                )
            result = to_result(request, state, captured_pages(state["messages"]), cost, notes)
            self.event(
                f"v1 {request.candidate.name}: {result.status} credits={cost.crustdata_credits}"
            )
            return result
        finally:
            try:
                client.close()
            finally:
                connection.close()
                ledger.close()


def result_json(result: V1Result) -> str:
    return json.dumps(result.model_dump(mode="json"), ensure_ascii=False)
