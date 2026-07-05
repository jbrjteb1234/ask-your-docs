"""Claude API wrapper — Python variant of /kit/ts/claude.

Retries with backoff + 60s timeout via SDK config, model from ANTHROPIC_MODEL
env (default claude-opus-4-8), per-call token counts + estimated USD cost
logged through kit-logger, optional JSON-schema structured output.

kit-logger is a /kit sibling (not on PyPI), so it is not declared as a
dependency here — install both, in the same requirements.txt.
"""

import os
import time
from dataclasses import dataclass
from typing import Any

from anthropic import Anthropic
from kit_logger import create_logger

__all__ = ["ClaudeCallResult", "build_request_params", "call_claude"]

log = create_logger("kit.claude")

# USD per million tokens; extend as models are added. Unknown models log cost_usd: None.
PRICES_PER_MTOK: dict[str, dict[str, float]] = {
    "claude-fable-5": {"input": 10, "output": 50},
    "claude-opus-4-8": {"input": 5, "output": 25},
    "claude-opus-4-7": {"input": 5, "output": 25},
    "claude-opus-4-6": {"input": 5, "output": 25},
    "claude-sonnet-5": {"input": 3, "output": 15},
    "claude-sonnet-4-6": {"input": 3, "output": 15},
    "claude-haiku-4-5": {"input": 1, "output": 5},
}

DEFAULT_MODEL = "claude-opus-4-8"
DEFAULT_MAX_TOKENS = 2048
TIMEOUT_S = 60.0
# The SDK retries 429/5xx/connection errors with exponential backoff.
MAX_RETRIES = 3

_client: Anthropic | None = None


def _get_client() -> Anthropic:
    global _client
    if _client is None:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise RuntimeError("ANTHROPIC_API_KEY is not set")
        _client = Anthropic(timeout=TIMEOUT_S, max_retries=MAX_RETRIES)
    return _client


@dataclass
class ClaudeCallResult:
    text: str
    stop_reason: str | None
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float | None


def build_request_params(
    prompt: str,
    system: str | None = None,
    max_tokens: int | None = None,
    json_schema: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Builds the exact request body call_claude would send — exported so dry-run
    previews are guaranteed identical to the real request. Needs no API key.
    """
    params: dict[str, Any] = {
        "model": os.environ.get("ANTHROPIC_MODEL") or DEFAULT_MODEL,
        "max_tokens": max_tokens if max_tokens is not None else DEFAULT_MAX_TOKENS,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        params["system"] = system
    if json_schema:
        params["output_config"] = {
            "format": {"type": "json_schema", "schema": json_schema}
        }
    return params


def call_claude(
    prompt: str,
    system: str | None = None,
    max_tokens: int | None = None,
    json_schema: dict[str, Any] | None = None,
) -> ClaudeCallResult:
    params = build_request_params(prompt, system, max_tokens, json_schema)
    model = params["model"]
    # output_config goes via extra_body so this works even where the installed
    # SDK version does not yet expose it as a typed parameter.
    output_config = params.pop("output_config", None)
    extra: dict[str, Any] = {}
    if output_config:
        extra["extra_body"] = {"output_config": output_config}

    started = time.monotonic()
    try:
        response = _get_client().messages.create(**params, **extra)

        text = "".join(b.text for b in response.content if b.type == "text")
        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens
        price = PRICES_PER_MTOK.get(model)
        cost_usd = (
            (input_tokens * price["input"] + output_tokens * price["output"]) / 1_000_000
            if price
            else None
        )

        log.info(
            "claude_call",
            model=model,
            ms=int((time.monotonic() - started) * 1000),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
            stop_reason=response.stop_reason,
        )

        return ClaudeCallResult(
            text=text,
            stop_reason=response.stop_reason,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
        )
    except Exception as err:
        log.error(
            "claude_call_failed",
            model=model,
            ms=int((time.monotonic() - started) * 1000),
            error=str(err),
        )
        raise
