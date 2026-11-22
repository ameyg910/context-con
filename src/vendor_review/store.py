"""Durable operation ledger; reservations survive errors, restarts and uncertain outcomes."""

import json
import sqlite3
import time
import uuid
from contextlib import contextmanager
from decimal import Decimal


class LimitError(Exception):
    pass


def units(value):
    return int((Decimal(str(value)) * 1_000_000).to_integral_value(rounding="ROUND_CEILING"))


class Ledger:
    def __init__(self, path, settings):
        self.settings = settings
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, timeout=10)
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS sessions (
              thread TEXT PRIMARY KEY, credits INTEGER, tool_calls INTEGER,
              model_calls INTEGER, tokens INTEGER);
            CREATE TABLE IF NOT EXISTS operations (
              id TEXT PRIMARY KEY, thread TEXT, turn TEXT, call_key TEXT,
              kind TEXT, name TEXT, path TEXT, started REAL, finished REAL,
              status TEXT, reserved INTEGER, actual INTEGER, token_reserve INTEGER,
              tokens INTEGER, details TEXT, result TEXT,
              UNIQUE(thread, call_key));
            CREATE TABLE IF NOT EXISTS artifacts (
              id TEXT PRIMARY KEY, operation TEXT, captured REAL, payload TEXT);
        """)

    @contextmanager
    def transaction(self):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            yield
            self.db.commit()
        except BaseException:
            self.db.rollback()
            raise

    def close(self):
        self.db.close()

    def session(self, thread):
        s = self.settings
        with self.transaction():
            self.db.execute(
                """INSERT INTO sessions VALUES (?,?,?,?,?)
              ON CONFLICT(thread) DO UPDATE SET
              credits=min(credits,excluded.credits), tool_calls=min(tool_calls,excluded.tool_calls),
              model_calls=min(model_calls,excluded.model_calls), tokens=min(tokens,excluded.tokens)
            """,
                (
                    thread,
                    units(s.session_credits),
                    s.session_tool_calls,
                    s.session_model_calls,
                    s.session_model_tokens,
                ),
            )

    def prior(self, thread, call_key):
        row = self.db.execute(
            "SELECT * FROM operations WHERE thread=? AND call_key=?", (thread, call_key)
        ).fetchone()
        return dict(row) if row else None

    def reserve(self, thread, turn, call_key, kind, name, path="", credits=0, tokens=0):
        with self.transaction():
            if self.prior(thread, call_key):
                raise LimitError("Operation already recorded; never automatically reissue")
            cap = self.db.execute("SELECT * FROM sessions WHERE thread=?", (thread,)).fetchone()
            if cap is None:
                raise LimitError("Session not initialized")
            totals = self._totals(thread)
            count = self.db.execute(
                "SELECT count(*) FROM operations WHERE thread=? AND turn=? AND kind=?",
                (thread, turn, kind),
            ).fetchone()[0]
            turn_cap = (
                self.settings.turn_tool_calls if kind == "tool" else self.settings.turn_model_calls
            )
            if count >= turn_cap or totals[kind + "_calls"] >= cap[kind + "_calls"]:
                raise LimitError(f"{kind} call limit reached")
            if totals["held"] + units(credits) > cap["credits"]:
                raise LimitError("Cumulative Crustdata budget exhausted (includes unknown charges)")
            turn_held = self.db.execute(
                "SELECT coalesce(sum(coalesce(actual,reserved)),0) FROM operations WHERE thread=? AND turn=?",
                (thread, turn),
            ).fetchone()[0]
            if turn_held + units(credits) > units(self.settings.turn_credits):
                raise LimitError("Per-turn Crustdata credit limit reached")
            if totals["tokens"] + tokens > cap["tokens"]:
                raise LimitError("Cumulative model token budget exhausted")
            op = uuid.uuid4().hex
            self.db.execute(
                "INSERT INTO operations VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    op,
                    thread,
                    turn,
                    call_key,
                    kind,
                    name,
                    path,
                    time.time(),
                    None,
                    "pending",
                    units(credits),
                    None,
                    tokens,
                    None,
                    "{}",
                    None,
                ),
            )
            return op

    def _totals(self, thread):
        row = self.db.execute(
            """SELECT
          coalesce(sum(coalesce(actual,reserved)),0) held,
          coalesce(sum(actual),0) observed,
          coalesce(sum(coalesce(tokens,token_reserve)),0) tokens,
          coalesce(sum(kind='tool'),0) tool_calls,
          coalesce(sum(kind='model'),0) model_calls,
          coalesce(sum(status IN ('pending','unknown') OR (actual IS NULL AND reserved>0)
            OR (kind='model' AND tokens IS NULL AND token_reserve>0)),0) uncertain
          FROM operations WHERE thread=?""",
            (thread,),
        ).fetchone()
        return dict(row)

    def summary(self, thread):
        total = self._totals(thread)
        cap = self.db.execute("SELECT * FROM sessions WHERE thread=?", (thread,)).fetchone()
        return {
            "observed_credits": total["observed"] / 1_000_000,
            "held_credits_including_unknown": total["held"] / 1_000_000,
            "remaining_credits": max(0, cap["credits"] - total["held"]) / 1_000_000,
            "token_usage_or_reservations": total["tokens"],
            "tool_calls": total["tool_calls"],
            "model_calls": total["model_calls"],
            "uncertain_operations": total["uncertain"],
        }

    def finish(self, op, status, result, actual=None, tokens=None, details=None):
        with self.transaction():
            self.db.execute(
                "UPDATE operations SET finished=?,status=?,actual=?,tokens=?,"
                "details=?,result=? WHERE id=?",
                (
                    time.time(),
                    status,
                    units(actual) if actual is not None else None,
                    tokens,
                    json.dumps(self.settings.redact(details or {})),
                    json.dumps(self.settings.redact(result)),
                    op,
                ),
            )

    def artifact(self, op, payload):
        artifact = uuid.uuid4().hex
        with self.transaction():
            self.db.execute(
                "INSERT INTO artifacts VALUES (?,?,?,?)",
                (artifact, op, time.time(), json.dumps(self.settings.redact(payload))),
            )
        return artifact

    def recent(self, thread, limit=12):
        return [
            dict(row)
            for row in self.db.execute(
                "SELECT id,kind,name,status,reserved,actual,tokens,details FROM operations "
                "WHERE thread=? ORDER BY started DESC LIMIT ?",
                (thread, limit),
            )
        ]

    def rate_wait(self, path, rpm, global_rpm=None):
        # Sliding 60-second windows include pending/failed requests and all local threads.
        now = time.time()
        waits = [0.0]
        for endpoint, limit in ((path, rpm), (None, global_rpm)):
            if limit is None:
                continue
            if limit <= 0:
                raise LimitError("Account rate limit disallows dispatch")
            sql = "SELECT started FROM operations WHERE kind='tool' AND path!='' AND started>?"
            args = [now - 60]
            if endpoint is not None:
                sql += " AND path=?"
                args.append(endpoint)
            rows = self.db.execute(sql + " ORDER BY started DESC", args).fetchall()
            if len(rows) >= int(limit):
                waits.append(max(0, rows[int(limit) - 1][0] + 60.05 - now))
        return max(waits)
