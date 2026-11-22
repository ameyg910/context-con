"""Versioned research inputs and model scope confirmation, separate from reference findings."""

import json
import re
from pathlib import Path

from vendor_review.graph import build_graph, turn_input

BENCHMARK_ROOT = Path(__file__).resolve().parents[2] / "benchmarks"


def load_benchmark(name):
    if name != "project44":
        raise ValueError("Unknown benchmark")
    return json.loads((BENCHMARK_ROOT / name / "brief.json").read_text(encoding="utf-8"))


def benchmark_prompt(case, confirm=False):
    text = (
        "This is a versioned synthetic research benchmark, not a real buyer brief. "
        "Preserve every question and check below. Do not invent missing buyer constraints. "
        "Do not treat a benchmark question as an established vendor fact.\n"
        + json.dumps(case, ensure_ascii=False, separators=(",", ":"))
    )
    if confirm:
        text += """\nCONFIRM UNDERSTANDING ONLY. No research, no tools, no factual verdict.
Return JSON only with these fields: understood (boolean), requirements (array of
{id, question, stage}), checks (array of {id, interpretation}), missing_buyer_inputs
(array of strings), scope_limitations (array of strings). Include EVERY original R and G ID.
Use short restatements. Clearly distinguish current vendor-document review from deferred
customer/professional corroboration. Acknowledge missing commercial thresholds and that model
agreement does not establish evidence truth. Do not assert that any vendor claim is verified.
For checks, copy each canonical instruction exactly into interpretation to avoid dropping details.
In scope_limitations explicitly acknowledge: bounded live read-only Crustdata research IS allowed
in subsequent research runs; only this confirmation has no tools. Operational vendor API tests,
outreach/accounts/watches/deployment are excluded. Known scenario and research questions are NOT
missing; buyer-specific operational constraints/thresholds are missing. Vendor marketing/badges
can be discovery/attributed claims, but cannot be treated as independent verification."""
    else:
        text += "\nStart intake. Ask for unresolved buyer inputs before paid research. Preserve all IDs."
    return text


class ConfirmationModel:
    """Do not bind any external tool definitions for a confirmation-only model call."""

    def __init__(self, model):
        self.model = model

    def bind_tools(self, schemas):
        return self

    def invoke(self, messages):
        return self.model.invoke(messages)


class NoResearch:
    def execute(self, *args, **kwargs):
        return {"status": "denied", "message": "Benchmark confirmation cannot execute research"}


def check_confirmation(content, case):
    if isinstance(content, list):
        content = "\n".join(p.get("text", "") for p in content if isinstance(p, dict))
    content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip())
    response = json.loads(content)
    for key in ("requirements", "checks"):
        expected = {item["id"] for item in case[key]}
        actual = [item["id"] for item in response[key]]
        if len(actual) != len(set(actual)) or set(actual) != expected:
            raise ValueError(f"Confirmation omitted or duplicated {key}")
    instructions = {item["id"]: item["instruction"] for item in case["checks"]}
    if any(item.get("interpretation") != instructions[item["id"]] for item in response["checks"]):
        raise ValueError("Confirmation shortened or changed a canonical check")
    if response.get("understood") is not True:
        raise ValueError("Model did not confirm understanding")
    if not response.get("missing_buyer_inputs") or not response.get("scope_limitations"):
        raise ValueError("Confirmation must preserve missing inputs and scope limits")
    expected_stages = {item["id"]: item["stage"] for item in case["requirements"]}
    if any(item.get("stage") != expected_stages[item["id"]] for item in response["requirements"]):
        raise ValueError("Confirmation changed current/deferred research scope")
    return response


def confirm_benchmark(case, model, ledger, settings, checkpoint, thread, event=print):
    graph = build_graph(ConfirmationModel(model), NoResearch(), ledger, settings, checkpoint, event)
    # Unique thread recommended: scope confirmation must not inherit unrelated research answers.
    config = {"configurable": {"thread_id": thread}, "recursion_limit": 100}
    if graph.get_state(config).values:
        raise ValueError("Use a fresh thread for benchmark scope confirmation")
    state = graph.invoke(turn_input(benchmark_prompt(case, True), settings), config)
    directory = settings.data_dir.parent / "benchmarks" / case["id"]
    directory.mkdir(parents=True, exist_ok=True)
    content = state["messages"][-1].content
    record = {
        "benchmark": case["id"],
        "version": case["version"],
        "thread": thread,
        "model": settings.model_name,
        "outcome": state.get("outcome"),
        "raw_response": settings.redact(content),
        "research_executed": False,
        "budget": ledger.summary(thread),
    }
    try:
        record["confirmation"] = check_confirmation(content, case)
        record["coverage_check"] = "passed"
    except (ValueError, KeyError, TypeError):
        record["coverage_check"] = "failed"
    path = directory / (thread + "-confirmation.json")
    path.write_text(json.dumps(settings.redact(record), indent=2), encoding="utf-8")
    return record, path.resolve()
