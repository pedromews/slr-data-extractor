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
