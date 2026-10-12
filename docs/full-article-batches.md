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
