from __future__ import annotations

import re

from .chunking_creation import Chunk


def _terms(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9][a-z0-9_-]+", text.lower()))


def rank_chunks(chunks: list[Chunk], query_terms: list[str], top_k: int) -> list[Chunk]:
    """Transparent lexical retrieval baseline with stable tie-breaking."""
    if top_k <= 0:
        raise ValueError("top_k must be positive")
    query = set()
    for term in query_terms:
        query.update(_terms(term))
    scored = []
    for index, chunk in enumerate(chunks):
        overlap = len(query & _terms(chunk.text))
        scored.append((overlap, -index, chunk))
    scored.sort(reverse=True, key=lambda row: (row[0], row[1]))
    return [row[2] for row in scored[:top_k]]

