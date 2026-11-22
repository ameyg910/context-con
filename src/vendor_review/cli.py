"""Interactive local entry point, diagnostics and bounded opt-in live smoke checks."""

import argparse
import json
import os
import re
import sqlite3
import sys
import time
import uuid
from contextlib import contextmanager

from langchain_core.messages import AIMessage, ToolMessage
from langgraph.checkpoint.sqlite import SqliteSaver

from vendor_review.benchmarks import benchmark_prompt, confirm_benchmark, load_benchmark
from vendor_review.config import Settings
from vendor_review.crustdata import Crustdata
from vendor_review.graph import build_graph, turn_input
from vendor_review.models import make_model
from vendor_review.report import write_report
from vendor_review.store import Ledger


def display(value):
    # Do not allow retrieved terminal control sequences to execute in a terminal.
    if (
        isinstance(value, list)
        and value
        and all(isinstance(part, dict) and part.get("type") == "text" for part in value)
    ):
        value = "\n".join(part.get("text", "") for part in value)
    text = value if isinstance(value, str) else json.dumps(value, indent=2, default=str)
    text = re.sub(r"[\x00-\x08\x0b-\x1f\x7f]", "", text)
    encoding = sys.stdout.encoding or "utf-8"
    print(text.encode(encoding, errors="backslashreplace").decode(encoding), flush=True)


@contextmanager
def runtime_lock(path):
    """One writer per runtime directory, including independent CLI processes."""
    with path.open("a+b") as handle:
        handle.seek(0)
        handle.write(b"0")
        handle.flush()
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise ValueError(
                "Another process owns this DATA_DIR; close it before resuming"
            ) from None
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == "nt":
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def abandon_pending(graph, config):
    """Never automatically execute a checkpoint's pending side effects after restart."""
    snapshot = graph.get_state(config)
    if not snapshot.next:
        return
    messages = snapshot.values.get("messages", [])
    answered = {m.tool_call_id for m in messages if isinstance(m, ToolMessage)}
    repairs = [
        ToolMessage(
            content=json.dumps(
                {
                    "status": "unknown",
                    "message": "Interrupted turn; not automatically reissued; inspect ledger",
                }
            ),
            tool_call_id=call["id"],
        )
        for message in messages
        if isinstance(message, AIMessage)
        for call in message.tool_calls
        if call["id"] not in answered
    ]
    repairs.append(
        AIMessage(
            content="Prior turn interrupted. Pending work was abandoned; "
            "unknown operation reservations remain in the ledger."
        )
    )
    graph.update_state(config, {"messages": repairs}, as_node="model")
    display("Recovered interrupted checkpoint without reissuing API operations. Inspect /ledger.")


def live_smoke(client, ledger, thread, settings):
    """Real REST checks only; this does not prove model-driven tool selection."""
    turn = uuid.uuid4().hex
    deadline = time.monotonic() + settings.turn_seconds
    result = client.preflight(thread, turn, deadline)
    if result["status"] != "ok":
        display(result)
        return 1
    company = client.execute(
        "identify_company",
        {"identifier": "crustdata.com"},
        thread,
        turn,
        "smoke:" + turn + ":identify",
        deadline,
    )
    display(company)
    results = [company]
    if company["status"] == "ok":
        rows = company["data"].get("records", [])
        matches = rows[0]["matches"] if rows else []
        company_id = (
            matches[0]["company_data"].get("crustdata_company_id") if len(matches) == 1 else None
        )
        if company_id:
            result = client.execute(
                "enrich_company",
                {"company_id": company_id},
                thread,
                turn,
                "smoke:" + turn + ":enrich",
                deadline,
            )
            display(result)
            results.append(result)
    # Use a separate turn but the same durable cumulative allowance; preflight consumed two calls.
    turn = uuid.uuid4().hex
    for name, args in (
        ("web_search", {"query": "Crustdata official company API"}),
        ("fetch_page", {"url": "https://www.crustdata.com/"}),
    ):
        result = client.execute(name, args, thread, turn, "smoke:" + turn + name, deadline)
        display(result)
        results.append(result)
    display(ledger.summary(thread))
    return 0 if len(results) == 4 and all(r["status"] == "ok" for r in results) else 1


