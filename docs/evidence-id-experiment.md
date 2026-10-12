# Evidence selection by ID (experimental)

Set `"evidence_mode": "segment_ids"` in a copy of the model configuration.
The default remains `verbatim`. No research-schema or human-reference changes
are required. Prompt version: `6.1-evidence-ids-relevance`.

The selected chunks are unchanged. Each page fragment is partitioned at
sentence-like punctuation and whitespace, with a maximum of 400 characters per
segment. Long sentences split at spaces where possible. Long tokens may split.
Every non-whitespace character is retained, with exact offsets into chunk text.
Segments never cross a page or chunk boundary. Adjacent IDs can provide context.
This heuristic may split abbreviations or sentences; it is not a semantic parser.

The model returns `value` and `evidence_ids` for each item. Only IDs belonging to
that field's selected chunks are accepted. The pipeline resolves them to the
existing quote/page/section/chunk output and runs the existing validation.
The model's raw response is retained. `evidence-catalog.json` records the complete
catalog and offsets; `retrieval.json` identifies chunks supplied to each field.
CLI manifests record the prompt, evidence mode and segmentation version.

Prepare a new run from the PDF with the copied configuration. Never overwrite
old runs. The normal CLI still uses constrained generation; the Qwen3 diagnostic
must keep response_format removed and enable_thinking=false, including token
counting. Existing diagnostic scripts must check pipeline.prompt_version (or
6.1-evidence-ids-relevance), rather than requiring the old 5.3 prompt.

This changes the model-facing output contract and context presentation. It is a
separate experiment, not a prompt-only comparison. Final output format remains
4.0-mvp. Exact retrieval does not establish semantic support or completeness.
Recheck token budgets before inference; do not truncate context silently.

## Relevance-only prompt experiment

Version 6.1 adds a generic field-relevance inclusion criterion. It requires
direct answers to the field definition, evidence for the complete claim, and
allows empty results without a value quota. It does not add field-specific
examples or change segmentation, retrieval, generation parameters or output.
Keep the 6.0 runs unchanged. Prepare a new run and compare batch IDs before
execution; rerun token checks because the system prompt is longer.
