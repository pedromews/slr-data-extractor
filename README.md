# Schema-based SLR data extraction

Modular pilot for the *Gender and Beyond* case study. Python 3.11.
Parser → page JSON → chunking → lexical retrieval → local LLM → validation.
Final evaluation and corpus-wide execution are intentionally not implemented.

## Setup and tests

```bash
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock.txt
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v
```

`requirements.txt` declares direct dependencies; `requirements.lock.txt` records
exact versions tested in the client environment. Install vLLM in a separate
Python 3.11 environment on PCAD; do not use the client lock to constrain vLLM.

## Convert one PDF

```bash
PYTHONPATH=src .venv/bin/python -m slr_extraction.pdf_parser \
  --input /absolute/path/paper.pdf \
  --study-id pilot-bias-free \
  --title "Bias-Free and Auto-Evolving Generative AI: Design Principles, Architectures, and Reinforcement Integration" \
  --output data/pilot-bias-free.pages.json
```

Output includes all physical pages (one-based), exact extracted text, statuses,
heuristic section spans, source SHA-256, parser version, warnings and timing.
Exit codes: 0 success; 1 failure; 2 JSON saved but review required. Existing
outputs are never overwritten. No OCR; empty or failed pages block extraction.

The page JSON remains compatible with `study_id`, `title`, and `pages` containing
`page` and `text`. Additional metadata preserves provenance. No paper content is
committed: `data/` and `runs/` are ignored by Git.

## Prepare without a model

```bash
PYTHONPATH=src .venv/bin/python -m slr_extraction.cli \
  --input data/pilot-bias-free.pages.json \
  --config config/pilot.json \
  --run-dir runs/pilot-bias-free-prepared-new \
  --prepare-only
```

Saves page input, schema, configuration, Python package versions, source snapshot
and hash, every chunk, selected/nonselected IDs and all eight exact requests.
Use a new run directory each time. `prepared` does not mean inference or token
preflight passed. No server is contacted in preparation mode.

The extraction CLI now uses `--config` and `--run-dir` instead of the old
`--model` and `--output` flags so every run has explicit settings and records.

## PCAD pilot: RTX 4090 24 GB

`config/pilot.json` selects Qwen2.5-7B-Instruct and an exact model revision.
Other models remain configurable; comparison is not run automatically.

In a separate server environment with Python 3.11 and `vllm==0.11.0`:

```bash
python scripts/serve_pilot.py \
  --config config/pilot.json --log-dir runs/server-pilot-001
```

This launches BF16, context 8192, one sequence, 90% GPU memory utilization,
`--generation-config vllm`, fixed model/tokenizer revisions and seed. Launch
arguments, GPU information, package versions and server stdout/stderr are saved.
Initial startup downloads weights if they are absent. Hardware/CUDA compatibility
and successful GPU startup must still be verified on PCAD.

In another terminal, use the client environment on the same host:

```bash
PYTHONPATH=src .venv/bin/python -m slr_extraction.cli \
  --input data/pilot-bias-free.pages.json \
  --config config/pilot.json \
  --run-dir runs/pilot-bias-free-001
```

Endpoint: `http://127.0.0.1:8000/v1`. No commercial API is used. The OpenAI SDK
is only a client for the local compatible server. The runner verifies vLLM
version and model ID, tokenizes all prompts, and aborts if any prompt plus output
budget exceeds context. It never truncates or changes retrieval per model.

Each field saves the raw HTTP response before parsing, validation output, elapsed
time and errors. A failed run retains preceding fields and has status `failed`;
it does not emit a successful article result. Successful runs save `result.json`.
The declared model revision must be checked against the retained server launch
log; `/models` alone cannot attest it.

## Review before expansion

Inspect PDF reading order, page/section evidence, qualifiers and retrieval
coverage for this one article. `not_found_in_context` means no support in selected
passages, not proven absence from the whole paper. Sections are heuristic;
null is valid. Exact text matching is not semantic entailment verification.

See [schema contract](docs/schema-contract.md) for configuration, migration and
validation limits. Map `pilot-bias-free` to the spreadsheet's A1–A10 identifier and
confirm the source version before any final evaluation. Do not run all articles
or compare model scores until this pilot has been manually validated.


## MVP schema

The researcher-defined schema is `config/gender_and_beyond_schema.json`.
`schema.py` provides a small Pydantic contract, without dynamic models or a
separately maintained meta-schema file. All fields return lists of textual values,
optional normalized text, configured qualifier dimensions and source evidence.

```bash
PYTHONPATH=src .venv/bin/python -m slr_extraction.schema config/gender_and_beyond_schema.json
```

The response structure is fixed across fields. Field names, qualifier dimensions
and allowed options are checked after generation; invalid answers fail and remain
in the raw audit records. Status is either `extracted` or `not_found_in_context`.
Unresolved ambiguities go in `notes`; this does not replace manual review.

Relations, value IDs, numeric/categorical types and advanced normalization policies
are deferred. No evaluation metrics or corpus-wide execution are implemented.
See [the MVP contract](docs/schema-contract.md).

`config/pilot.json` is the source of execution parameters, including chunking,
retrieval and generation. `top_k` means retrieved chunks; `sampling_top_k` is the
vLLM sampling parameter. `config/models.json` only lists candidate models; it does
not override the execution configuration. Low-level chunking/retrieval functions
require explicit parameters rather than conflicting defaults.

The simplified schema/output version is `2.0-mvp`, prompt version `3.0-mvp`.
Previous run folders are preserved, but their formats/prompts are not equivalent.
Prepare a new run before executing this version:

```bash
PYTHONPATH=src .venv/bin/python -m slr_extraction.cli \
  --input data/pilot-bias-free.pages.json \
  --schema config/gender_and_beyond_schema.json \
  --config config/pilot.json \
  --run-dir runs/pilot-mvp-new --prepare-only
```
