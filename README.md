# Schema-based SLR data extraction

Initial implementation skeleton for the *Gender and Beyond* case study.

The pipeline is intentionally independent from ProfOlaf. It uses an
OpenAI-compatible endpoint, so the same code can call locally served models
through vLLM. The model is a configuration value; PDF processing, chunking,
retrieval, prompts and validation remain constant between experimental runs.

## Current scope

1. Read page-aware text exported from a PDF.
2. Build overlapping chunks without losing page provenance.
3. Rank chunks independently for each extraction field.
4. Ask an LLM for a schema-constrained extraction.
5. Validate values and supporting evidence with Pydantic.
6. Save one auditable JSON result per article and model.

PDF parsing and the final evaluation module are deliberately left behind
interfaces. The meeting must first fix the PDF parser, gold-standard
normalization rules and metrics.

## Files

- `config/extraction_schema.json`: preliminary case-study schema.
- `config/models.json`: proposed controlled model comparison.
- `src/slr_extraction/models.py`: structured output models.
- `src/slr_extraction/chunking.py`: deterministic page-aware chunking.
- `src/slr_extraction/retrieval.py`: transparent lexical baseline retrieval.
- `src/slr_extraction/pipeline.py`: extraction orchestration.
- `tests/test_core.py`: unit tests that do not require an LLM.

## Input format

The pipeline currently accepts a JSON file containing page text:

```json
{
  "study_id": "A1",
  "title": "Paper title",
  "pages": [
    {"page": 1, "text": "First page..."},
    {"page": 2, "text": "Second page..."}
  ]
}
```

Keeping PDF parsing separate makes it possible to evaluate extraction without
silently changing the parser between models.

## Run

```bash
export OPENAI_BASE_URL="http://127.0.0.1:8000/v1"
export OPENAI_API_KEY="local"

PYTHONPATH=src python -m slr_extraction.cli \
  --input article_pages.json \
  --schema config/extraction_schema.json \
  --model Qwen/Qwen2.5-7B-Instruct \
  --output result.json
```

## Test

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

