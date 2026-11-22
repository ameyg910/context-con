"""FastAPI server for the intake chat and vendor search UI.

Run:  vendor-review-web  (or python -m vendor_review.web.app)

Plug-in points (no code change needed in this file):
  V1_RUNNER=package.module:ClassName     single-vendor evidence agent, implements V1Runner
  DISCOVERY=package.module:ClassName     candidate discovery, implements Discovery
Both default to honest "not connected" placeholders.
"""

from __future__ import annotations

import importlib
import os
import sqlite3
import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.sqlite import SqliteSaver
from pydantic import BaseModel, Field, ValidationError

from vendor_review.brief import (
    RECOMMENDED,
    REQUIRED,
    BuyerBrief,
    completeness,
    missing_recommended,
    missing_required,
)
from vendor_review.chat_intake import GREETING, build_intake_graph, intake_turn
from vendor_review.config import Settings
from vendor_review.pipeline import Candidate, NotConnectedDiscovery, NotConnectedV1
from vendor_review.searches import SearchStore, execute_run
from vendor_review.store import Ledger

STATIC = Path(__file__).parent / "static"


def load_plugin(spec: str | None, default):
    if not spec:
        return default
    module, _, name = spec.partition(":")
    return getattr(importlib.import_module(module), name)()


class Runtime:
    def __init__(self, settings: Settings, model=None, v1=None, discovery=None):
        self.settings = settings
        root = Path(settings.data_dir) / "web"
        root.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()  # graph, checkpointer and ledger share connections
        self.ledger = Ledger(root / "ledger.sqlite", settings)
        self.checkpoints = SqliteSaver(
            sqlite3.connect(root / "intake.sqlite", check_same_thread=False)
        )
        self.store = SearchStore(root / "search.sqlite")
        self.model_error = None
        if model is None:
            try:
                from vendor_review.models import make_model

                model = make_model(settings)
            except Exception as exc:  # missing key/provider: rule-based intake still works
                self.model_error = f"{type(exc).__name__}: {settings.redact(str(exc))[:200]}"
        self.model = model
        self.client = os.environ.get("CLIENT_NAME", "a mid-size Indian 3PL logistics company")
        self.graph = build_intake_graph(
            model, self.ledger, settings, self.checkpoints, client=self.client
        )
        self.v1 = v1 or load_plugin(os.environ.get("V1_RUNNER"), NotConnectedV1())
        self.discovery = discovery or load_plugin(
            os.environ.get("DISCOVERY"), NotConnectedDiscovery()
        )
        self.search_credits = float(os.environ.get("SEARCH_CREDITS", "20"))
        self.search_seconds = float(os.environ.get("SEARCH_SECONDS_PER_VENDOR", "180"))
        self.workers: dict[str, threading.Thread] = {}

    def cfg(self, sid):
        return {"configurable": {"thread_id": "intake:" + sid}}

    def launch(self, rid):
        with self.lock:
            if rid in self.workers and self.workers[rid].is_alive():
                return
            t = threading.Thread(
                target=execute_run,
                args=(
                    self.store,
                    rid,
                    self.discovery,
                    self.v1,
                    self.search_credits,
                    self.search_seconds,
                ),
                daemon=True,
            )
            self.workers[rid] = t
            t.start()

    def resume_unfinished(self):
        for rid in self.store.unfinished_runs():
            self.launch(rid)


