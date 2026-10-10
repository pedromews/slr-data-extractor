"""Small fixtures live in tests, independent of documentation/examples."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from slr_data_extraction.definitions.result_definition import FieldExtraction
from slr_data_extraction.definitions.schema_definition import ReviewSchema, fingerprint
from slr_data_extraction.validation.evidence_validation import validate_field

ROOT = Path(__file__).resolve().parents[1]


class SchemaTests(unittest.TestCase):
    def setUp(self):
        self.raw = {'schema_id': 'fixture', 'schema_version': '1', 'title': 'Test review',
                    'fields': [{'name': 'finding', 'definition': 'Reported finding',
                                'retrieval_terms': ['finding']}]}

    def test_invalid_schemas(self):
        cases = []
        duplicate = copy.deepcopy(self.raw); duplicate['fields'] *= 2; cases.append(duplicate)
        unknown = copy.deepcopy(self.raw); unknown['relations'] = []; cases.append(unknown)
        blank = copy.deepcopy(self.raw); blank['fields'][0]['definition'] = ' '; cases.append(blank)
        empty = copy.deepcopy(self.raw); empty['fields'][0]['retrieval_terms'] = []; cases.append(empty)
        for name in ['rules', 'qualifiers', 'unit_of_extraction']:
            removed = copy.deepcopy(self.raw)
            removed['fields'][0][name] = [] if name == 'rules' else {}
            cases.append(removed)
        for case in cases:
            with self.subTest(case=case), self.assertRaises(ValueError):
                ReviewSchema.model_validate(case)

    def test_textual_values_with_evidence(self):
        field = ReviewSchema.model_validate(self.raw).fields[0]
        # No values is valid and does not need evidence.
        absent = FieldExtraction(field_name='finding', status='not_found_in_context', values=[])
        validate_field(absent, field, [], [])
        from slr_data_extraction.chunking import PageText, build_chunks
        pages = [{'page': 1, 'text': 'A finding.'}]
        chunks = build_chunks([PageText(1, 'A finding.')], max_chars=100, overlap_chars=0)
        payload = {'field_name': 'finding', 'status': 'extracted', 'values': [{
            'value': 'finding',
            'evidence': [{'quote': 'A finding.', 'page_start': 1, 'page_end': 1,
                          'chunk_id': chunks[0].chunk_id}]}]}
        validate_field(FieldExtraction.model_validate(payload), field, chunks, pages)
        for value in [24, True, 2.5, None, '', '   ']:
            bad = copy.deepcopy(payload); bad['values'][0]['value'] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                FieldExtraction.model_validate(bad)

    def test_value_contract_rejects_legacy_properties(self):
        from slr_data_extraction.definitions.result_definition import ExtractedValue
        payload = {'value': 'A supported finding', 'evidence': [{
            'quote': 'A finding.', 'page_start': 1, 'page_end': 1,
            'chunk_id': 'chunk-0001'}]}
        for name in ['raw_value', 'normalized_value']:
            with self.subTest(name=name), self.assertRaises(ValueError):
                ExtractedValue.model_validate({**payload, name: 'finding'})
        with self.assertRaises(ValueError):
            ExtractedValue.model_validate({**payload, 'evidence': []})
        properties = ExtractedValue.model_json_schema()['properties']
        self.assertEqual(set(properties), {'value', 'evidence'})

    def test_only_two_states(self):
        for status in ['ambiguous', 'not_applicable', 'extracted']:
            with self.subTest(status=status), self.assertRaises(ValueError):
                FieldExtraction(field_name='finding', status=status, values=[])

    def test_fingerprint(self):
        self.assertEqual(fingerprint(self.raw), fingerprint(dict(reversed(list(self.raw.items())))))
        changed = copy.deepcopy(self.raw); changed['fields'][0]['definition'] += ' changed'
        self.assertNotEqual(fingerprint(self.raw), fingerprint(changed))

    def test_cli_prepares_renamed_schema_without_server(self):
        with tempfile.TemporaryDirectory() as tmp:
            article = Path(tmp) / 'article.json'
            article.write_text(json.dumps({'study_id': 'TEST', 'title': 'Test',
                'pages': [{'page': 1, 'text': 'Gender bias was observed.'}]}))
            run = Path(tmp) / 'run'
            result = subprocess.run([sys.executable, '-m', 'slr_data_extraction.execution.cli',
                '--input', str(article), '--run-dir', str(run), '--prepare-only'],
                capture_output=True, text=True, cwd=ROOT)
            self.assertEqual(result.returncode, 0, result.stderr)
            manifest = json.loads((run / 'manifest.json').read_text())
            self.assertEqual(manifest['status'], 'prepared')
            self.assertEqual(manifest['schema_id'], 'gender_and_beyond')
            schema = json.loads((ROOT / 'config/gender_and_beyond_schema.json').read_text())
            expected_names = [field['name'] for field in schema['fields']]
            self.assertEqual(len(list(run.glob('*.request.json'))), len(expected_names))
            selection = json.loads((run / 'retrieval.json').read_text())
            self.assertEqual([item['field'] for item in selection], expected_names)
            self.assertTrue((run / 'source/pipeline.py').exists())
            source_root = ROOT / 'src/slr_data_extraction'
            expected = {p.relative_to(source_root) for p in source_root.rglob('*.py')}
            actual = {p.relative_to(run / 'source') for p in (run / 'source').rglob('*.py')}
            self.assertEqual(actual, expected)
            import hashlib
            digest = hashlib.sha256()
            for relative in sorted(expected):
                self.assertEqual((run / 'source' / relative).read_bytes(),
                                 (source_root / relative).read_bytes())
                digest.update(relative.as_posix().encode())
                digest.update((source_root / relative).read_bytes())
            self.assertEqual(manifest['source_sha256'], digest.hexdigest())
            self.assertFalse((run / 'result.json').exists())
            requests = [json.loads(p.read_text()) for p in run.glob('*.request.json')]
            self.assertTrue(all(r['response_format'] == requests[0]['response_format'] for r in requests))
            for request in requests:
                serialized = json.dumps(request)
                for removed in ['unit_of_extraction', 'raw_value', 'normalized_value']:
                    self.assertNotIn(removed, serialized)

    def test_quote_length_boundary_and_exported_constraint(self):
        from slr_data_extraction.definitions.result_definition import Evidence
        common = dict(page_start=1, page_end=1, chunk_id='chunk-0001')
        self.assertEqual(len(Evidence(quote='x' * 400, **common).quote), 400)
        with self.assertRaises(ValueError):
            Evidence(quote='x' * 401, **common)
        schema = FieldExtraction.model_json_schema()
        self.assertEqual(schema['$defs']['Evidence']['properties']['quote']['maxLength'], 400)
