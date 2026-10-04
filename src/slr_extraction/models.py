"""Fixed textual output format for the initial pilot."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

OUTPUT_VERSION = '2.0-mvp'


class Output(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)


class Evidence(Output):
    quote: str = Field(min_length=1, pattern=r'\S')
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
    raw_value: str = Field(min_length=1, pattern=r'\S')
    normalized_value: str | None
    qualifiers: dict[str, str]
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
    output_version: Literal['2.0-mvp'] = OUTPUT_VERSION
    schema_id: str
    schema_version: str
    schema_sha256: str
    study_id: str
    title: str
    model_id: str
    fields: list[FieldExtraction]
