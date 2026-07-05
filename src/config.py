"""Env-backed configuration with honest missing-config reporting.

The app must boot and answer /health with NO env vars set; endpoints that
need external services return 503 naming exactly what is missing.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# app/.env regardless of where the process was started from
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

# What each endpoint needs to do real work.
INGEST_REQUIRES = ["SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "VOYAGE_API_KEY"]
ASK_REQUIRES = INGEST_REQUIRES + ["ANTHROPIC_API_KEY"]


def missing(required: list[str]) -> list[str]:
    return [name for name in required if not os.environ.get(name)]


def embeddings_provider() -> str:
    return os.environ.get("EMBEDDINGS_PROVIDER", "voyage")


def embeddings_model() -> str:
    return os.environ.get("EMBEDDINGS_MODEL", "voyage-3.5-lite")


def embeddings_dim() -> int:
    return int(os.environ.get("EMBEDDINGS_DIM", "1024"))


def top_k() -> int:
    return int(os.environ.get("TOP_K", "5"))


def min_similarity() -> float:
    return float(os.environ.get("MIN_SIMILARITY", "0.30"))


def admin_key() -> str:
    return os.environ.get("ADMIN_KEY", "")


def contact_email() -> str:
    return os.environ.get("CONTACT_EMAIL", "")


def rate_limit_per_min() -> int:
    return int(os.environ.get("RATE_LIMIT_PER_MIN", "10"))


def trust_proxy() -> bool:
    # Only when the app runs behind a proxy we control (Railway, nginx) is
    # X-Forwarded-For trustworthy. Off by default: a direct client must not be
    # able to forge its own rate-limit identity.
    return os.environ.get("TRUST_PROXY", "").lower() in ("1", "true", "yes")
