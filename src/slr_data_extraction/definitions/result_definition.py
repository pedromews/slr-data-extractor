"""Fixed textual output format for the initial pilot."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

OUTPUT_VERSION = '4.0-mvp'


# Example of a structurally valid FieldExtraction returned by the model:
# {
#   "field_name": "bias_types",
#   "status": "extracted",
#   "values": [
#     {
#       "value": "gender bias",
#       "evidence": [
#         {
#           "quote": "We observed gender bias in the generated responses.",
#           "page_start": 2,
#           "page_end": 2,
#           "section": null,
#           "chunk_id": "chunk-0003"
#         }
#       ]
#     }
#   ],
#   "notes": null
# }
# This is a fictional example, not an annotation from a real study.
# Each value needs at least one supporting evidence entry. Only the quote must
# be literal; value expresses the extracted information. Pages are one-based
# physical PDF page numbers. section and notes may be omitted or set to null.
# chunk_id identifies a supplied chunk and is required in pipeline responses;
# the separately maintained human reference does not need chunk IDs.
#
# A field with no supported value uses:
# {"field_name": "bias_types", "status": "not_found_in_context", "values": []}
# This means absence from the supplied context, not necessarily the full paper.
#
# Invalid examples (each change independently violates the Pydantic contract):
# - Set status to "extracted" with values=[] (or the reverse combination).
# - Set value to "   ", null, or a number: nonblank text is required.
# - Set evidence=[]: every extracted value needs evidence.
# - Use a blank quote or a quote longer than 400 characters.
# - Set page_start to 0, or page_end below page_start.
# - Omit chunk_id, or add removed properties such as raw_value/normalized_value.
#
# These models validate structure, not factual correctness. The separate
# evidence validator checks the requested field, selected chunk, literal quote,
# actual page range and any supplied section. Semantic support still needs review.
# After extraction, the pipeline wraps the field responses in ArticleExtraction:
# output_version, schema_id, schema_version, schema_sha256, study_id, title,
# model_id and fields. The model returns one field; the pipeline adds metadata.


class Output(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)


class Evidence(Output):
    quote: str = Field(min_length=1, max_length=400, pattern=r'\S')
    page_start: int = Field(ge=1)
    page_end: int = Field(ge=1)
    section: str | None = None
    chunk_id: str = Field(min_length=1)

    @model_validator(mode='after')
    def valid_page_range(self):
        if self.page_end < self.page_start:
            raise ValueError('page_end must be greater than or equal to page_start')
        return self


class ExtractedValue(Output):
    value: str = Field(min_length=1, pattern=r'\S')
    evidence: list[Evidence] = Field(min_length=1)


class FieldExtraction(Output):
    field_name: str
    status: Literal['extracted', 'not_found_in_context']
    values: list[ExtractedValue]
    notes: str | None = None

    @model_validator(mode='after')
    def consistent_status(self):
        if (self.status == 'extracted') != bool(self.values):
            raise ValueError('Only extracted status has values, and it must have at least one')
        return self


class ArticleExtraction(Output):
    output_version: Literal['4.0-mvp'] = OUTPUT_VERSION
    schema_id: str
    schema_version: str
    schema_sha256: str
    study_id: str
    title: str
    model_id: str
    fields: list[FieldExtraction]
