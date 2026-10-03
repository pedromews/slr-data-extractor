# Meeting brief: schema and model selection

## Fixed thesis scope

The thesis will implement a modular, schema-based pipeline for data extraction
from the primary studies included in a systematic literature review. The
experiment will compare different open-weight LLMs while keeping the corpus,
PDF parser, chunking, retrieval, prompts, schema, validation and metrics fixed.
The human extraction from *Gender and Beyond* will be the reference.

Proposed main research question:

> How accurately can different Large Language Models reproduce human-performed
> data extraction in a Systematic Literature Review when used within the same
> schema-based pipeline?

## Corpus finding

The review paper reports 10 final primary studies: eight found through database
screening and two added by snowballing. The `INCLUÍDOS` worksheet also contains
10 records (A1–A10), with every substantive extraction column populated. This
worksheet should be the authoritative human reference. The `Dados
bibliométricos` worksheet is a reduced view and should not be treated as a
second gold standard.

One issue should be clarified: the `Origem` column currently labels six studies
as `Bases` and four as `Snowballing`, while the paper states eight plus two.
This does not prevent extraction experiments, but the provenance metadata
should be corrected or explicitly excluded from evaluation.

## Proposed minimum schema

The first version should extract the eight substantive fields already present
in the human spreadsheet:

| Field | Source | Cardinality | Important distinction |
| --- | --- | --- | --- |
| `bias_types` | RQ1 | Multiple | Observed vs merely discussed |
| `se_tasks_or_contexts` | RQ1.1 | Multiple | Technical SDLC task vs socio-technical context |
| `llm_systems` | RQ1.2 | Multiple | Subject under test vs auxiliary/judge model |
| `bias_sources` | RQ1.3 | Multiple | Demonstrated cause vs author hypothesis/background claim |
| `evaluation_methods` | RQ1.4 | Multiple | Method, dataset and measurement details |
| `reported_impacts` | RQ1.5 | Multiple | Observed impact vs inferred/general impact |
| `manifestations` | Additional sheet field | Multiple | Concrete behavior/output rather than broad bias label |
| `mitigation_strategies` | Additional sheet field | Multiple | Proposed vs implemented vs empirically tested |

Bibliographic metadata should be stored with every study, but authors, year and
title do not need to be primary evaluation targets because they are not the
scientifically difficult part of the task.

### Required representation

Each extracted value should contain:

```json
{
  "raw_value": "gender bias",
  "normalized_value": "gender_bias",
  "qualifier": "empirically_observed",
  "evidence": [
    {
      "quote": "verbatim passage from the paper",
      "page_start": 7,
      "page_end": 7,
      "section": "Results",
      "chunk_id": "chunk-0012"
    }
  ]
}
```

The raw value preserves fidelity to the paper. The normalized value supports
comparison with the human reference. The qualifier prevents the pipeline from
treating conceptual discussion, hypotheses and empirical findings as
equivalent. Evidence enables traceability and manual verification.

### Decisions required at the meeting

1. Are all eight substantive fields in scope, or should the MVP use only five?
2. Should relation tuples such as `(bias, model, SE task)` be evaluated in the
   main experiment or retained as an optional extension?
3. Who validates the normalized human reference and disagreements?
4. How should a correct pipeline value absent from the spreadsheet be scored?
5. Is the human reference called `gold standard` or the more conservative
   `human reference extraction`?

## Proposed model comparison

### Recommended core experiment

Use Qwen2.5-Instruct at 1.5B, 3B and 7B parameters. This makes model capacity
the principal changing factor and reduces the confounding introduced by
comparing unrelated model families. All three expose the same usage pattern,
support structured/JSON output and fit the existing vLLM-based architecture.

| Model | Purpose | License note |
| --- | --- | --- |
| Qwen2.5-1.5B-Instruct | Small-capacity condition | Apache 2.0 |
| Qwen2.5-3B-Instruct | Medium-capacity condition | `qwen-research`; confirm acceptability |
| Qwen2.5-7B-Instruct | Large-capacity condition | Apache 2.0; already tested on PCAD |

The main comparison should use BF16 for every model. Introducing quantization
for only one model would confound model size with numerical precision.

### Optional extension

After the controlled size comparison, add one similarly sized model from a
different family. This tests whether findings generalize beyond Qwen, but it is
not necessary for the minimum viable thesis.

### Settings to freeze

- temperature: 0 or the lowest value accepted by every model;
- identical chunks and retrieved passages for every model;
- identical prompts and JSON schema;
- identical maximum output tokens;
- fixed model revisions, vLLM version and generation configuration;
- at least one complete run; repeated runs only if nondeterminism remains or
  time permits.

## Implementation started

The accompanying skeleton already defines:

- a machine-readable extraction schema;
- Pydantic models for values and provenance;
- deterministic page-aware chunking;
- transparent per-field lexical retrieval;
- an OpenAI-compatible extraction client for vLLM;
- JSON validation and basic evidence integrity checks;
- unit tests for chunking, retrieval and schema consistency.

The next implementation decision is the PDF parser. It should return page-aware
text and be frozen before comparing models. The next data task is to convert
the 10 human spreadsheet rows into atomic, normalized reference values.

## Suggested meeting outcome

The meeting should approve:

1. the eight-field schema or a smaller MVP subset;
2. the controlled Qwen 1.5B/3B/7B comparison or an alternative model set;
3. the definition and validation process for the human reference;
4. whether evidence correctness is a primary metric;
5. the treatment of relation extraction as core scope or optional extension.