def run(args, settings):
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    with runtime_lock(settings.data_dir / "app.lock"):
        ledger = Ledger(settings.data_dir / "ledger.sqlite", settings)
        thread = args.thread
        ledger.session(thread)
        client = Crustdata(settings, ledger, display)
        connection = sqlite3.connect(
            settings.data_dir / "checkpoints.sqlite", check_same_thread=False
        )
        try:
            if args.confirm_only:
                record, path = confirm_benchmark(
                    load_benchmark(args.benchmark, args.benchmark_version),
                    make_model(settings),
                    ledger,
                    settings,
                    SqliteSaver(connection),
                    thread,
                    display,
                )
                display(record)
                display("Benchmark confirmation: " + str(path))
                return 0 if record["coverage_check"] == "passed" else 1
            if args.ledger:
                display(ledger.summary(thread))
                display(ledger.recent(thread))
                return 0
            if args.artifact:
                row = ledger.db.execute(
                    "SELECT payload FROM artifacts WHERE id=?", (args.artifact,)
                ).fetchone()
                display(json.loads(row[0]) if row else "Artifact not found")
                return 0 if row else 1
            if args.report:
                checkpoint = SqliteSaver(connection).get_tuple(
                    {"configurable": {"thread_id": thread}}
                )
                state = checkpoint.checkpoint["channel_values"] if checkpoint else {}
                display(str(write_report(state, ledger, thread, settings)))
                return 0
            if args.smoke:
                return live_smoke(client, ledger, thread, settings)
            turn = uuid.uuid4().hex
            preflight = client.preflight(thread, turn, time.monotonic() + settings.turn_seconds)
            if args.check_access:
                display(preflight)
                display(ledger.summary(thread))
                return 0 if preflight["status"] == "ok" else 1
            if preflight["status"] != "ok":
                display(
                    "Crustdata preflight failed. Chat can continue; paid tools remain disabled."
                )
            graph = build_graph(
                make_model(settings),
                client,
                ledger,
                settings,
                SqliteSaver(connection),
                display,
                review=not args.chat_only,
            )
            config = {"configurable": {"thread_id": thread}, "recursion_limit": 100}
            abandon_pending(graph, config)
            display(f"Technical Vendor Evidence Review · foundation · thread={thread}")
            display("/new [name]  /history  /ledger  /report  /exit")
            pending = iter(args.prompt) if args.prompt else None
            initial = (
                benchmark_prompt(load_benchmark(args.benchmark, args.benchmark_version))
                if args.benchmark
                else None
            )
            while True:
                try:
                    if initial is not None:
                        text, initial = initial, None
                    else:
                        text = next(pending) if pending else input("you> ")
                except (EOFError, StopIteration):
                    break
                if text.strip() == "/exit":
                    break
                if text.startswith("/new"):
                    thread = text[4:].strip() or uuid.uuid4().hex[:12]
                    validate_thread(thread)
                    ledger.session(thread)
                    config["configurable"]["thread_id"] = thread
                    abandon_pending(graph, config)
                    display(
                        f"Selected thread={thread}; each thread has its own cumulative allowance"
                    )
                    continue
                if text.strip() == "/ledger":
                    display(ledger.summary(thread))
                    display(ledger.recent(thread))
                    continue
                if text.strip() == "/history":
                    for message in graph.get_state(config).values.get("messages", []):
                        display({"type": message.type, "content": message.content})
                    continue
                if text.strip() == "/report":
                    display(
                        str(write_report(graph.get_state(config).values, ledger, thread, settings))
                    )
                    continue
                if not text.strip():
                    continue
                state = graph.invoke(turn_input(text, settings), config)
                report_path = (
                    write_report(state, ledger, thread, settings) if not args.chat_only else None
                )
                display(state["messages"][-1].content)
                display(ledger.summary(thread))
                if report_path:
                    display("HTML dossier: " + str(report_path))
                if pending and state.get("outcome") in {"model_failed", "budget_stop"}:
                    return 1
            return 0
        finally:
            client.close()
            connection.close()
            ledger.close()


def validate_thread(value):
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", value):
        raise ValueError("Thread must contain 1–80 letters, digits, underscores or hyphens")
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--thread", default="default", type=validate_thread)
    parser.add_argument(
        "--benchmark",
        choices=["project44"],
        help="Load the versioned synthetic benchmark, without historical reference answers",
    )
    parser.add_argument(
        "--benchmark-version",
        choices=["1.1.0", "1.0.0"],
        help="Benchmark version (default: latest 1.1.0; 1.0.0 keeps branches deferred)",
    )
    parser.add_argument(
        "--confirm-only",
        action="store_true",
        help="Ask the model to acknowledge benchmark scope; no research tools or Crustdata calls",
    )
    parser.add_argument(
        "--chat-only", action="store_true", help="Legacy foundation chat without gated intake"
    )
    parser.add_argument(
        "--prompt", action="append", help="Run a turn then exit; repeat for multiple turns"
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--check-access", action="store_true", help="Free account checks, no model call"
    )
    mode.add_argument(
        "--smoke", action="store_true", help="Opt-in paid REST smoke under session cap"
    )
    mode.add_argument("--ledger", action="store_true", help="Inspect local ledger without network")
    mode.add_argument("--artifact", help="Inspect a local artifact without network")
    mode.add_argument(
        "--report", action="store_true", help="Export saved HTML dossier without network"
    )
    args = parser.parse_args()
    if args.confirm_only and not args.benchmark:
        parser.error("--confirm-only requires --benchmark")
    if args.confirm_only and args.thread == "default":
        args.thread = "project44-confirm-" + uuid.uuid4().hex[:8]
    try:
        settings = Settings.load()
        if args.confirm_only:
            settings = settings.model_copy(update={"session_credits": 0})
        return run(args, settings)
    except KeyboardInterrupt:
        display(
            "Interrupted. Saved operations remain; unknown dispatches are never automatically replayed."
        )
        return 130
    except Exception as exc:
        # Validation errors can include secret input values; never print arbitrary exception bodies.
        display(
            f"Startup/turn failed ({type(exc).__name__}). Check .env names, limits and selected model. "
            "Credentials and exception payloads suppressed."
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
