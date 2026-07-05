"""Supabase access: chunk storage, per-file replace/delete, vector retrieval."""

import os
from collections import defaultdict
from typing import Any

from supabase import Client, create_client

_client: Client | None = None


def get_db() -> Client:
    global _client
    if _client is None:
        _client = create_client(
            os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"]
        )
    return _client


def replace_chunks(filename: str, rows: list[dict[str, Any]]) -> None:
    """Delete-then-insert so re-ingesting a changed file never duplicates."""
    db = get_db()
    db.table("chunks").delete().eq("filename", filename).execute()
    if rows:
        db.table("chunks").insert(rows).execute()


def delete_chunks(filename: str) -> int:
    result = get_db().table("chunks").delete().eq("filename", filename).execute()
    return len(result.data or [])


def list_documents() -> list[dict[str, Any]]:
    result = get_db().table("chunks").select("filename, page").execute()
    by_file: dict[str, dict[str, Any]] = defaultdict(lambda: {"chunks": 0, "pages": 0})
    for row in result.data or []:
        info = by_file[row["filename"]]
        info["chunks"] += 1
        if row["page"] is not None:
            info["pages"] = max(info["pages"], row["page"])
    return [
        {"filename": name, "chunks": info["chunks"], "pages": info["pages"] or None}
        for name, info in sorted(by_file.items())
    ]


def match_chunks(query_embedding: list[float], match_count: int) -> list[dict[str, Any]]:
    result = get_db().rpc(
        "match_chunks",
        {"query_embedding": query_embedding, "match_count": match_count},
    ).execute()
    return result.data or []


def insert_question(
    question: str, answer: str, confident: bool, citations: list[dict[str, Any]]
) -> None:
    get_db().table("questions").insert(
        {
            "question": question,
            "answer": answer,
            "confident": confident,
            "citations": citations,
        }
    ).execute()


def list_questions(unanswered_only: bool, limit: int) -> list[dict[str, Any]]:
    query = (
        get_db()
        .table("questions")
        .select("id, question, answer, confident, citations, created_at")
        .order("created_at", desc=True)
        .limit(limit)
    )
    if unanswered_only:
        query = query.eq("confident", False)
    return query.execute().data or []
