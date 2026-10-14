# Full-article batch pilot

Prepare with `scripts/prepare_full_article.py`, then verify every request with
`scripts/check_batch_tokens.py`. Freeze the shared batch plan before comparing
models. Character estimates alone are not sufficient for execution.

`scripts/run_batch_field.py` executes one named field across all approved batches.
It verifies request hashes from the token check, reconstructs each request with
the current pipeline, and checks the served model and vLLM version. Model revision
remains operator-declared and should be checked against the server launch log.
Generation is unconstrained, with Qwen3 thinking disabled and no automatic retries.

Each batch has its own request, raw response, validation output and status.
`--resume` reuses completed outputs after validation and executes only batches
whose directories do not exist. Failed or interrupted attempts are preserved and
not resent. For an intentional retry, use a new run directory. Resume requires
identical input files, runner and pipeline code. A process lock prevents concurrent
execution in the same run directory on the PCAD/macOS platforms.

`consolidated-review.json` always marks completeness and lists failed batches.
`field-result.json` is written only when every batch has passed. Consolidation
removes only identical value/evidence objects and records their batch provenance.
Different wording, different evidence or different evidence ordering are retained.
Notes remain attributed to their batches. This is not semantic deduplication or
final evaluation. A not-found result from one batch never erases other findings.

The first planned real execution is bias_types only: nine calls for P1. Review it
before executing the other six fields. Bibliographic chunks remain included;
semantic review must distinguish cited titles from claims of the primary study.

Use `prepare_full_article.py --schema config/gender_and_beyond_schema.json`
to explicitly use the current review schema. Without this option, preparation
retains the schema saved in `--source-run`. The selected schema is archived
and its source path and SHA-256 are recorded in the preparation manifest.

For the terms ablation control, prepare from the no-terms run with the same
`--batch-plan` and `--include-retrieval-terms`. This saves
`include_retrieval_terms_in_prompt: true` in the run configuration and labels
the prompt version with `-with-terms-control`. Only the field definition payload
gains retrieval terms; the system prompt, passages and generation settings stay
unchanged. Token-check the new requests before running the two selected fields.

Prompt 6.3 adds a generic claim-status instruction: evidence must support the
claim at its stated certainty, and empirical confirmation is not required when
the field permits proposed, hypothetical or background claims. For the P1
comparison, retain retrieval terms and reuse the terms-control schema and batch
plan. Run only `bias_types` and `reported_impacts` (18 generation calls).

For model comparisons, `--config` selects an explicit model configuration.
Use the same frozen batch plan and schema; tokenize again with the new server.
The Llama 3.1 8B AWQ pilot configuration preserves the Qwen3 pilot settings
and changes only model ID and revision. The Qwen-specific `enable_thinking`
template argument is retained in requests for comparability; Llama has no
corresponding thinking toggle. Verify the served template and token budget.
