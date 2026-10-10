from __future__ import annotations

import re
from dataclasses import dataclass, replace


@dataclass(frozen=True)
class PageText:
    page: int
    text: str
    sections: tuple[dict, ...] = ()


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    page_start: int
    page_end: int
    text: str
    page_spans: tuple[tuple[int, int, int], ...] = ()
    section: str | None = None


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _build_chunks(
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


CHUNKING_VERSION = '2-section-boundaries'


def build_chunks(pages: list[PageText], *, max_chars: int, overlap_chars: int) -> list[Chunk]:
    """Split at annotated section transitions; overlap never crosses a boundary."""
    if max_chars <= 0 or not 0 <= overlap_chars < max_chars:
        raise ValueError('Require max_chars > 0 and 0 <= overlap_chars < max_chars')
    groups = []
    for page in pages:
        spans = page.sections or ({'start': 0, 'end': len(page.text), 'section': None},)
        cursor = 0
        for span in spans:
            if span['start'] != cursor or not cursor <= span['end'] <= len(page.text):
                raise ValueError('Section spans must cover page text in order without gaps or overlaps')
            cursor = span['end']
            section = span['section']
            if not groups or groups[-1][0] != section:
                groups.append((section, []))
            groups[-1][1].append(PageText(page.page, page.text[span['start']:span['end']]))
        if cursor != len(page.text):
            raise ValueError('Section spans do not cover the complete page')
    chunks = []
    for section, fragments in groups:
        for chunk in _build_chunks(fragments, max_chars=max_chars, overlap_chars=overlap_chars):
            chunks.append(replace(chunk, chunk_id=f'chunk-{len(chunks) + 1:04d}', section=section))
    return chunks
