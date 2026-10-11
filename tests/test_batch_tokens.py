import importlib.util
import tempfile
import unittest
from pathlib import Path
import httpx

spec = importlib.util.spec_from_file_location('check_batch_tokens',
    Path(__file__).resolve().parents[1] / 'scripts/check_batch_tokens.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class TokenBudgetTests(unittest.TestCase):
    def test_counts_every_request_and_preserves_template_options(self):
        calls = []
        def handler(request):
            import json
            calls.append(json.loads(request.content))
            self.assertEqual(request.url.path, '/tokenize')
            return httpx.Response(200, json={'count': 6000 + len(calls), 'max_model_len': 8192})
        req = {'model': 'test', 'messages': [{'role': 'user', 'content': 'Text'}],
               'max_tokens': 2191, 'extra_body': {'chat_template_kwargs': {'enable_thinking': False}}}
        with tempfile.TemporaryDirectory() as tmp, httpx.Client(transport=httpx.MockTransport(handler)) as http:
            rows = module.check_requests(http, 'http://localhost', 'test',
                [('a.request.json', req), ('b.request.json', req)], 8192, Path(tmp))
            self.assertTrue(rows[0]['fits'])
            self.assertFalse(rows[1]['fits'])
            self.assertEqual(calls[0]['chat_template_kwargs'], {'enable_thinking': False})
            self.assertEqual(len(list(Path(tmp).glob('*.tokenize.json'))), 2)

    def test_rejects_wrong_model_before_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, 'Model mismatch'):
                module.check_requests(None, '', 'expected',
                    [('test.request.json', {'model': 'other'})], 8192, Path(tmp))
