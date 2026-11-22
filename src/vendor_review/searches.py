"""Durable search runs: discovery result, one evaluation row per candidate, final comparison.

Every step is written before the next starts, so a killed process resumes where it stopped:
completed evaluations are reused, never re-run. A candidate whose evaluation was in flight at
the kill is re-requested with the same (run_id, candidate_key); the v1 runner owns its own
paid-call idempotency for that key.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

from vendor_review.brief import BuyerBrief
from vendor_review.pipeline import (
    Candidate,
    Comparison,
    Discovery,
    NotConnectedV1,
    SearchSpec,
    V1Request,
    V1Result,
    V1Runner,
    build_spec,
    compare,
)

DONE = ("completed", "partial", "failed", "not_connected")
# With a real evaluator connected, a "not_connected" placeholder is work still to do.
FINISHED = ("completed", "partial", "failed")


class SearchStore:
    def __init__(self, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.db = sqlite3.connect(path, timeout=10, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS sessions (
              id TEXT PRIMARY KEY, created REAL, title TEXT);
            CREATE TABLE IF NOT EXISTS runs (
              id TEXT PRIMARY KEY, session TEXT UNIQUE, created REAL, finished REAL,
              status TEXT, brief TEXT, spec TEXT, candidates TEXT, comparison TEXT, error TEXT);
            CREATE TABLE IF NOT EXISTS evaluations (
              run TEXT, candidate_key TEXT, started REAL, finished REAL, status TEXT,
              result TEXT, PRIMARY KEY (run, candidate_key));
        """)

    def _q(self, sql, args=()):
        with self.lock:
            cur = self.db.execute(sql, args)
            self.db.commit()
            return cur

    # sessions
    def create_session(self) -> str:
        sid = uuid.uuid4().hex[:12]
        self._q("INSERT INTO sessions VALUES (?,?,?)", (sid, time.time(), "New search"))
        return sid

    def sessions(self):
        rows = self._q(
            "SELECT s.id, s.created, s.title, r.status FROM sessions s "
            "LEFT JOIN runs r ON r.session=s.id ORDER BY s.created DESC LIMIT 50"
        ).fetchall()
        return [dict(r) for r in rows]

    def session_exists(self, sid) -> bool:
        return self._q("SELECT 1 FROM sessions WHERE id=?", (sid,)).fetchone() is not None

    def set_title(self, sid, title):
        self._q("UPDATE sessions SET title=? WHERE id=?", (title[:80], sid))

    # runs
    def run_for(self, sid):
        row = self._q("SELECT * FROM runs WHERE session=?", (sid,)).fetchone()
        return dict(row) if row else None

    def start_run(self, sid, brief: BuyerBrief) -> tuple[str, bool]:
        """Idempotent: a second confirm (double click, retry after restart) returns the same run."""
        with self.lock:
            existing = self.run_for(sid)
            if existing:
                return existing["id"], False
            rid = "run_" + uuid.uuid4().hex[:10]
            spec = build_spec(rid, brief)
            self._q(
                "INSERT INTO runs VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    rid,
                    sid,
                    time.time(),
                    None,
                    "discovering",
                    brief.model_dump_json(),
                    spec.model_dump_json(),
                    None,
                    None,
                    None,
                ),
            )
            return rid, True

    def unfinished_runs(self):
        rows = self._q("SELECT id FROM runs WHERE status NOT IN ('done','error')").fetchall()
        return [r["id"] for r in rows]

    def run(self, rid):
        row = self._q("SELECT * FROM runs WHERE id=?", (rid,)).fetchone()
        return dict(row) if row else None

    def update_run(self, rid, **fields):
        cols = ", ".join(f"{k}=?" for k in fields)
        self._q(f"UPDATE runs SET {cols} WHERE id=?", (*fields.values(), rid))

    def evaluations(self, rid):
        rows = self._q("SELECT * FROM evaluations WHERE run=?", (rid,)).fetchall()
        return {r["candidate_key"]: dict(r) for r in rows}

    def mark_evaluating(self, rid, key):
        self._q(
            "INSERT INTO evaluations VALUES (?,?,?,?,?,?) ON CONFLICT(run,candidate_key) "
            "DO UPDATE SET started=excluded.started, status='running'",
            (rid, key, time.time(), None, "running", None),
        )

    def reset_evaluations(self, rid, statuses):
        """Make failed/placeholder evaluations pending again; completed ones are kept."""
        marks = ",".join("?" * len(statuses))
        self._q(f"DELETE FROM evaluations WHERE run=? AND status IN ({marks})", (rid, *statuses))

    def save_evaluation(self, rid, key, result: V1Result):
        self._q(
            "UPDATE evaluations SET finished=?, status=?, result=? WHERE run=? AND candidate_key=?",
            (time.time(), result.status, result.model_dump_json(), rid, key),
        )


