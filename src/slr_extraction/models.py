from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    quote: str = Field(min_length=1, description="Verbatim supporting passage")
    page_start: int = Field(ge=1)
    page_end: int = Field(ge=1)
    section: str | None = None
    chunk_id: str = Field(min_length=1)

    @model_validator(mode="after")
    def valid_page_range(self) -> "Evidence":
        if self.page_end < self.page_start:
            raise ValueError("page_end must be greater than or equal to page_start")
        return self


class ExtractedValue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    raw_value: str = Field(min_length=1)
    normalized_value: str | None = None
    qualifier: Literal[
        "empirically_observed",
        "reported_not_observed",
        "author_hypothesis",
        "background_claim",
        "proposed",
        "implemented",
        "empirically_tested",
        "subject_under_test",
        "auxiliary_model",
        "technical_task",
        "socio_technical_context",
        "not_applicable",
        "unspecified",
    ] = "unspecified"
    evidence: list[Evidence] = Field(min_length=1)


class FieldExtraction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field_name: str
    values: list[ExtractedValue] = Field(default_factory=list)
    not_reported: bool = False
    notes: str | None = None

    @model_validator(mode="after")
    def consistent_absence(self) -> "FieldExtraction":
        if self.not_reported and self.values:
            raise ValueError("not_reported cannot be true when values are present")
        return self


class ArticleExtraction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str
    study_id: str
    title: str
    model_id: str
    fields: list[FieldExtraction]

