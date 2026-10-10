import copy
import json
from pathlib import Path
import unittest
from slr_data_extraction.execution.ollama_cli import native_request
from slr_data_extraction.pipeline import ExtractionPipeline

ROOT = Path(__file__).resolve().parents[1]


class OllamaTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads((ROOT / 'config/pilot-ollama.json').read_text())
        pipeline = ExtractionPipeline(ROOT / 'config/gender_and_beyond_schema.json', self.config)
        _, items = pipeline.prepare({'pages': [{'page': 1, 'text': 'gender bias'}]})
        self.request = items[0]['request']

    def test_full_messages_and_schema_are_preserved(self):
        body = native_request(self.request, self.config)
        for message in self.request['messages']:
            self.assertIn(message['content'], body['prompt'])
        self.assertTrue(body['raw'])
        self.assertEqual(body['format'], self.request['response_format']['json_schema']['schema'])
        self.assertEqual(body['options']['num_predict'], self.config['max_tokens'])

    def test_context_overflow_is_rejected_not_truncated(self):
        request = copy.deepcopy(self.request)
        request['messages'][1]['content'] = 'é' * self.config['max_model_len']
        with self.assertRaisesRegex(ValueError, 'refusing truncation'):
            native_request(request, self.config)

    def test_other_model_templates_are_rejected(self):
        self.config['model_id'] = 'another-model'
        with self.assertRaisesRegex(ValueError, 'only Qwen2.5'):
            native_request(self.request, self.config)