def execute_run(
    store: SearchStore,
    rid: str,
    discovery: Discovery,
    v1: V1Runner,
    credit_limit: float,
    seconds_limit: float,
    event=print,
):
    run = store.run(rid)
    spec = SearchSpec.model_validate_json(run["spec"])
    brief = BuyerBrief.model_validate_json(run["brief"])
    try:
        if run["candidates"] is None:
            found = discovery.find(spec)
            excluded = {v.strip().lower() for v in spec.exclude_vendors}
            unique: dict[str, Candidate] = {}
            for cand in sorted(found, key=lambda c: -c.relevance):
                if cand.name.strip().lower() in excluded or cand.domain.lower() in excluded:
                    continue
                unique.setdefault(cand.key, cand)  # duplicate records collapse to one
            chosen = list(unique.values())[: spec.top_k]
            store.update_run(
                rid,
                status="evaluating",
                candidates=json.dumps([c.model_dump(mode="json") for c in chosen]),
            )
            event(f"{rid}: discovered {len(found)} → evaluating {len(chosen)}")
        candidates = [Candidate.model_validate(c) for c in json.loads(store.run(rid)["candidates"])]
        per_vendor = credit_limit / max(1, len(candidates))

        def evaluate(cand):
            store.mark_evaluating(rid, cand.key)
            request = V1Request(
                run_id=rid,
                candidate=cand,
                brief=brief,
                questions=spec.questions,
                credit_limit=per_vendor,
                seconds_limit=seconds_limit,
            )
            try:
                result = v1.evaluate(request)
            except Exception as exc:
                result = V1Result(
                    candidate_key=cand.key,
                    status="failed",
                    notes=f"Evaluation failed: {type(exc).__name__}: {str(exc)[:200]}",
                )
            store.save_evaluation(rid, cand.key, result)
            event(f"{rid}: {cand.name} → {result.status}")

        pending = [
            cand
            for cand in candidates
            if (store.evaluations(rid).get(cand.key) or {}).get("status")
            not in (DONE if isinstance(v1, NotConnectedV1) else FINISHED)
        ]  # never repeat completed work after a restart
        workers = max(1, min(len(pending) or 1, int(os.environ.get("V1_PARALLEL", "4"))))
        if workers == 1:
            for cand in pending:  # a crash stops here; nothing queued keeps running
                evaluate(cand)
        else:
            with ThreadPoolExecutor(max_workers=workers) as pool:
                list(pool.map(evaluate, pending))
        results = {
            k: V1Result.model_validate_json(v["result"])
            for k, v in store.evaluations(rid).items()
            if v["result"]
        }
        comparison: Comparison = compare(spec, candidates, results)
        store.update_run(
            rid, status="done", finished=time.time(), comparison=comparison.model_dump_json()
        )
    except Exception as exc:
        store.update_run(rid, status="error", error=f"{type(exc).__name__}: {exc}"[:500])
        event(f"{rid}: error {type(exc).__name__}")
