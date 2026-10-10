"""Small contract for researcher-defined textual extraction fields."""
import argparse
import hashlib
import json
from pathlib import Path
from typing import Annotated
from pydantic import BaseModel, ConfigDict, Field, model_validator


# Minimal valid JSON:
# {
#   "schema_id": "gender_and_beyond",
#   "schema_version": "4.0-mvp",
#   "title": "Gender and Beyond",
#   "fields": [
#     {
#       "name": "bias_types",
#       "definition": "Bias types explicitly reported by the study.",
#       "retrieval_terms": ["bias", "fairness"]
#     }
#   ]
# }
#
# Invalid examples: each change below, applied independently to the valid
# example, triggers a validation error:
# - Remove "definition": a required property is missing.
# - Set "retrieval_terms": "bias": a list is required, not a string.
# - Set "retrieval_terms": []: at least one term is required.
# - Set "name": "Bias Types": identifiers must match ^[a-z][a-z0-9_]*$.
# - Set "definition": "   ": text must contain non-whitespace characters.
# - Add "value_type": "text" to the field: this property is not part of the MVP.
# - Set "fields": []: the review must define at least one field.
# - Duplicate the field in "fields": field names must be unique.
# - Add "rules" or "qualifiers": these properties are not part of this contract.
#
# These rules check structure and basic configuration consistency;
# researchers remain responsible for the scientific adequacy of definitions.
# Pydantic validates the contract directly, without reading meta_schema.json.

Text = Annotated[str, Field(min_length=1, pattern=r'\S')]
Identifier = Annotated[str, Field(pattern=r'^[a-z][a-z0-9_]*$')]


class Contract(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)


class FieldDefinition(Contract):
    name: Identifier
    definition: Text
    retrieval_terms: list[Text] = Field(min_length=1)


class ReviewSchema(Contract):
    schema_id: Identifier
    schema_version: Text
    title: Text
    fields: list[FieldDefinition] = Field(min_length=1)

    @model_validator(mode='after')
    def unique_fields(self):
        names = [field.name for field in self.fields]
        if len(names) != len(set(names)):
            raise ValueError('Duplicate field name')
        return self


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(',', ':')).encode()).hexdigest()


def load_schema(path):
    return ReviewSchema.model_validate_json(Path(path).read_text(encoding='utf-8'))


def main():
    parser = argparse.ArgumentParser(description='Validate a review schema without a model call.')
    parser.add_argument('schema')
    args = parser.parse_args()
    schema = load_schema(args.schema)
    print(f'{schema.schema_id}@{schema.schema_version}: valid ({len(schema.fields)} fields)')


if __name__ == '__main__':
    main()
