"""p2-docs-assistant M2 — public ask API + embeddable widget + admin view.

Public surface: /ask (rate-limited, CORS-open for the embed), /widget.js,
/demo, /health. Admin surface (X-Admin-Key): /ingest, /documents,
/admin/questions, /admin. Boots with no env vars; endpoints needing external
services answer 503 naming exactly what is missing (see src/config.py).
"""

import hmac
import time
from collections import defaultdict, deque
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from kit_logger import create_logger

from . import config, db, rag
from .chunker import chunk_text
from .embeddings import get_embedder
from .extract import SUPPORTED_EXTENSIONS, extract_units, safe_filename

log = create_logger("api")

app = FastAPI(title="p2-docs-assistant", version="0.2.0")

# The widget embeds on client sites, so /ask must accept cross-origin POSTs.
# Only Content-Type is allowed through, which keeps X-Admin-Key endpoints
# unreachable from other origins (their preflight fails).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)

STATIC_DIR = Path(__file__).resolve().parents[1] / "static"


def _require(required: list[str]) -> None:
    missing = config.missing(required)
    if missing:
        raise HTTPException(
            status_code=503,
            detail=f"not configured - set in .env: {', '.join(missing)}",
        )


def _require_admin(request: Request) -> None:
    configured = config.admin_key()
    if not configured:
        raise HTTPException(status_code=503, detail="not configured - set ADMIN_KEY in .env")
    provided = request.headers.get("x-admin-key", "")
    if not hmac.compare_digest(provided.encode(), configured.encode()):
        raise HTTPException(status_code=401, detail="invalid admin key")


# --- public rate limit on /ask (per IP, sliding minute) ---------------------

_ask_windows: dict[str, deque] = defaultdict(deque)


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _rate_limited(ip: str) -> bool:
    now = time.monotonic()
    window = _ask_windows[ip]
    while window and now - window[0] > 60:
        window.popleft()
    if len(window) >= config.rate_limit_per_min():
        return True
    window.append(now)
    return False


# --- public endpoints --------------------------------------------------------

@app.get("/health")
def health() -> dict:
    return {"status": "ok", "missing_config": config.missing(config.ASK_REQUIRES)}


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)


@app.post("/ask")
def ask(request: AskRequest, http_request: Request) -> dict:
    ip = _client_ip(http_request)
    if _rate_limited(ip):
        log.warn("ask_rate_limited", ip=ip)
        raise HTTPException(status_code=429, detail="too many requests - try again in a minute")
    _require(config.ASK_REQUIRES)
    log.info("ask_received", question=request.question)
    started = time.monotonic()
    try:
        response = rag.ask(request.question)
    except httpx.HTTPError as err:
        log.error("ask_embed_failed", error=str(err))
        raise HTTPException(status_code=502, detail="embeddings call failed")
    # Record for the admin view; a logging failure must never break the answer.
    try:
        db.insert_question(
            request.question, response["answer"], response["confident"], response["citations"]
        )
    except Exception as err:
        log.warn("question_log_failed", error=str(err))
    log.info(
        "ask_completed",
        confident=response["confident"],
        ms=int((time.monotonic() - started) * 1000),
    )
    return response


@app.get("/widget.js")
def widget_js() -> FileResponse:
    return FileResponse(STATIC_DIR / "widget.js", media_type="application/javascript")


@app.get("/demo")
def demo_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "embed-demo.html", media_type="text/html")


# --- admin endpoints (X-Admin-Key) -------------------------------------------

@app.get("/admin")
def admin_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "admin.html", media_type="text/html")


@app.get("/admin/questions")
def admin_questions(request: Request, unanswered: bool = False, limit: int = 100) -> dict:
    _require_admin(request)
    _require(config.INGEST_REQUIRES[:2])  # Supabase only
    try:
        rows = db.list_questions(unanswered_only=unanswered, limit=min(max(limit, 1), 500))
    except Exception as err:
        log.error("questions_read_failed", error=str(err))
        raise HTTPException(
            status_code=502,
            detail="database read failed - has the latest supabase/schema.sql been run?",
        )
    return {"questions": rows}


@app.post("/ingest")
async def ingest(request: Request, files: list[UploadFile]) -> dict:
    _require_admin(request)
    _require(config.INGEST_REQUIRES)
    if not files:
        raise HTTPException(status_code=400, detail="no files uploaded")

    # Validate everything before ingesting anything.
    named = [(safe_filename(f.filename or ""), f) for f in files]
    for name, _ in named:
        if not name.lower().endswith(SUPPORTED_EXTENSIONS):
            raise HTTPException(
                status_code=400,
                detail=f"unsupported file type: {name or '(unnamed)'} "
                f"(supported: {', '.join(SUPPORTED_EXTENSIONS)})",
            )

    embedder = get_embedder()
    ingested = []
    for name, upload in named:
        started = time.monotonic()
        data = await upload.read()
        log.info("ingest_received", filename=name, bytes=len(data))

        units = extract_units(name, data)
        rows = []
        for page, text in units:
            for piece in chunk_text(text):
                rows.append(
                    {
                        "filename": name,
                        "chunk_index": len(rows),
                        "page": page,
                        "content": piece,
                    }
                )
        if not rows:
            raise HTTPException(
                status_code=400, detail=f"no extractable text in {name}"
            )

        try:
            vectors = embedder.embed([r["content"] for r in rows], input_type="document")
        except httpx.HTTPError as err:
            log.error("ingest_embed_failed", filename=name, error=str(err))
            raise HTTPException(status_code=502, detail="embeddings call failed")
        for row, vector in zip(rows, vectors):
            row["embedding"] = vector

        try:
            db.replace_chunks(name, rows)
        except Exception as err:
            log.error("ingest_store_failed", filename=name, error=str(err))
            raise HTTPException(status_code=502, detail="database write failed")

        pages = max((r["page"] or 0 for r in rows), default=0) or None
        log.info(
            "ingest_stored",
            filename=name,
            chunks=len(rows),
            pages=pages,
            ms=int((time.monotonic() - started) * 1000),
        )
        ingested.append({"filename": name, "chunks": len(rows), "pages": pages})

    return {"ingested": ingested}


@app.get("/documents")
def documents(request: Request) -> dict:
    _require_admin(request)
    _require(config.INGEST_REQUIRES[:2])  # Supabase only
    return {"documents": db.list_documents()}


@app.delete("/documents/{filename}")
def delete_document(request: Request, filename: str) -> dict:
    _require_admin(request)
    _require(config.INGEST_REQUIRES[:2])  # Supabase only
    name = safe_filename(filename)
    deleted = db.delete_chunks(name)
    if deleted == 0:
        raise HTTPException(status_code=404, detail=f"no chunks stored for {name}")
    log.info("document_deleted", filename=name, chunks=deleted)
    return {"deleted": name, "chunks": deleted}
