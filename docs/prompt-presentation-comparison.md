# Prompt presentation comparison

Compare `field_prompt_style=json` (default) with `instruction`. Both use prompt 6.5 in segment-ID mode; the instruction variant has an explicit version suffix. Only the user-message field/context presentation changes. System instructions, concise-value policy, definitions, retrieval-term inclusion, evidence catalog, output schema and generation parameters remain fixed.

Prepare both arms anew using the current schema. Historical outputs are not the baseline for this experiment. On PCAD, after transferring the updated code:

```sh
cd "$HOME/slr-data-extractor"
for style in json instruction; do
  PYTHONPATH=src "$SCRATCH/slr-client-venv/bin/python" scripts/prepare_full_article.py \
    --source-run runs/pilot-p1-single-chunk-prepared-001 \
    --batch-plan runs/pilot-p1-single-chunk-prepared-001/batches.json \
    --schema config/gender_and_beyond_schema.json \
    --field-prompt-style "$style" \
    --run-dir "runs/pilot-p1-prompt65-$style-prepared-001" || break
done
```

Verify every request against the running model tokenizer before generation. The source configuration uses Qwen/Qwen3-14B-AWQ, the pinned revision, retrieval terms enabled, unconstrained JSON and thinking disabled. Confirm the server matches it.

```sh
for style in json instruction; do
  PYTHONPATH=src "$SCRATCH/slr-client-venv/bin/python" scripts/check_batch_tokens.py \
    --prepared-run "runs/pilot-p1-prompt65-$style-prepared-001" \
    --output-dir "runs/pilot-p1-prompt65-$style-tokens-001" \
    --expected-plan-sha256 7a20dfcebfe76ab31f93776705c6ca23d65e1c276fc8fcd23b728c68a2c286c8 || break
done
```

Only after both token checks pass, run the initial two fields (104 generation calls total):

```sh
for field in bias_types reported_impacts; do
  for style in json instruction; do
    PYTHONPATH=src "$SCRATCH/slr-client-venv/bin/python" scripts/run_batch_field.py \
      --prepared-run "runs/pilot-p1-prompt65-$style-prepared-001" \
      --token-check "runs/pilot-p1-prompt65-$style-tokens-001" \
      --run-dir "runs/pilot-p1-prompt65-$style-$field-001" \
      --field "$field" || break 2
  done
done
```

Review paired raw and consolidated outputs: validation failures, value length and explanatory-sentence frequency, lost distinctions, inclusion/exclusion errors, and evidence support. Shorter values are not automatically more accurate. Use the same reference snapshot for both arms and regard comparisons as exploratory until expert approval. No retries or final corpus evaluation are introduced.