class MessageIn(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


class BriefIn(BaseModel):
    brief: dict


class SearchIn(BaseModel):
    confirm: bool


def create_app(runtime: Runtime | None = None) -> FastAPI:
    holder: dict[str, Runtime] = {}

    @asynccontextmanager
    async def lifespan(app):
        holder["rt"] = runtime or Runtime(Settings.load())
        holder["rt"].resume_unfinished()  # restart: continue searches from their last saved step
        yield

    app = FastAPI(title="Vendor Search Desk", lifespan=lifespan)

    def rt() -> Runtime:
        return holder["rt"]

    def require(sid):
        if not rt().store.session_exists(sid):
            raise HTTPException(404, "Unknown session")

    def view(sid):
        r = rt()
        with r.lock:
            state = r.graph.get_state(r.cfg(sid)).values
        brief = BuyerBrief.model_validate(state.get("brief") or {})
        messages = [
            {"role": "user" if isinstance(m, HumanMessage) else "assistant", "text": m.content}
            for m in state.get("messages", [])
            if isinstance(m, (HumanMessage, AIMessage))
        ]
        run = r.store.run_for(sid)
        return {
            "id": sid,
            "messages": messages,
            "brief": brief.model_dump(mode="json"),
            "budget_label": brief.budget.label(),
            "missing_required": [
                {"field": f, "label": REQUIRED[f]} for f in missing_required(brief)
            ],
            "missing_recommended": [
                {"field": f, "label": RECOMMENDED[f]} for f in missing_recommended(brief)
            ],
            "completeness": completeness(brief),
            "stage": "searching" if run else state.get("stage", "collecting"),
            "mode": state.get("mode", "fallback"),
            "run_id": run["id"] if run else None,
        }

    @app.get("/")
    def index():
        return FileResponse(STATIC / "index.html")

    @app.get("/api/config")
    def config():
        r = rt()
        return {
            "client": r.client,
            "model": f"{r.settings.model_provider}/{r.settings.model_name}",
            "model_available": r.model is not None,
            "model_error": r.model_error,
            "v1": type(r.v1).__name__,
            "v1_connected": not isinstance(r.v1, NotConnectedV1),
            "discovery": type(r.discovery).__name__,
            "synthetic": bool(
                getattr(r.v1, "synthetic", False) or getattr(r.discovery, "synthetic", False)
            ),
            "search_credits": r.search_credits,
        }

    @app.get("/api/sessions")
    def sessions():
        return rt().store.sessions()

    @app.post("/api/sessions")
    def create_session():
        r = rt()
        sid = r.store.create_session()
        with r.lock:
            r.ledger.session("intake:" + sid)
            r.graph.update_state(
                r.cfg(sid),
                {
                    "messages": [AIMessage(content=GREETING)],
                    "brief": {},
                    "stage": "collecting",
                    "mode": "model" if r.model else "fallback",
                    "asked": [],
                },
                as_node="intake",
            )
        return view(sid)

    @app.get("/api/sessions/{sid}")
    def get_session(sid: str):
        require(sid)
        return view(sid)

    @app.post("/api/sessions/{sid}/messages")
    def post_message(sid: str, body: MessageIn):
        require(sid)
        r = rt()
        if r.store.run_for(sid):
            raise HTTPException(409, "Search already started; the brief is locked for this run")
        with r.lock:
            first = not any(
                isinstance(m, HumanMessage)
                for m in r.graph.get_state(r.cfg(sid)).values.get("messages", [])
            )
            r.graph.invoke(intake_turn(body.text, r.settings), r.cfg(sid))
        if first:
            r.store.set_title(sid, body.text.strip().splitlines()[0])
        return view(sid)

    @app.put("/api/sessions/{sid}/brief")
    def put_brief(sid: str, body: BriefIn):
        """Direct edits from the brief panel: the buyer's own words, validated, no model."""
        require(sid)
        r = rt()
        if r.store.run_for(sid):
            raise HTTPException(409, "Search already started; the brief is locked for this run")
        try:
            brief = BuyerBrief.model_validate(body.brief)
        except ValidationError as exc:
            raise HTTPException(422, exc.errors(include_url=False)) from None
        with r.lock:
            r.graph.update_state(
                r.cfg(sid),
                {
                    "brief": brief.model_dump(mode="json"),
                    "stage": "collecting" if missing_required(brief) else "ready",
                },
                as_node="intake",
            )
        return view(sid)

    @app.post("/api/sessions/{sid}/search")
    def start_search(sid: str, body: SearchIn):
        """The buyer's explicit approval to spend on discovery and evaluation."""
        require(sid)
        if not body.confirm:
            raise HTTPException(400, "Search needs explicit confirmation")
        r = rt()
        state = view(sid)
        if state["missing_required"]:
            raise HTTPException(
                409, "Brief incomplete: " + ", ".join(m["label"] for m in state["missing_required"])
            )
        rid, _created = r.store.start_run(sid, BuyerBrief.model_validate(state["brief"]))
        r.launch(rid)
        return get_search(sid)

    @app.post("/api/sessions/{sid}/search/evaluate")
    def evaluate_shortlist(sid: str, body: SearchIn):
        """Evaluate an already discovered shortlist with the connected V1, without new discovery."""
        require(sid)
        if not body.confirm:
            raise HTTPException(400, "Evaluation needs explicit confirmation")
        r = rt()
        if isinstance(r.v1, NotConnectedV1):
            raise HTTPException(409, "The vendor evaluator is not connected in this build")
        run = r.store.run_for(sid)
        if not run or not run["candidates"]:
            raise HTTPException(409, "Run discovery first")
        if run["status"] not in {"done", "error"}:
            raise HTTPException(409, "This run is still in progress")
        # Retry vendors whose review failed (for example a provider rate limit) and placeholders;
        # completed reviews are kept. Each vendor's V1 thread resumes from its saved
        # captures and its ledger cap persists, so a retry cannot exceed the original allowance.
        r.store.reset_evaluations(run["id"], ("failed", "not_connected", "partial"))
        r.store.update_run(
            run["id"], status="evaluating", finished=None, comparison=None, error=None
        )
        r.launch(run["id"])
        return get_search(sid)

    @app.get("/api/sessions/{sid}/search")
    def get_search(sid: str):
        require(sid)
        r = rt()
        run = r.store.run_for(sid)
        if not run:
            return {"status": "not_started"}
        import json

        evals = r.store.evaluations(run["id"])
        candidates = json.loads(run["candidates"]) if run["candidates"] else None
        for c in candidates or []:
            c["key"] = Candidate.model_validate(c).key
        return {
            "run_id": run["id"],
            "status": run["status"],
            "error": run["error"],
            "spec": json.loads(run["spec"]),
            "candidates": candidates,
            "evaluations": {
                k: {
                    "status": v["status"],
                    "result": json.loads(v["result"]) if v["result"] else None,
                }
                for k, v in evals.items()
            },
            "comparison": json.loads(run["comparison"]) if run["comparison"] else None,
        }

    @app.get("/api/sessions/{sid}/verdict")
    def get_verdict(sid: str):
        """Final verdict and next steps, derived only from the saved comparison and evidence."""
        from vendor_review.verdict import build_verdict

        require(sid)
        r = rt()
        run = r.store.run_for(sid)
        if not run or not run["comparison"]:
            raise HTTPException(409, "The evaluation has not finished yet")
        return {
            "session": sid,
            "title": next((s["title"] for s in r.store.sessions() if s["id"] == sid), ""),
            **build_verdict(run, r.store.evaluations(run["id"])),
        }

    @app.get("/verdict")
    def verdict_page():
        return FileResponse(STATIC / "verdict.html")

    @app.get("/api/sessions/{sid}/ledger")
    def ledger(sid: str):
        require(sid)
        r = rt()
        with r.lock:
            return r.ledger.summary("intake:" + sid)

    app.mount("/static", StaticFiles(directory=STATIC), name="static")
    return app


def main():
    import uvicorn

    host = os.environ.get("WEB_HOST", "127.0.0.1")
    port = int(os.environ.get("WEB_PORT", "8765"))
    uvicorn.run(create_app(), host=host, port=port)


if __name__ == "__main__":
    main()
