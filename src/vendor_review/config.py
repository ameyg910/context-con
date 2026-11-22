"""Validated local configuration and one redaction boundary for persisted/displayed data."""

import os
import re
from decimal import Decimal
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator


class Settings(BaseModel):
    model_config = ConfigDict(frozen=True)
    crustdata_api_key: SecretStr = SecretStr("")
    gemini_api_key: SecretStr = SecretStr("")
    model_provider: Literal["gemini", "ollama"] = "gemini"
    model_name: str = "gemini-3.1-flash-lite"
    ollama_base_url: str = "http://localhost:11434"
    ollama_tool_mode: Literal["native", "structured"] = "structured"
    data_dir: Path = Path(".local/runtime")
    session_credits: Decimal = Field(default=Decimal("10"), ge=0, le=1000)
    turn_credits: Decimal = Field(default=Decimal("5"), ge=0, le=1000)
    turn_tool_calls: int = Field(default=10, ge=1, le=20)
    session_tool_calls: int = Field(default=40, ge=1, le=1000)
    turn_model_calls: int = Field(default=10, ge=1, le=20)
    session_model_calls: int = Field(default=30, ge=1, le=1000)
    session_model_tokens: int = Field(default=100000, ge=1, le=10000000)
    model_output_tokens: int = Field(default=2048, ge=64, le=8192)
    turn_seconds: float = Field(default=120, gt=0, le=600)
    request_seconds: float = Field(default=30, gt=0, le=60)
    model_input_usd_per_million: Decimal | None = Field(default=None, ge=0)
    model_output_usd_per_million: Decimal | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def local_model_is_explicit(self):
        if self.model_provider == "gemini" and self.model_name not in {
            "gemini-3.8-flash",
            "gemini-3.1-flash-lite",
        }:
            raise ValueError(
                "This build permits only documented free-tier Gemini models; no paid fallback"
            )
        if self.model_provider == "gemini" and any(
            rate is not None and rate > 0
            for rate in (self.model_input_usd_per_million, self.model_output_usd_per_million)
        ):
            raise ValueError(
                "Gemini is free-tier only in this build; positive paid rates are not allowed"
            )
        if self.model_provider == "ollama" and self.model_name.startswith("gemini-"):
            raise ValueError("Set MODEL_NAME to an installed Ollama model with tool support")
        if self.model_provider == "ollama":
            from urllib.parse import urlsplit

            url = urlsplit(self.ollama_base_url)
            if url.hostname not in {"localhost", "127.0.0.1", "::1"} or url.scheme != "http":
                raise ValueError("OLLAMA_BASE_URL must be a local HTTP server")
        return self

    @classmethod
    def load(cls):
        load_dotenv(override=False)
        # This local app does not send conversation traces to an external observability service.
        os.environ["LANGSMITH_TRACING"] = "false"
        os.environ["LANGCHAIN_TRACING_V2"] = "false"
        values = {
            name: os.environ[name.upper()]
            for name in cls.model_fields
            if os.environ.get(name.upper(), "")
        }
        return cls(**values)

    def redact(self, value):
        if isinstance(value, dict):
            return {str(k): self.redact(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [self.redact(v) for v in value]
        if not isinstance(value, str):
            return value
        for secret in (self.crustdata_api_key, self.gemini_api_key):
            if secret.get_secret_value():
                value = value.replace(secret.get_secret_value(), "[REDACTED]")
        value = re.sub(
            r"(?i)Bearer\s+(?!authentication\b|auth\b|token\b)[^\s\"']+", "Bearer [REDACTED]", value
        )
        return re.sub(r"(?:cd_[A-Za-z0-9_-]{16,}|AIza[A-Za-z0-9_-]{20,})", "[REDACTED]", value)
