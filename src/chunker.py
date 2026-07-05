"""Fixed-size character chunking with overlap. Deliberately simple (per brief)."""

CHUNK_SIZE = 1200
CHUNK_OVERLAP = 200


def chunk_text(text: str) -> list[str]:
    step = CHUNK_SIZE - CHUNK_OVERLAP
    chunks: list[str] = []
    i = 0
    while i < len(text):
        piece = text[i : i + CHUNK_SIZE].strip()
        if piece:
            chunks.append(piece)
        if i + CHUNK_SIZE >= len(text):
            break
        i += step
    return chunks
