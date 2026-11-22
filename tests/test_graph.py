import json
import sqlite3

import httpx
from conftest import MATCH, fixture_client
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.sqlite import SqliteSaver

from vendor_review.cli import abandon_pending, runtime_lock
from vendor_review.graph import build_graph, turn_input


class ScriptedModel:
    """Deterministic fixture; never represented as live model validation."""

    def __init__(self, replies):
        self.replies = iter(replies)
        self.inputs = []

    def bind_tools(self, schemas):
        assert {x["function"]["name"] for x in schemas} >= {"identify_company", "fetch_page"}
        return self

    def invoke(self, messages):
        self.inputs.append(messages)
        reply = next(self.replies)
        if isinstance(reply, Exception):
            raise reply
        return reply


def answer(content="fixture answer", calls=None):
    return AIMessage(
        content=content,
        tool_calls=calls or [],
        usage_metadata={"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
    )


def test_real_langgraph_loop_two_turns_restart_and_isolation(setup):
    settings, ledger = setup
    client = fixture_client(
        settings,
        ledger,
        lambda _: httpx.Response(200, json=MATCH, headers={"X-Credits-Used": "0.2"}),
    )
    model = ScriptedModel(
        [
            answer(
                "",
                [
                    {
                        "name": "identify_company",
                        "args": {"identifier": "example.com"},
                        "id": "call-1",
                        "type": "tool_call",
                    }
                ],
            ),
            answer("Example identified using provider record"),
            answer("Same Example company"),
        ]
    )
    path = settings.data_dir / "checkpoints.sqlite"
    config = {"configurable": {"thread_id": "a"}}
    with sqlite3.connect(path, check_same_thread=False) as connection:
        graph = build_graph(
            model, client, ledger, settings, SqliteSaver(connection), lambda _: None
        )
        first = graph.invoke(turn_input("Research Example at example.com", settings), config)
        assert any(isinstance(m, ToolMessage) for m in first["messages"])
        second = graph.invoke(turn_input("What company are we discussing?", settings), config)
        assert second["messages"][-1].content.startswith("Same Example company")
        assert "API evidence" in second["messages"][-1].content
        assert len([m for m in second["messages"] if isinstance(m, HumanMessage)]) == 2
    # Reopen an actual SQLite checkpointer, with a new graph/model object.
    restarted = ScriptedModel([answer("I retain Example")])
    with sqlite3.connect(path, check_same_thread=False) as connection:
        graph = build_graph(
            restarted, client, ledger, settings, SqliteSaver(connection), lambda _: None
        )
        graph.invoke(turn_input("Continue", settings), config)
        assert "example.com" in json.dumps(
            [m.model_dump() for m in restarted.inputs[0]], default=str
        )
        assert graph.get_state({"configurable": {"thread_id": "b"}}).values == {}
    client.close()


def test_multiple_calls_and_endless_model_stop_at_turn_limits(setup):
    settings, ledger = setup
    limited = settings.model_copy(update={"turn_tool_calls": 1, "turn_model_calls": 2})
    ledger.settings = limited
    count = []

    def handler(_):
        count.append(1)
        return httpx.Response(200, json=MATCH, headers={"X-Credits-Used": "0.2"})

    client = fixture_client(limited, ledger, handler)

    def calls(prefix):
        return [
            {
                "name": "identify_company",
                "args": {"identifier": "example.com"},
                "id": prefix + str(i),
                "type": "tool_call",
            }
            for i in range(3)
        ]

    model = ScriptedModel([answer("", calls("first")), answer("", calls("second"))])
    with sqlite3.connect(":memory:", check_same_thread=False) as connection:
        graph = build_graph(model, client, ledger, limited, SqliteSaver(connection), lambda _: None)
        result = graph.invoke(turn_input("research", limited), {"configurable": {"thread_id": "a"}})
        assert "model call limit" in result["messages"][-1].content
        assert len(count) == 1
        assert len(model.inputs) == 2
        assert len([m for m in result["messages"] if isinstance(m, ToolMessage)]) == 6
    client.close()


def test_model_failure_is_bounded_and_secrets_never_checkpointed(setup):
    settings, ledger = setup
    client = fixture_client(settings, ledger, lambda _: None)
    model = ScriptedModel([RuntimeError("contains test-secret-not-real")])
    with sqlite3.connect(":memory:", check_same_thread=False) as connection:
        graph = build_graph(
            model, client, ledger, settings, SqliteSaver(connection), lambda _: None
        )
        config = {"configurable": {"thread_id": "a"}}
        result = graph.invoke(turn_input("my key test-secret-not-real", settings), config)
        assert "test-secret-not-real" not in json.dumps(
            [m.model_dump() for m in result["messages"]]
        )
        assert ledger.summary("a")["token_usage_or_reservations"] > 0
        assert len(model.inputs) == 1
    client.close()


def test_interrupted_tool_checkpoint_is_abandoned_without_network(setup):
    settings, ledger = setup
    client = fixture_client(
        settings, ledger, lambda _: (_ for _ in ()).throw(AssertionError("network"))
    )
    model = ScriptedModel([])
    with sqlite3.connect(":memory:", check_same_thread=False) as connection:
        graph = build_graph(
            model, client, ledger, settings, SqliteSaver(connection), lambda _: None
        )
        config = {"configurable": {"thread_id": "a"}}
        state = turn_input("research", settings)
        state["messages"].append(
            answer(
                "",
                [
                    {
                        "name": "identify_company",
                        "args": {"identifier": "example.com"},
                        "id": "pending",
                        "type": "tool_call",
                    }
                ],
            )
        )
        graph.update_state(config, state, as_node="model")
        assert graph.get_state(config).next == ("tools",)
        abandon_pending(graph, config)
        assert not graph.get_state(config).next
        assert "interrupted" in graph.get_state(config).values["messages"][-1].content
        assert model.inputs == []
    client.close()


def test_runtime_lock_blocks_concurrent_writer(tmp_path):
    import pytest

    with runtime_lock(tmp_path / "app.lock"):
        with pytest.raises(ValueError):
            with runtime_lock(tmp_path / "app.lock"):
                pass


def test_model_deadline_rejects_late_tool_call_without_dispatch(setup):
    import time

    settings, ledger = setup
    limited = settings.model_copy(update={"request_seconds": 0.02})

    class SlowModel(ScriptedModel):
        def invoke(self, messages):
            time.sleep(0.1)
            return answer(
                "",
                [
                    {
                        "name": "identify_company",
                        "args": {"identifier": "example.com"},
                        "id": "late",
                        "type": "tool_call",
                    }
                ],
            )

    client = fixture_client(
        limited, ledger, lambda _: (_ for _ in ()).throw(AssertionError("late dispatch"))
    )
    with sqlite3.connect(":memory:", check_same_thread=False) as connection:
        graph = build_graph(
            SlowModel([]), client, ledger, limited, SqliteSaver(connection), lambda _: None
        )
        result = graph.invoke(turn_input("research", limited), {"configurable": {"thread_id": "a"}})
        assert "TimeoutError" in result["messages"][-1].content
        assert ledger.summary("a")["tool_calls"] == 0
        assert ledger.summary("a")["token_usage_or_reservations"] > 0
    client.close()
