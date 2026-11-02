# P1 batch-size comparison

Development experiment: Qwen3-14B-AWQ, prompt 7.1, evidence IDs, and the schema
and configuration frozen in `runs/pilot-p1-prompt71-qwen-prepared-001`.
Compare 1, 2 and 3 consecutive chunks per request for `bias_types` and
`reported_impacts`. Keep all chunks, including References and the last short
batch. Do not filter passages or change consolidation between arms.

For P1: 26, 13 and 9 batches respectively; two fields require 52, 26 and 18
calls (96 total). Run all arms anew. The 2,048-token output allowance remains
fixed per call, so total available output differs. Record truncation and timing;
this experiment changes grouping, not context amount in isolation.

Preparation:

```sh
for size in 1 2 3; do
  PYTHONPATH=src "$SCRATCH/slr-client-venv/bin/python" scripts/prepare_full_article.py \
    --source-run runs/pilot-p1-prompt71-qwen-prepared-001 \
    --chunks-per-batch "$size" --field-prompt-style instruction \
    --run-dir "runs/pilot-p1-group$size-prepared-001" || break
done
```

Before inference, compare config, schema, chunks and evidence catalog across arms;
all must be identical. Check every request with `scripts/check_batch_tokens.py`,
using each arm's own `batch_plan_sha256` from its manifest. If a plan exceeds the
context, stop: do not truncate or silently change generation parameters.

After all token checks pass, use `scripts/run_batch_field.py` for each of the two
fields in each arm. Compare article-level consolidated outputs against the same
human reference snapshot. Counts alone are not accuracy; inspect omissions,
out-of-scope entries, evidence support, grouping, duplicates and failures.
No interruption/resume experiment is planned. No new unit-test campaign is needed.
