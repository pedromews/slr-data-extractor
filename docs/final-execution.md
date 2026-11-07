# Official extraction procedure

The official full-article entry point is `scripts/run_article.py`. The older `execution.cli` remains a retrieval-based pilot entry point and is used by the official runner only with `--prepare-only` to parse and snapshot the source. Do not use its direct generation mode for final experiments.

## Selected configuration

- Prompt 7.3, instruction template, retrieval terms included in the prompt.
- Schema 4.6 (specialist revisions must receive a new version before final evaluation).
- Qwen/Qwen3-14B-AWQ, revision 31c69efc29464b6bb0aee1398b5a7b50a99340c3.
- vLLM 0.11.0; server environment used during comparison: transformers 4.57.6, tokenizers 0.22.2. The live client/server package snapshots and launch command are archived in `config/environments/tupi1-2026-11-07/`.
- Thinking enabled, unconstrained generation, 4,096 output tokens including reasoning, 8,192 context tokens.
- One chunk per field per call, all chunks in document order, including references. No retrieval filtering in generation.
- No automatic retry, output repair, semantic deduplication, or LLM reviewer.

The model revision is a declared server launch parameter; `/models` alone cannot prove the loaded weights revision. Preserve the server launch log and dependency inventory.

## Execution

From the repository root, with the local Qwen server ready:

```bash
PYTHONPATH=src "$SCRATCH/slr-client-venv/bin/python" scripts/run_article.py \
  --input data/papers/P1-bias-free-and-auto-evolving-generative-ai-design-principles-architectures-and-reinforcement-integration.json \
  --run-dir runs/pilot-p1-official-thinking-001
```

PDF input is also accepted; add `--study-id P1`. The default schema and config are `config/gender_and_beyond_schema.json` and `config/models/qwen3-14b-awq-final.json`.

The runner first prepares every request and checks the whole matrix with the server tokenizer. Any context overflow stops generation. It does not silently truncate or change chunk grouping. `--prepare-only` stops after token approval.

## Short PCAD confirmation before freezing

Run the P1 command above with `--field bias_types --batch 2` and a new run directory, e.g. `runs/smoke-p1-official-thinking-bias2-001`. This tests the production path while generating one request. The result is explicitly partial and never creates an article-wide `result.json`.

Check `manifest.json`, `fields/bias_types/batch-02/field-01.raw.txt`, `.reasoning.txt`, `.final.txt`, `.usage.json`, `.validated.json`, and `fields/bias_types/consolidated-review.json`. Sampling need not reproduce the earlier wording exactly; the check concerns correct requests, reasoning separation, source validation, audit files and consolidation.

## Response handling

The original HTTP response is saved before interpretation. The shared decoder accepts server reasoning fields or the existing Qwen closing `</think>` boundary; it rejects missing/unfinished thinking and ambiguous boundaries. Only the final text is parsed as SelectedField. Markdown fences are not removed. A truncated/refused response is a failure, not absence. Evidence IDs resolve only against the supplied chunks; field name, source quote/page and section are validated.

## Consolidation

`run_batch_field.consolidate` removes only identical complete value/evidence objects. JSON key order is ignored; value case, wording, evidence order, quotes, pages, sections and chunk IDs remain significant. Same concept with different wording or evidence stays separate. It does not combine evidence across differently represented values. Batch provenance is saved alongside the consolidated field. Notes are retained with batch labels. Empty batches do not erase findings from other batches.

A field result is emitted only when every selected article batch succeeded and the run covers all batches. Partial/failed runs retain `consolidated-review.json` with errors and provenance. The article `result.json` is emitted only when all fields succeed and no field/batch filter was used. Absence means not found in the supplied article context, not proof of real-world absence.

The top-level runner deliberately requires a new directory and has no automatic resume. The existing field runner can resume only never-attempted calls under its identity checks; it never silently resends failed/interrupted calls.

## Audit findings and local verification

The previous direct pipeline requested response_format, while the batch scripts removed it and forced thinking off. The pipeline now has explicit generation switches; the final profile selects the tested behavior, and both batch preparation and execution use its thinking flag. The tested reasoning decoder is shared by the diagnostic and official extraction path.

Local replay of the saved P1 schema-4.6 bias_types batch 2 thinking-on response: newly constructed request exactly matches the diagnostic request; final result exactly matches the saved diagnostic result; full source validation succeeds; reasoning/final/usage artifacts are written. Missing or unfinished reasoning is rejected. Existing pilot and batch-execution checks passed (14 checks); no new experiment or interruption campaign was added.

## Implementation freeze

Tag: `implementation-freeze-v1.0`. This freezes the technical implementation and selected configuration, not specialist approval of the schema, human references or evaluation criteria. Any later approved change must receive a new version and new run directories. Do not tune using held-out papers.

The live confirmation `runs/smoke-p1-official-thinking-bias2-001` completed on tupi1 with code 6bd6f08. All 208 prepared requests passed token verification (minimum spare context: 522 tokens). Exactly one generation completed in 5.88 seconds. Raw response, reasoning, final JSON, resolved evidence and batch provenance were saved. No article-wide result was emitted for the partial run.

The new request was exactly equal to the previous schema-4.6 diagnostic request. The model nevertheless grouped gender, ethnicity, age and disability into one value. Thinking does not guarantee atomic concepts or identical results across executions/environments. The cause of this variation was not isolated; no retry was used to select a preferred response.

### Recreating the recorded environment

The snapshots are inventories of installed package versions, not wheel archives or hash-locked installers. They do not guarantee bitwise reproduction or compatibility with every node. Use Python 3.11.2 and retain server launch logs for each execution.

```bash
python3.11 -m venv "$SCRATCH/slr-client-venv"
"$SCRATCH/slr-client-venv/bin/python" -m pip install -r config/environments/tupi1-2026-11-07/client-requirements.txt
python3.11 -m venv "$SCRATCH/slr-vllm-venv"
"$SCRATCH/slr-vllm-venv/bin/python" -m pip install -r config/environments/tupi1-2026-11-07/server-requirements.txt
export HF_HOME="$SCRATCH/huggingface"
"$SCRATCH/slr-vllm-venv/bin/python" scripts/serve_pilot.py \
  --config config/models/qwen3-14b-awq-final.json \
  --log-dir runs/server-frozen-001
```

`server-command.txt` records the resolved API-server command used in the successful tupi1 check. `environment.json` records hardware, driver, Python and configuration/package-snapshot SHA-256 hashes. Model weights are pinned by Hugging Face revision in the model config. The server and client are separate environments; their OpenAI SDK versions differ intentionally in this captured inventory.
