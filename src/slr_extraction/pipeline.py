from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from openai import OpenAI

from .chunking import Chunk, PageText, build_chunks
from .models import ArticleExtraction, FieldExtraction
from .retrieval import rank_chunks


SYSTEM_PROMPT = """You extract data from primary studies for a systematic
literature review. Use only the supplied passages. Every extracted value must
have verbatim evidence and the exact page and chunk identifiers supplied in
the context. Do not use outside knowledge. Do not infer an absent value.
Return not_reported=true when the passages do not support a value."""


class ExtractionPipeline:
    def __init__(
        self,
        schema_path: str | Path,
        model_id: str,
        *,
        client: OpenAI | None = None,
        top_k: int = 6,
        temperature: float = 0.0,
    ) -> None:
        self.schema = json.loads(Path(schema_path).read_text(encoding="utf-8"))
        self.model_id = model_id
        self.client = client or OpenAI()
        self.top_k = top_k
        self.temperature = temperature

    @staticmethod
    def _context(chunks: list[Chunk]) -> str:
        parts = []
        for chunk in chunks:
            parts.append(
                f"[{chunk.chunk_id}; pages {chunk.page_start}-{chunk.page_end}]\n"
                f"{chunk.text}"
            )
        return "\n\n".join(parts)

    def _extract_field(self, field: dict[str, Any], chunks: list[Chunk]) -> FieldExtraction:
        selected = rank_chunks(chunks, field.get("retrieval_terms", []), self.top_k)
        prompt = f"""Study extraction field: {field['name']}
Definition: {field['description']}
Cardinality: {field['cardinality']}
Rules: {json.dumps(field.get('rules', []), ensure_ascii=False)}

Passages:
{self._context(selected)}
"""
        response = self.client.responses.parse(
            model=self.model_id,
            input=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            text_format=FieldExtraction,
            temperature=self.temperature,
        )
        result = response.output_parsed
        if result.field_name != field["name"]:
            result.field_name = field["name"]
        chunks_by_id = {chunk.chunk_id: chunk for chunk in selected}
        for value in result.values:
            for evidence in value.evidence:
                if evidence.chunk_id not in chunks_by_id:
                    raise ValueError(f"Unknown evidence chunk: {evidence.chunk_id}")
                normalized_quote = " ".join(evidence.quote.split()).casefold()
                normalized_chunk = " ".join(
                    chunks_by_id[evidence.chunk_id].text.split()
                ).casefold()
                if normalized_quote not in normalized_chunk:
                    raise ValueError(
                        f"Evidence quote is not present in {evidence.chunk_id}"
                    )
        return result

    def run(self, article: dict[str, Any]) -> ArticleExtraction:
        pages = [PageText(page=int(p["page"]), text=p["text"]) for p in article["pages"]]
        chunks = build_chunks(pages)
        fields = [self._extract_field(field, chunks) for field in self.schema["fields"]]
        return ArticleExtraction(
            schema_version=self.schema["schema_version"],
            study_id=article["study_id"],
            title=article["title"],
            model_id=self.model_id,
            fields=fields,
        )
