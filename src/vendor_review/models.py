"""Provider construction only; graph code owns call/token accounting and tool execution."""

import json
import uuid
from queue import Empty, Queue
from threading import Thread
from typing import Literal

from langchain_core.messages import AIMessage, SystemMessage
from pydantic import BaseModel, ConfigDict, Field


class LocalCall(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Literal[
        "account_access",
        "account_credits",
        "identify_company",
        "enrich_company",
        "web_search",
        "fetch_page",
        "update_intake",
        "record_findings",
        "search_people",
        "enrich_person",
        "search_person_posts",
        "register_reference",
        "record_coverage",
        "read_evidence",
    ]
    arguments: dict


class LocalDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reply: str = Field(
        description="Answer when no further tools are required; cite returned evidence"
    )
    calls: list[LocalCall] = Field(
        max_length=5, description="Tools to execute, or [] for final answer"
    )


class StructuredLocalModel:
    """Ollama JSON-schema actions; executor still validates each tool's exact arguments.

    A model action is not a tool success. Only captured REST results establish execution.
    This mode does not claim provider-native function calling.
    """

    def __init__(self, model):
        self.model = model

    def bind_tools(self, schemas):
        self.schemas = schemas
        self.structured = self.model.with_structured_output(
            LocalDecision, method="json_schema", include_raw=True
        )
        return self

    def invoke(self, messages):
        instruction = (
            "\nReturn a LocalDecision. Request tools using calls, never JSON inside reply. "
        )
        instruction += "Only answer using returned tool results. Tool contracts:\n" + json.dumps(
            self.schemas
        )
        prepared = [SystemMessage(content=str(messages[0].content) + instruction)] + messages[1:]
        output = self.structured.invoke(prepared)
        if output.get("parsing_error") or output.get("parsed") is None:
            raise ValueError("Local structured action did not match schema")
        decision = output["parsed"]
        raw = output["raw"]
        return AIMessage(
            content=decision.reply,
            tool_calls=[
                {
                    "name": call.name,
                    "args": call.arguments,
                    "id": uuid.uuid4().hex,
                    "type": "tool_call",
                }
                for call in decision.calls
            ],
            usage_metadata=raw.usage_metadata,
        )


def invoke_bounded(model, messages, seconds):
    """Bound caller wait even if a provider ignores its socket timeout.

    Timeout cannot guarantee provider cancellation: keep the token reservation and never
    execute a late model result's tool calls. The daemon only returns a value to this queue.
    """
    outcome = Queue(maxsize=1)

    def invoke():
        try:
            outcome.put((True, model.invoke(messages)))
        except Exception as exc:
            outcome.put((False, exc))

    Thread(target=invoke, daemon=True).start()
    try:
        ok, result = outcome.get(timeout=max(0.001, seconds))
    except Empty:
        raise TimeoutError("Provider outcome unknown after deadline") from None
    if not ok:
        raise result
    return result


def make_model(settings):
    if settings.model_provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI

        if not settings.gemini_api_key.get_secret_value():
            raise ValueError("GEMINI_API_KEY is required for MODEL_PROVIDER=gemini")
        return ChatGoogleGenerativeAI(
            model=settings.model_name,
            api_key=settings.gemini_api_key,
            max_output_tokens=settings.model_output_tokens,
            max_retries=0,
            timeout=settings.request_seconds,
        )
    from langchain_ollama import ChatOllama

    model = ChatOllama(
        model=settings.model_name,
        base_url=settings.ollama_base_url,
        num_predict=settings.model_output_tokens,
        temperature=0,
        client_kwargs={"timeout": settings.request_seconds},
        num_ctx=16384,
    )
    return StructuredLocalModel(model) if settings.ollama_tool_mode == "structured" else model
