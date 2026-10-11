# Optional BM25 selection

The default remains `selection_method: lexical`. Set `selection_method: bm25`
in a copied configuration for the experimental alternative. Both use top_k and
stable document-order tie breaking, including zero-score candidates.

BM25 uses all article chunks as the corpus, positive IDF
`log(1 + (N - df + 0.5) / (df + 0.5))`, k1=1.5 and b=0.75. Query tokens
are deduplicated. Source text is never changed. The English tokenizer splits
hyphens and underscores and heuristically normalizes common plural suffixes;
it is not a lemmatizer and does not repair PDF broken words. Overlapping chunks
influence document frequency. No reference answers enter scoring.

This variant changes both scoring and lexical normalization. Improvements cannot
be attributed to BM25 alone. It introduces no dependencies. CLI manifests record
the selection method and version.

Run an offline comparison from the repository root:

```bash
PYTHONPATH=src .venv/bin/python scripts/compare_selection.py \
  --source-run runs/diagnostic-p1-evidence-ids-001 \
  --output /tmp/p1-selection-comparison.json
```

The output includes full BM25 rankings and request character counts. Character
counts are not token counts. Verify all requests with the served model's
`/tokenize` endpoint before inference; the diagnostic runner does this without
silently truncating contexts.

P1 inspection found mixed results: the Table I chunk is now selected for
se_tasks_or_contexts and evaluation_methods. The explicit bias source passages
remain excluded. The Introduction passages supporting reported_impacts are lost.
A References chunk is selected for bias_types. These findings do not justify
replacing the baseline. Keep this experiment optional; do not tune it against
P1 reference answers or change the human reference to fit model outputs.
