# MVP contract

The review schema is `config/gender_and_beyond_schema.json`. Researchers define
fields and their semantics; `schema.py` validates a small Pydantic contract.
There is no separately maintained meta-schema file or dynamic model compilation.

## Review definition

- `schema_id`, `schema_version`, `title`: identity and version.
- `fields`: a nonempty list with unique field names.

Each field contains:

- `name`: a stable identifier.
- `definition`: an operational definition.
- `unit_of_extraction`: what one item in the value list represents.
- `rules`: inclusion, exclusion, normalization instructions and examples.
- `retrieval_terms`: terms used by lexical retrieval.
- `qualifiers`: dimensions with a definition and a map of allowed options.

Every declared dimension is required for each extracted value. Declaring no
dimensions is allowed. The contract contains no Gender and Beyond-specific
concepts. Other reviews extracting textual values can be configured without
editing Python.

## Fixed output

Each field returns `field_name`, `status`, `values` and optional `notes`.

Each value contains textual `raw_value`, textual or null `normalized_value`,
`qualifiers` and one or more evidence entries. Each evidence entry records quote,
page_start, page_end, chunk_id and optional section. There are no value IDs or
relations.

`extracted` requires at least one value. `not_found_in_context` requires an empty
list but does not prove absence from the complete article. Uncertainty and
ambiguity belong in notes; the prompt instructs the model not to force an
interpretation. This requires human inspection and does not provide a structured
ambiguity category. Negative findings can be extracted textual values with evidence.

## Validation

1. Pydantic validates a fixed structure without coercing numbers into text.
2. Direct validation checks the requested field, qualifier dimensions and options.
3. Evidence is checked against selected chunks, pages and sections.

The JSON Schema sent to the server constrains the structure. Domain-specific
qualifier options are checked after generation. There are no silent corrections
or retries: invalid responses are recorded and the run fails. This behavior must
remain constant across models. Quote matching does not establish that the passage
semantically supports the claim; interpretive rules require human review.

## Parameters and traceability

`pilot.json` centralizes execution parameters. `models.json` is only a candidate
list. Each run saves the effective schema and configuration, the PDF hash in the
input, prompts, chunks and retrieval selection, declared model revision, raw
responses, errors, timings, environment and a source snapshot. This also captures
uncommitted code changes. Context checks remain mandatory before generation.

Current versions: schema/output 2.0-mvp, prompt 3.0-mvp. Earlier run directories
are neither overwritten nor reinterpreted. The loader rejects properties from
older contracts instead of ignoring them. Results are not migrated automatically.

## Outside the MVP

Relations and referential integrity; numeric, boolean and categorical types;
closed vocabularies; configurable cardinality; policy-based normalization;
additional scientific statuses; final evaluation and full-corpus execution.
These capabilities should return only when motivated by the pilot or protocol.
