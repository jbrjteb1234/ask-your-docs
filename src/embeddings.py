"""Embeddings behind a thin interface so the provider is swappable via env.

Chosen provider: Voyage AI (voyage-3.5-lite) — near-zero cost ($0.02/1M tokens,
200M free tokens on signup) and the embeddings partner Anthropic's docs point
to. Swap by implementing Embedder and adding a branch in get_embedder().
"""

import os
import time
from typing import Literal, Protocol

import httpx

from kit_logger import create_logger

from . import config

log = create_logger("embeddings")

# USD per million tokens; unknown models log cost_usd: None.
VOYAGE_PRICES_PER_MTOK = {
    "voyage-3.5-lite": 0.02,
    "voyage-3.5": 0.06,
    "voyage-3-large": 0.18,
}

VOYAGE_URL = "https://api.voyageai.com/v1/embeddings"
BATCH_SIZE = 128
TIMEOUT_S = 60.0

InputType = Literal["document", "query"]


class Embedder(Protocol):
    def embed(self, texts: list[str], input_type: InputType) -> list[list[float]]: ...


class VoyageEmbedder:
    def __init__(self) -> None:
        self.model = config.embeddings_model()
        self.api_key = os.environ.get("VOYAGE_API_KEY", "")

    def embed(self, texts: list[str], input_type: InputType) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), BATCH_SIZE):
            vectors.extend(self._embed_batch(texts[start : start + BATCH_SIZE], input_type))
        return vectors

    def _embed_batch(self, batch: list[str], input_type: InputType) -> list[list[float]]:
        started = time.monotonic()
        response = httpx.post(
            VOYAGE_URL,
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": self.model,
                "input": batch,
                "input_type": input_type,
                "output_dimension": config.embeddings_dim(),
            },
            timeout=TIMEOUT_S,
        )
        response.raise_for_status()
        body = response.json()
        total_tokens = body.get("usage", {}).get("total_tokens")
        price = VOYAGE_PRICES_PER_MTOK.get(self.model)
        cost_usd = (
            total_tokens * price / 1_000_000
            if price is not None and total_tokens is not None
            else None
        )
        log.info(
            "embed_call",
            provider="voyage",
            model=self.model,
            input_type=input_type,
            texts=len(batch),
            ms=int((time.monotonic() - started) * 1000),
            total_tokens=total_tokens,
            cost_usd=cost_usd,
        )
        ordered = sorted(body["data"], key=lambda d: d["index"])
        return [d["embedding"] for d in ordered]


def get_embedder() -> Embedder:
    provider = config.embeddings_provider()
    if provider == "voyage":
        return VoyageEmbedder()
    raise ValueError(f"unknown EMBEDDINGS_PROVIDER: {provider}")
