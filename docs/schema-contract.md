# MVP contract

The review schema is `config/gender_and_beyond_schema.json`. Researchers define
fields and their semantics; `definitions/schema_definition.py` validates a small Pydantic contract.
There is no separately maintained meta-schema file or dynamic model compilation.

## Review definition

- `schema_id`, `schema_version`, `title`: identity and version.
- `fields`: a nonempty list with unique field names.

Each field contains:

- `name`: a stable identifier.
- `definition`: an operational definition.
- `retrieval_terms`: terms used by lexical retrieval.

The contract contains no topic-specific concepts. Researchers supply the three
field properties above. The generic prompt handles atomic extraction, literal
evidence and preservation of meaning. Proposed, implemented and empirically
evaluated claims must remain distinguishable in the textual values.
The removed properties unit_of_extraction, rules and qualifiers are rejected rather than ignored.

## Fixed output

Each field returns `field_name`, `status`, `values` and optional `notes`.

Each item contains a nonempty textual `value` and one or more supporting evidence entries. Each evidence entry records quote,
page_start, page_end, chunk_id and optional section. There are no value IDs or
relations.

`extracted` requires at least one value. `not_found_in_context` requires an empty
list but does not prove absence from the complete article. Uncertainty and
ambiguity belong in notes; the prompt instructs the model not to force an
interpretation. This requires human inspection and does not provide a structured
ambiguity category. Negative findings can be extracted textual values with evidence.

## Validation

1. Pydantic validates a fixed structure without coercing numbers into text.
2. Direct validation checks the requested field.
3. Evidence is checked against selected chunks, pages and sections.

The JSON Schema sent to the server constrains the structure. There are no silent corrections
or retries: invalid responses are recorded and the run fails. This behavior must
remain constant across models. Quote matching does not establish that the passage
semantically supports the claim; interpretive rules require human review.

## Parameters and traceability

`config/models/qwen.json` and `config/models/ollama.json` contain execution parameters.
`config/models/models.json` is only a candidate
list. Each run saves the effective schema and configuration, the PDF hash in the
input, prompts, chunks and retrieval selection, declared model revision, raw
responses, errors, timings, environment and a source snapshot. This also captures
uncommitted code changes. Context checks remain mandatory before generation.

Current versions: schema/output 4.0-mvp, prompt 5.2-mvp. Earlier run directories
are neither overwritten nor reinterpreted. The loader rejects properties from
older contracts instead of ignoring them. Results are not migrated automatically.

## Outside the MVP

Relations and referential integrity; numeric, boolean and categorical types;
closed vocabularies; configurable cardinality; policy-based normalization;
additional scientific statuses; final evaluation and full-corpus execution.
These capabilities should return only when motivated by the pilot or protocol.

The local Ollama pilot attempts every field once and reports completed_with_errors
if any validation fails; the vLLM CLI stops on the first error. Neither path repairs
responses. Earlier human-reference drafts are retained for manual review and are
not automatically migrated to the new output contract.

Evidence quotes have an experimental maximum of 400 characters, exported as
maxLength and checked by Pydantic. No automatic cutting or repair is applied.
The generic prompt requests short contiguous quotes and distinct items, preserving
compound concepts and relationships. Values must be supported by evidence; only
evidence quotes are subject to literal matching. Value representation may be
revisited after the pilot. No normalization step is performed.

The human reference is maintained separately and does not need pipeline chunk IDs,
execution metadata or field statuses. It is not loaded as a pipeline response.

Section metadata is attached to each page fragment, not pooled across a chunk's
pages. A label is supplied only when the fragment has a unique match on the
normalized page and lies entirely inside one parser section span. Missing,
ambiguous or cross-section fragments receive null. Fragment text is unchanged.
These labels remain parser heuristics, not verified PDF headings.

## Section-aware chunking

Parser implementation 2 recognizes numbered headings and alphabetic subsections,
retaining the parent heading in subsection labels. Wrapped uppercase headings are
joined for labels only; page text and offsets are unchanged. Heading detection
remains heuristic; unusual layouts and wrapped mixed-case subsection titles may
need review. Table captions are not treated as section headings.

Chunking version `2-section-boundaries` splits at changes in annotated section
labels and applies size limits and overlap within each section. A section can
continue across pages. Missing annotations retain a null label; incomplete or
overlapping supplied spans fail explicitly. Existing page JSON is not reparsed
or upgraded automatically: use PDF input to obtain the new annotations.

This changes chunk IDs, selected context and potentially extraction results.
Create new runs; do not compare them as a model-only change against older runs.
The CLI manifest records the chunking version alongside the source hash.
