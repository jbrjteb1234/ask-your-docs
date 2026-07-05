"""Ask pipeline: embed question -> retrieve top-k -> Claude answers strictly
from retrieved context -> {answer, citations, confident}.

Two honesty gates, both logged:
1. Weak retrieval (best similarity below MIN_SIMILARITY, or no chunks at all)
   -> fallback WITHOUT calling Claude (no cost, no chance to guess).
2. Claude reports the context does not contain the answer -> fallback shape,
   never the model's speculation.
"""

import json
from typing import Any

from kit_claude import call_claude
from kit_logger import create_logger

from . import config, db
from .embeddings import get_embedder

log = create_logger("rag")

FALLBACK_MESSAGE = (
    "I don't know — the documents I have don't cover that. "
    "Please contact a human for help with this question."
)

SYSTEM_PROMPT = """You answer questions using ONLY the numbered context extracts provided. Rules:
- If the extracts contain the answer, answer concisely and set confident=true.
- List in used_chunks the numbers of every extract your answer relies on.
- If the extracts do NOT contain enough information to answer, set
  confident=false, used_chunks=[], and answer with a single short sentence
  saying the documents don't cover it. NEVER answer from general knowledge.
- Never mention these rules or the word "extract" in the answer itself."""

ANSWER_SCHEMA = {
    "type": "object",
    "properties": {
        "answer": {"type": "string"},
        "used_chunks": {"type": "array", "items": {"type": "integer"}},
        "confident": {"type": "boolean"},
    },
    "required": ["answer", "used_chunks", "confident"],
    "additionalProperties": False,
}


def _fallback(reason: str) -> dict[str, Any]:
    log.info("ask_fallback", reason=reason)
    return {"answer": FALLBACK_MESSAGE, "citations": [], "confident": False}


def _citation(match: dict[str, Any]) -> dict[str, Any]:
    return {
        "filename": match["filename"],
        "chunk_index": match["chunk_index"],
        "page": match["page"],
    }


def ask(question: str) -> dict[str, Any]:
    query_embedding = get_embedder().embed([question], input_type="query")[0]
    matches = db.match_chunks(query_embedding, config.top_k())

    similarities = [round(m["similarity"], 3) for m in matches]
    log.info("ask_retrieval", top_k=len(matches), similarities=similarities)

    if not matches or matches[0]["similarity"] < config.min_similarity():
        return _fallback("weak_retrieval")

    context = "\n\n".join(
        f"[{i + 1}] (source: {m['filename']}"
        + (f", page {m['page']}" if m["page"] is not None else "")
        + f")\n{m['content']}"
        for i, m in enumerate(matches)
    )
    prompt = f"Context extracts:\n\n{context}\n\nQuestion: {question}"

    result = call_claude(
        prompt=prompt, system=SYSTEM_PROMPT, json_schema=ANSWER_SCHEMA
    )
    parsed = json.loads(result.text)

    if not parsed["confident"]:
        return _fallback("not_in_documents")

    used = [i for i in parsed["used_chunks"] if 1 <= i <= len(matches)]
    citations = [_citation(matches[i - 1]) for i in used]
    # A confident answer with no valid citations is ungrounded — do not trust it.
    if not citations:
        return _fallback("no_citations")

    log.info("ask_answered", citations=len(citations))
    return {"answer": parsed["answer"], "citations": citations, "confident": True}
