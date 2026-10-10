# A1 schema alignment and selection experiment

This is exploratory pilot development, not final evaluation. The original
`data/reference/A1.reference-draft.json` is unchanged. The separate
`data/reference/A1.reference-aligned-draft.json` is an AI-assisted candidate
requiring researcher review, not an approved human gold standard.

## Semantic alignment

Schema 3.2 includes proposed evaluation methods, potential impacts and explicitly
discussed bias types, rather than implicitly requiring empirical observations.
Generation contexts are eligible as intended AI software pipeline contexts.
Manifestations name forms of bias rather than locations alone. The generic prompt
and output contract are unchanged; semantic status remains in textual values.

The candidate reference removes legacy qualifiers and preserves their meaning in
normalized values. It splits grouped mitigation strategies, replaces location-only
manifestations with named forms from their quotations and corrects the RLHF section
to IV.C. Original evidence wording is retained, including human dehyphenation.
Researchers must review those interpretations, whether the intended generation
contexts belong in the review, and completeness. Bias auditors and fairness checkers
may overlap conceptually; review their granularity before finalizing the reference.

## Controlled comparison

Compare `config/gender_and_beyond_schema.json` with
`config/experiments/gender_and_beyond_selection_terms.json`. They have identical
versions, definitions and extraction units; only retrieval terms differ. Record
schema hashes to distinguish them. Keep the algorithm, top_k=6, chunking, article,
model revision, generation parameters and prompt template fixed. Selected context
will differ by design. Terms were developed after inspecting A1: this is tuning,
not independent evidence of generalization.

Run both arms anew. Comparing the new variant directly against the old PCAD run
would confound schema changes with selection changes. For the unconstrained PCAD
diagnostic, apply the SAME removal of response_format and SAME JSON-only system
suffix to both arms. The normal CLI still uses constrained generation; do not
silently mix these protocols. No remote inference has been run for this experiment.

## Offline selection check

Using the saved 17 chunks from pilot-a1-ollama-004 and top_k=6:

| Field | Variant context change relevant to the reference |
| --- | --- |
| se_tasks_or_contexts | Includes chunk-0011 (generation contexts in Table I). |
| bias_sources | Includes chunk-0003 (configuration, orchestration, reuse). |
| evaluation_methods | Includes chunk-0011 (KPIs) and chunk-0008 (proposal context). |
| mitigation_strategies | Includes chunk-0014 (datasets and taxonomies), but loses chunk-0007 (bias auditors). |

The last tradeoff matters: this variant does not recover all reference evidence.
Do not claim better extraction accuracy from context coverage alone. Do not add
reference quotations, expected answers or manually chosen chunk IDs to the prompt.

The PCAD and local original chunks, retrieval and schema hashes were confirmed
identical. That confirmation applies to the original runs, not the revised schema.

Validation: both schemas pass the Pydantic contract; non-retrieval field properties
are equal across the two arms; all 37 existing unit tests pass. No model calls were
made. Preserve separate run directories and audit raw outputs for the next pair.
