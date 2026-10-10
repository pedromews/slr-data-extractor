import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import httpx
from openai import OpenAI

from slr_data_extraction.execution.audit import Audit
from slr_data_extraction.validation.preflight import preflight
from slr_data_extraction.definitions.result_definition import FieldExtraction
from slr_data_extraction.pipeline import ExtractionPipeline
from slr_data_extraction.validation.evidence_validation import validate_field

ROOT = Path(__file__).resolve().parents[1]


class PilotTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name)
        self.article = {'study_id': 'TEST', 'title': 'Test paper', 'pages': [
            {'page': 1, 'text': 'Background only.', 'status': 'ok', 'sections': []},
            {'page': 2, 'text': 'gender bias observed', 'status': 'ok', 'sections': [
                {'start': 0, 'end': 20, 'section': 'Results'}]}]}
        config = json.loads((ROOT / 'config/models/qwen.json').read_text())
        config['model_id'] = 'test-model'
        self.pipeline = ExtractionPipeline(ROOT / 'config/gender_and_beyond_schema.json', config)
        self.chunks, self.prepared = self.pipeline.prepare(self.article)
        self.field = self.prepared[0]['field']
        self.value = {'field_name': 'bias_types', 'status': 'extracted', 'values': [{
            'value': 'gender bias',
            'evidence': [{
                'quote': 'gender bias', 'page_start': 2, 'page_end': 2,
                'chunk_id': next(c.chunk_id for c in self.chunks if 'gender bias' in c.text), 'section': 'Results'}]}]}

    def test_fragment_section_requires_exact_span_coverage(self):
        from slr_data_extraction.pipeline import fragment_section
        page = {'text': 'Intro.\nResults   here.', 'sections': [
            {'start': 0, 'end': 7, 'section': 'Introduction'},
            {'start': 7, 'end': 22, 'section': 'Results'}]}
        self.assertEqual(fragment_section('Results here.', page), 'Results')
        self.assertIsNone(fragment_section('Intro. Results here.', page))
        self.assertIsNone(fragment_section('Missing', page))
        self.assertIsNone(fragment_section('Results here.', {'text': page['text']}))
        self.assertIsNone(fragment_section('same', {'text': 'same same', 'sections': [
            {'start': 0, 'end': 9, 'section': 'Results'}]}))

    def test_request_labels_each_page_fragment_without_leaking_sections(self):
        prompt = self.prepared[0]['request']['messages'][1]['content']
        self.assertIn('[page 1; parser section: null] Background only.', prompt)
        self.assertIn('[page 2; parser section: "Results"] gender bias observed', prompt)
        self.assertNotIn('heuristic section labels', prompt)

    def test_valid_evidence_and_section(self):
        result = FieldExtraction.model_validate(self.value)
        self.assertEqual(validate_field(result, self.field, self.chunks, self.article['pages']), result)

    def test_invalid_evidence_is_rejected(self):
        for change in [dict(page_start=1, page_end=1), dict(quote='invented'),
                       dict(quote='   '), dict(section='Discussion'), dict(chunk_id='missing'),
                       dict(quote='Gender bias')]:
            with self.subTest(change=change):
                value = copy.deepcopy(self.value)
                value['values'][0]['evidence'][0].update(change)
                with self.assertRaises(ValueError):
                    validate_field(FieldExtraction.model_validate(value), self.field,
                                   self.chunks, self.article['pages'])

    def test_wrong_field_is_rejected(self):
        value = copy.deepcopy(self.value)
        value['field_name'] = 'llm_systems'
        with self.assertRaises(ValueError):
            validate_field(FieldExtraction.model_validate(value), self.field,
                           self.chunks, self.article['pages'])

    def test_empty_or_failed_pages_block_generation(self):
        for status in ['empty', 'error']:
            article = copy.deepcopy(self.article)
            article['pages'][0]['status'] = status
            with self.assertRaises(ValueError):
                self.pipeline.prepare(article)

    def test_late_document_evidence_is_retrieved(self):
        article = {'pages': [{'page': i, 'text': 'unrelated content ' * 150} for i in range(1, 9)]}
        article['pages'].append({'page': 9, 'text': 'gender bias fairness ' * 100})
        _, prepared = self.pipeline.prepare(article)
        self.assertEqual(prepared[0]['selected'][0].page_end, 9)

    def client(self, content, finish='stop', http_status=200):
        def handler(request):
            self.assertEqual(request.url.path, '/v1/chat/completions')
            body = {'id': 'test', 'object': 'chat.completion', 'created': 0, 'model': 'test-model',
                    'choices': [{'index': 0, 'finish_reason': finish,
                                 'message': {'role': 'assistant', 'content': content}}]}
            return httpx.Response(http_status, json=body)
        client = OpenAI(base_url='http://127.0.0.1:8000/v1', api_key='local', max_retries=0,
                        http_client=httpx.Client(transport=httpx.MockTransport(handler)))
        self.addCleanup(client.close)
        return client

    def test_raw_response_and_validated_result_are_saved(self):
        self.pipeline.client = self.client(json.dumps(self.value))
        fields = self.pipeline.extract(self.prepared[:1], self.article['pages'], Audit(self.directory))
        self.assertEqual(fields[0].values[0].value, 'gender bias')
        self.assertTrue((self.directory / 'field-01.raw.txt').exists())
        self.assertTrue((self.directory / 'field-01.validated.json').exists())
        self.assertEqual(json.loads((self.directory / 'field-01.status.json').read_text())['status'], 'completed')

    def test_bad_json_and_truncated_response_remain_auditable(self):
        for content, finish in [('invalid JSON', 'stop'), (json.dumps(self.value), 'length')]:
            with self.subTest(finish=finish):
                self.pipeline.client = self.client(content, finish)
                with self.assertRaises(ValueError):
                    self.pipeline.extract(self.prepared[:1], self.article['pages'], Audit(self.directory))
                status = json.loads((self.directory / 'field-01.status.json').read_text())
                self.assertEqual(status['status'], 'failed')
                self.assertTrue((self.directory / 'field-01.raw.txt').exists())
                self.assertFalse((self.directory / 'field-01.validated.json').exists())

    def test_http_errors_are_saved(self):
        self.pipeline.client = self.client('server error', http_status=400)
        with self.assertRaises(Exception):
            self.pipeline.extract(self.prepared[:1], self.article['pages'], Audit(self.directory))
        self.assertIn('server error', (self.directory / 'field-01.raw.txt').read_text())
        self.assertEqual(json.loads((self.directory / 'field-01.status.json').read_text())['status'], 'failed')

    def test_context_overflow_fails_without_truncating(self):
        config = json.loads((ROOT / 'config/models/qwen.json').read_text())
        config['model_id'] = 'test-model'
        original = copy.deepcopy(self.prepared[0]['request'])
        def handler(request):
            if request.url.path == '/version':
                return httpx.Response(200, json={'version': '0.11.0'})
            if request.url.path == '/v1/models':
                return httpx.Response(200, json={'data': [{'id': 'test-model'}]})
            self.assertEqual(request.url.path, '/tokenize')
            return httpx.Response(200, json={'count': 8000, 'max_model_len': 8192})
        client = httpx.Client(transport=httpx.MockTransport(handler))
        with patch('slr_data_extraction.validation.preflight.httpx.Client', return_value=client):
            with self.assertRaisesRegex(ValueError, 'Context overflow'):
                preflight(config, self.prepared, self.directory)
        self.assertEqual(self.prepared[0]['request'], original)

    def test_removed_qualifiers_are_rejected(self):
        value = copy.deepcopy(self.value)
        value['values'][0]['qualifiers'] = {'evidence_status': 'observed'}
        with self.assertRaises(ValueError):
            FieldExtraction.model_validate(value)
