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
coverage for this one article. `not_reported` means no support in selected
passages, not proven absence from the whole paper. Sections are heuristic;
null is valid. Exact text matching is not semantic entailment verification.

See [technical review](docs/code_review.md) for fixes, provisional decisions and
limitations. Map `pilot-bias-free` to the spreadsheet's A1–A10 identifier and
confirm the source version before any final evaluation. Do not run all articles
or compare model scores until this pilot has been manually validated.
