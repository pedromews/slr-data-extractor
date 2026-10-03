from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class PageText:
    page: int
    text: str


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    page_start: int
    page_end: int
    text: str


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def build_chunks(
    pages: list[PageText],
    *,
    max_chars: int = 6000,
    overlap_chars: int = 600,
) -> list[Chunk]:
    """Create deterministic chunks and retain the contributing page range.

    Character limits are a transparent baseline. The final protocol may replace
    them with tokenizer-aware limits, but every model must receive the same
    chunks in the main comparison.
    """
    if max_chars <= 0:
        raise ValueError("max_chars must be positive")
    if overlap_chars < 0 or overlap_chars >= max_chars:
        raise ValueError("overlap_chars must be between zero and max_chars")

    segments: list[tuple[int, str]] = []
    for page in pages:
        cleaned = _clean(page.text)
        if cleaned:
            segments.append((page.page, cleaned))

    chunks: list[Chunk] = []
    buffer = ""
    page_start: int | None = None
    page_end: int | None = None

    def flush() -> None:
        nonlocal buffer, page_start, page_end
        if not buffer or page_start is None or page_end is None:
            return
        chunks.append(
            Chunk(
                chunk_id=f"chunk-{len(chunks) + 1:04d}",
                page_start=page_start,
                page_end=page_end,
                text=buffer.strip(),
            )
        )
        buffer = buffer[-overlap_chars:] if overlap_chars else ""
        page_start = page_end if buffer else None

    for page, text in segments:
        cursor = 0
        while cursor < len(text):
            if page_start is None:
                page_start = page
            page_end = page
            available = max_chars - len(buffer)
            buffer += (" " if buffer else "") + text[cursor : cursor + available]
            cursor += available
            if len(buffer) >= max_chars:
                flush()

    flush()
    return chunks

