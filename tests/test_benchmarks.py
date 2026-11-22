import json
import sqlite3

import pytest
from langgraph.checkpoint.sqlite import SqliteSaver
from test_graph import ScriptedModel, answer

from vendor_review.benchmarks import (
    benchmark_prompt,
    check_confirmation,
    confirm_benchmark,
    load_benchmark,
)


def acknowledgement(case):
    return {
        "understood": True,
        "requirements": [
            {"id": r["id"], "question": r["question"], "stage": r["stage"]}
            for r in case["requirements"]
        ],
        "checks": [{"id": c["id"], "interpretation": c["instruction"]} for c in case["checks"]],
        "missing_buyer_inputs": case["missing_buyer_inputs"],
        "scope_limitations": ["Agreement is not evidence verification; no research executed."],
    }


def test_benchmark_keeps_original_claims_checks_and_unknowns():
    case = load_benchmark("project44")
    assert len(case["requirements"]) == 8 and len(case["checks"]) == 12
    assert {"R2", "R3", "R4", "R5", "R6"} <= {r["id"] for r in case["requirements"]}
    text = benchmark_prompt(case, True)
    assert "631278" not in text and "documented_interface_not_runtime_verified" not in text
    assert "Girteka" in text and "85%" in text and "Asendia" in text
    assert "No research, no tools" in text
    assert len(text) <= 8000


@pytest.mark.parametrize("failure", ["omission", "duplicate", "stage", "unknowns"])
def test_confirmation_coverage_rejects_changed_scope(failure):
    case = load_benchmark("project44")
    ack = acknowledgement(case)
    if failure == "omission":
        ack["checks"].pop()
    if failure == "duplicate":
        ack["requirements"].append(ack["requirements"][0])
    if failure == "stage":
        ack["requirements"][2]["stage"] = "current_vendor_research"
    if failure == "unknowns":
        ack["missing_buyer_inputs"] = []
    with pytest.raises(ValueError):
        check_confirmation(json.dumps(ack), case)


def test_confirmation_uses_model_and_checkpoint_without_research_tools(setup):
    settings, ledger = setup
    case = load_benchmark("project44")
    model = ScriptedModel([answer(json.dumps(acknowledgement(case)))])
    with sqlite3.connect(":memory:", check_same_thread=False) as connection:
        record, path = confirm_benchmark(
            case, model, ledger, settings, SqliteSaver(connection), "a", lambda _: None
        )
        assert record["coverage_check"] == "passed" and path.exists()
        assert ledger.summary("a")["tool_calls"] == 0
        assert ledger.summary("a")["model_calls"] == 1
