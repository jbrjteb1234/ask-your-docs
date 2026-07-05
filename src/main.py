"""p2-docs-assistant M1 — bare HTTP API: ingest documents, ask grounded questions.

Boots with no env vars; endpoints needing external services answer 503 naming
exactly what is missing (see src/config.py).
"""

import time

import httpx
from fastapi import FastAPI, HTTPException, UploadFile
from pydantic import BaseModel, Field

from kit_logger import create_logger

from . import config, db, rag
from .chunker import chunk_text
from .embeddings import get_embedder
from .extract import SUPPORTED_EXTENSIONS, extract_units, safe_filename

log = create_logger("api")

app = FastAPI(title="p2-docs-assistant", version="0.1.0")


def _require(required: list[str]) -> None:
    missing = config.missing(required)
    if missing:
        raise HTTPException(
            status_code=503,
            detail=f"not configured — set in .env: {', '.join(missing)}",
        )


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "missing_config": config.missing(config.ASK_REQUIRES)}


@app.post("/ingest")
async def ingest(files: list[UploadFile]) -> dict:
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


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)


@app.post("/ask")
def ask(request: AskRequest) -> dict:
    _require(config.ASK_REQUIRES)
    log.info("ask_received", question=request.question)
    started = time.monotonic()
    try:
        response = rag.ask(request.question)
    except httpx.HTTPError as err:
        log.error("ask_embed_failed", error=str(err))
        raise HTTPException(status_code=502, detail="embeddings call failed")
    log.info(
        "ask_completed",
        confident=response["confident"],
        ms=int((time.monotonic() - started) * 1000),
    )
    return response


@app.get("/documents")
def documents() -> dict:
    _require(config.INGEST_REQUIRES[:2])  # Supabase only
    return {"documents": db.list_documents()}


@app.delete("/documents/{filename}")
def delete_document(filename: str) -> dict:
    _require(config.INGEST_REQUIRES[:2])  # Supabase only
    name = safe_filename(filename)
    deleted = db.delete_chunks(name)
    if deleted == 0:
        raise HTTPException(status_code=404, detail=f"no chunks stored for {name}")
    log.info("document_deleted", filename=name, chunks=deleted)
    return {"deleted": name, "chunks": deleted}
