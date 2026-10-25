import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('scope_diagnostic', Path(__file__).resolve().parents[1] / 'scripts/run_scope_diagnostic.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ScopeDiagnosticTests(unittest.TestCase):
    def test_only_system_suffix_changes(self):
        original = {'model': 'model', 'temperature': 0, 'max_tokens': 2048,
                    'messages': [{'role': 'system', 'content': 'Original instructions'},
                                 {'role': 'user', 'content': 'Definition and frozen passages'}],
                    'extra_body': {'chat_template_kwargs': {'enable_thinking': False}}}
        baseline = module.variant_request(original, 'baseline')
        self.assertEqual(baseline, original)
        for variant in ('clarified', 'individual-items'):
            with self.subTest(variant=variant):
                changed = module.variant_request(original, variant)
                self.assertEqual(changed['messages'][0]['content'],
                                 original['messages'][0]['content'] + module.SUPPLEMENTS[variant])
                changed['messages'][0]['content'] = original['messages'][0]['content']
                self.assertEqual(changed, original)
                self.assertEqual(original['messages'][0]['content'], 'Original instructions')
