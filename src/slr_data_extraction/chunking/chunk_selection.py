from __future__ import annotations

import re
import math
from collections import Counter

from .chunking_creation import Chunk


def _terms(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9][a-z0-9_-]+", text.lower()))


def rank_chunks(chunks: list[Chunk], query_terms: list[str], top_k: int, *, method: str = "lexical") -> list[Chunk]:
    """Transparent lexical retrieval baseline with stable tie-breaking."""
    if top_k <= 0:
        raise ValueError("top_k must be positive")
    if method == "bm25":
        scores = bm25_scores(chunks, query_terms)
        order = sorted(range(len(chunks)), key=lambda i: (-scores[i], i))
        return [chunks[i] for i in order[:top_k]]
    if method != "lexical":
        raise ValueError("Unknown selection_method")
    query = set()
    for term in query_terms:
        query.update(_terms(term))
    scored = []
    for index, chunk in enumerate(chunks):
        overlap = len(query & _terms(chunk.text))
        scored.append((overlap, -index, chunk))
    scored.sort(reverse=True, key=lambda row: (row[0], row[1]))
    return [row[2] for row in scored[:top_k]]



SELECTION_VERSIONS = {"lexical": "1-word-overlap", "bm25": "1-bm25-plural"}


def bm25_tokens(text: str) -> list[str]:
    """English lexical normalization only; never modify source evidence.

    Split hyphens/underscores and normalize common plural suffixes. This is a
    heuristic, not a lemmatizer; irregular forms and PDF broken words remain.
    """
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    result = []
    for token in tokens:
        if len(token) > 4 and token.endswith("ies"):
            token = token[:-3] + "y"
        elif len(token) > 3 and token.endswith("s") and not token.endswith(("ss", "us", "is", "as")):
            token = token[:-1]
        result.append(token)
    return result


def bm25_scores(chunks: list[Chunk], query_terms: list[str]) -> list[float]:
    """Okapi BM25 with positive IDF, fixed k1=1.5 and b=0.75.

    The corpus is all article chunks, including overlap. Query terms are unique;
    ties use document order in rank_chunks. No reference annotations are used.
    """
    if not chunks:
        return []
    documents = [Counter(bm25_tokens(c.text)) for c in chunks]
    lengths = [sum(d.values()) for d in documents]
    average = sum(lengths) / len(documents)
    if not average:
        return [0.0] * len(chunks)
    query = sorted(set(bm25_tokens(" ".join(query_terms))))
    frequencies = {term: sum(term in doc for doc in documents) for term in query}
    scores = []
    for doc, length in zip(documents, lengths):
        score = 0.0
        for term in query:
            tf = doc[term]
            if tf:
                df = frequencies[term]
                idf = math.log(1 + (len(documents) - df + 0.5) / (df + 0.5))
                score += idf * tf * 2.5 / (tf + 1.5 * (0.25 + 0.75 * length / average))
        scores.append(score)
    return scores
