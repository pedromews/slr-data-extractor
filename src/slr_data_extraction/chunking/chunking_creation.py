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
    page_spans: tuple[tuple[int, int, int], ...] = ()


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def build_chunks(
    pages: list[PageText],
    *,
    max_chars: int,
    overlap_chars: int,
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

    # Keep page spans in the normalized document so overlap retains provenance.
    parts: list[str] = []
    spans: list[tuple[int, int, int]] = []
    offset = 0
    for page in pages:
        cleaned = _clean(page.text)
        if not cleaned:
            continue
        if parts:
            parts.append(" ")
            offset += 1
        spans.append((offset, offset + len(cleaned), page.page))
        parts.append(cleaned)
        offset += len(cleaned)

    document = "".join(parts)
    chunks: list[Chunk] = []
    start = 0
    while start < len(document):
        end = min(start + max_chars, len(document))
        contributing_pages = [
            page for page_start, page_end, page in spans
            if page_start < end and page_end > start
        ]
        # A one-character window can contain only an inter-page separator.
        # Attribute that separator to the preceding page.
        if not contributing_pages:
            contributing_pages = [next(
                page for _, page_end, page in spans if page_end == start
            )]
        chunks.append(Chunk(
            chunk_id=f"chunk-{len(chunks) + 1:04d}",
            page_start=contributing_pages[0],
            page_end=contributing_pages[-1],
            text=document[start:end],
            page_spans=tuple((max(a, start) - start, min(b, end) - start, page)
                             for a, b, page in spans if a < end and b > start),
        ))
        if end == len(document):
            break
        start = end - overlap_chars
    return chunks
