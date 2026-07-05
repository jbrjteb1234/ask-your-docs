"""Text extraction: PDF (per page, so citations can name pages) and text/markdown."""

import io
from pathlib import PurePosixPath, PureWindowsPath

from pypdf import PdfReader

SUPPORTED_EXTENSIONS = (".pdf", ".txt", ".md")


def safe_filename(raw: str) -> str:
    """Strip any client-supplied path components; keep just the base name."""
    return PurePosixPath(PureWindowsPath(raw).as_posix()).name


def extract_units(filename: str, data: bytes) -> list[tuple[int | None, str]]:
    """Returns (page, text) units — one per PDF page, or a single (None, text)
    for text/markdown. Raises ValueError for unsupported types.
    """
    name = filename.lower()
    if name.endswith(".pdf"):
        reader = PdfReader(io.BytesIO(data))
        return [(i + 1, page.extract_text() or "") for i, page in enumerate(reader.pages)]
    if name.endswith((".txt", ".md")):
        return [(None, data.decode("utf-8", errors="replace"))]
    raise ValueError(
        f"unsupported file type: {filename} (supported: {', '.join(SUPPORTED_EXTENSIONS)})"
    )
