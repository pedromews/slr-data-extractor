# Local A1 pilot with Ollama

This is an exploratory quantized Mac pilot, separate from the controlled PCAD
BF16/vLLM experiment. The parser input, schema, chunk creation, lexical selection,
message content and evidence validation are reused unchanged. No human reference
is supplied to the model.

Start the local server in another terminal:

```bash
ollama serve
```

Download the model and run from the repository root:

```bash
ollama pull qwen2.5:7b-instruct-q4_K_M
PYTHONPATH=src .venv/bin/python -m slr_data_extraction.execution.ollama_cli \
  --input data/pilot-bias-free.pages.json \
  --config config/pilot-ollama.json \
  --run-dir runs/pilot-a1-ollama-001
```

Use a new run directory for every attempt. Python 3.11 in the project environment
runs the pipeline. Ollama is an independent server installed through Homebrew.

## Deliberate local differences

- Ollama native /api/generate on loopback port 11434, with Metal and Q4_K_M
  weights, instead of vLLM/CUDA and BF16.
- Explicit Qwen2.5 ChatML rendering in raw mode. The original system and user
  message contents and structured output schema are preserved.
- Context capacity 32768 instead of 8192. Before generation, the complete rendered
  prompt UTF-8 byte length plus 32 safety tokens and the output allowance must
  fit. This is a conservative bound for Qwen2.5 byte-level BPE, not an exact
  tokenizer count. It prevents shortening context to fit. Actual prompt token
  counts are preserved in raw responses.
- A 30-minute HTTP timeout accommodates local prompt evaluation.
- Each field is attempted once. Validation failures are retained and subsequent
  fields are still attempted, so a single article can expose multiple issues.
  The run returns nonzero and does not produce result.json if any field fails.

## Audit artifacts

The run saves source code, configuration, input, schema, chunks, selections,
original prepared requests and actual Ollama requests. It also saves server
version, model digest, model metadata/template, raw responses (including timings
and token counts), per-field status, validated outputs and server process details.
The manifest distinguishes completed, completed_with_errors and failed runs.
Source evidence validation does not prove semantic correctness.

The reference draft is neither read nor changed. Runs and article data remain
gitignored. The original PCAD configuration and CLI are unchanged.
