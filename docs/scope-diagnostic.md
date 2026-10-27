# Frozen-batch category and scope diagnostic

Replay batch 2 of the prompt 6.5 instruction arm for `bias_types` and
`reported_impacts`. Run a fresh baseline and a clarified arm (four calls total).
The only request change is a generic system-message suffix about enumerated
categories and the definition's evidence requirements. It contains no P1 answers.
This tests the combined supplement, not the separate contribution of each rule.

The script reads saved requests directly: field definitions, retrieval terms,
passages, output schema and generation parameters are preserved. It checks server
identity and token budget before each call; saves the original and modified
request, their hashes, the script, raw response, selected evidence catalog,
resolved result, timing and errors. No retries or truncation are used. Passing
validation does not establish semantic correctness. The production prompt remains
unchanged. This is a batch diagnostic, not an article-wide extraction.

On the allocated PCAD node, after `git pull --ff-only` and checking the server:

```sh
cd "$HOME/slr-data-extractor"
for field in bias_types reported_impacts; do
  for variant in baseline clarified; do
    PYTHONPATH=src "$SCRATCH/slr-client-venv/bin/python" scripts/run_scope_diagnostic.py \
      --prepared-run runs/pilot-p1-prompt65-instruction-prepared-001 \
      --field "$field" --batch 2 --variant "$variant" \
      --run-dir "runs/diagnostic-p1-prompt65-scope-$field-$variant-001" || break 2
  done
done
```

Each target must be new. `--prepare-only` saves the request without contacting the
server; use a different target for execution. Compare category granularity,
out-of-scope entries, supported consequences and evidence support. Review the raw
response even when validation fails. Interpret results as exploratory on P1;
confirm any selected policy on other papers before freezing the experiment.


## Individual items experiment

Keep prompt 6.5 in instruction style as the baseline. The `individual-items`
variant adds only the item-granularity instruction, explicitly allowing several
values to share an evidence ID. It does not include the earlier `clarified`
supplement or any P1 answer examples. No splitting or rewriting of model values
is performed after generation. Run two fresh calls on batch 2:

```sh
for variant in baseline individual-items; do
  PYTHONPATH=src "$SCRATCH/slr-client-venv/bin/python" scripts/run_scope_diagnostic.py \
    --prepared-run runs/pilot-p1-prompt65-instruction-prepared-001 \
    --field bias_types --batch 2 --variant "$variant" \
    --run-dir "runs/diagnostic-p1-bias-items-$variant-001" || break
done
```

Check whether the four demographic categories become distinct values supported
by the same supplied segment, without adding causes or consequences as bias types.
Validation success alone does not establish this. If the targeted test succeeds,
check compound concepts in other fields and papers before adopting the instruction.


## Short system prompt comparison

The `short` variant replaces the system message instead of appending instructions.
The user message (definition, terms, output schema and passages) and all request
parameters remain identical. The manifest records the full replacement text;
production prompt 6.5 is unchanged. This tests a bundle of wording changes, not
length alone. Compare two fresh calls on `bias_types`, batch 2:

```sh
for variant in baseline short; do
  PYTHONPATH=src "$SCRATCH/slr-client-venv/bin/python" scripts/run_scope_diagnostic.py \
    --prepared-run runs/pilot-p1-prompt65-instruction-prepared-001 \
    --field bias_types --batch 2 --variant "$variant" \
    --run-dir "runs/diagnostic-p1-bias-short-$variant-001" || break
done
```

Review separated categories, extraneous causes/consequences, missing categories,
and evidence IDs. Do not adopt the variant solely because it passes validation.


## Retrieval terms ablation on Llama

Compare fresh baseline and `no-terms` calls for `bias_types` on batches 2 and 5.
Use the Llama preparation directly. Only the retrieval-terms line in the user
message is removed; the system prompt, definition, output schema, passages and
sampling parameters remain unchanged. No retrieval filtering occurs in this
full-article experiment. The source schema is preserved for provenance; the
manifest records removal and the effective configuration sets term inclusion false.

```sh
for batch in 2 5; do
  for variant in baseline no-terms; do
    PYTHONPATH=src "$SCRATCH/slr-client-venv/bin/python" scripts/run_scope_diagnostic.py \
      --prepared-run runs/pilot-p1-prompt65-llama-prepared-001 \
      --field bias_types --batch "$batch" --variant "$variant" \
      --run-dir "runs/diagnostic-p1-llama-terms-batch$batch-$variant-001" || break 2
  done
done
```

Check preservation of supported demographic categories in batch 2 and unsupported
categories in batch 5. An existing evidence ID does not prove semantic support.
This four-call diagnostic tests term inclusion, not general model superiority.
