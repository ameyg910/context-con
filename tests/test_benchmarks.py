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
    assert len(case["requirements"]) == 8 and len(case["checks"]) == 13
    assert len(load_benchmark("project44", "1.0.0")["checks"]) == 12
    assert {"R2", "R3", "R4", "R5", "R6"} <= {r["id"] for r in case["requirements"]}
    text = benchmark_prompt(case, True)
    assert "631278" not in text and "documented_interface_not_runtime_verified" not in text
    assert "Girteka" in text and "85%" in text and "Asendia" in text
    assert "No research, no tools" in text
    assert len(text) <= 8000


def test_v1_0_0_is_preserved_and_v1_1_0_only_adds_branch_scope():
    old, new = load_benchmark("project44", "1.0.0"), load_benchmark("project44")
    assert old["version"] == "1.0.0" and new["version"] == "1.1.0"
    assert new["checks"][:12] == old["checks"] and new["checks"][12]["id"] == "G13"
    assert [r["question"] for r in new["requirements"]] == [
        r["question"] for r in old["requirements"]
    ]
    assert new["missing_buyer_inputs"] == old["missing_buyer_inputs"]
    stages = {r["id"]: r["stage"] for r in new["requirements"]}
    assert stages["R3"] == "customer_corroboration"
    assert old["requirements"][2]["stage"] == "deferred_customer_corroboration"
    assert "enabled read-only customer/professional" in benchmark_prompt(new, True)
    assert "deferred customer/professional corroboration" in benchmark_prompt(old, True)
    for case in (old, new):
        text = benchmark_prompt(case, True)
        assert "631278" not in text and "legacy_claims" not in text and len(text) <= 8000
    with pytest.raises(ValueError):
        load_benchmark("project44", "9.9.9")


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
