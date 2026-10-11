"""Deterministic evidence catalog; offsets index the unchanged chunk text."""
import re
from typing import Literal
from pydantic import Field
from ..definitions.result_definition import Output, FieldExtraction

SEGMENT_VERSION = "1-page-sentence-400"


class SelectedValue(Output):
    value: str = Field(min_length=1, pattern=r"\S")
    evidence_ids: list[str] = Field(min_length=1)


class SelectedField(Output):
    field_name: str
    status: Literal["extracted", "not_found_in_context"]
    values: list[SelectedValue]
    notes: str | None = None


def build_catalog(chunks):
    """Split at pages and sentence-like boundaries, then at 400 characters.

    No non-whitespace character is discarded. Long sentences use word boundaries
    when possible; pathological long tokens are split. Adjacent IDs may be cited
    together. Sentence detection is heuristic, not linguistic parsing.
    """
    catalog = {}
    for chunk in chunks:
        index = 0
        for a, b, page in chunk.page_spans:
            text = chunk.text[a:b]
            boundaries = [0] + [m.end() for m in re.finditer(r"[.!?]\s+", text)] + [len(text)]
            for left, right in zip(boundaries, boundaries[1:]):
                while left < right:
                    end = min(left + 400, right)
                    if end < right:
                        space = text.rfind(" ", left, end)
                        if space > left:
                            end = space
                    start = left
                    while start < end and text[start].isspace():
                        start += 1
                    stop = end
                    while stop > start and text[stop - 1].isspace():
                        stop -= 1
                    if stop > start:
                        index += 1
                        catalog[f"{chunk.chunk_id}-e{index:03d}"] = {
                            "start": a + start, "end": a + stop,
                            "quote": text[start:stop], "page_start": page,
                            "page_end": page, "section": chunk.section,
                            "chunk_id": chunk.chunk_id,
                        }
                    left = end
    return catalog


def resolve_selection(content, catalog):
    selected = SelectedField.model_validate_json(content)
    values = []
    for item in selected.values:
        evidence = []
        for identifier in item.evidence_ids:
            if identifier not in catalog:
                raise ValueError(f"Unknown or unselected evidence ID: {identifier}")
            entry = catalog[identifier]
            evidence.append({k: v for k, v in entry.items() if k not in {"start", "end"}})
        values.append({"value": item.value, "evidence": evidence})
    return FieldExtraction.model_validate({
        "field_name": selected.field_name, "status": selected.status,
        "values": values, "notes": selected.notes,
    })
