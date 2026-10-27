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
        for variant in ('clarified', 'individual-items', 'specific-support'):
            with self.subTest(variant=variant):
                changed = module.variant_request(original, variant)
                self.assertEqual(changed['messages'][0]['content'],
                                 original['messages'][0]['content'] + module.SUPPLEMENTS[variant])
                changed['messages'][0]['content'] = original['messages'][0]['content']
                self.assertEqual(changed, original)
                self.assertEqual(original['messages'][0]['content'], 'Original instructions')

    def test_short_replaces_only_system_and_preserves_source(self):
        original = {'model': 'model', 'seed': 42, 'temperature': 0,
                    'messages': [{'role': 'system', 'content': 'Original instructions'},
                                 {'role': 'user', 'content': 'Frozen user message'}],
                    'extra_body': {'chat_template_kwargs': {'enable_thinking': False}}}
        changed = module.variant_request(original, 'short')
        self.assertEqual(changed['messages'][0]['content'], module.SHORT_SYSTEM_PROMPT)
        self.assertNotIn('Original instructions', changed['messages'][0]['content'])
        changed['messages'][0]['content'] = 'Original instructions'
        self.assertEqual(changed, original)
        self.assertEqual(original['messages'][0]['content'], 'Original instructions')

    def test_no_terms_preserves_everything_else_including_passage_text(self):
        prefix = 'Extract field.\nField definition:\nCategories.'
        terms = '\nRetrieval terms: ["gender", "bias"]'
        suffix = '\nOutput JSON schema: {}\nPassages:\nRetrieval terms: literal article text'
        original = {'model': 'model', 'seed': 42,
                    'messages': [{'role': 'system', 'content': 'Original system'},
                                 {'role': 'user', 'content': prefix + terms + suffix}]}
        changed = module.variant_request(original, 'no-terms')
        self.assertEqual(changed['messages'][1]['content'], prefix + suffix)
        changed['messages'][1]['content'] = prefix + terms + suffix
        self.assertEqual(changed, original)
        self.assertEqual(original['messages'][1]['content'], prefix + terms + suffix)

    def test_no_terms_refuses_missing_terms(self):
        request = {'messages': [{'role': 'system', 'content': 'System'},
                               {'role': 'user', 'content': 'Field\nOutput JSON schema: {}\nPassages:\nText'}]}
        with self.assertRaises(ValueError):
            module.variant_request(request, 'no-terms')

    def test_verbatim_preserves_parameters_and_field_header(self):
        original = {'model': 'model', 'seed': 42, 'extra_body': {'top_k': -1},
                    'messages': [{'role': 'system', 'content': 'Shared rules.\nFor each value, return evidence_ids from passages.'},
                                 {'role': 'user', 'content': 'Field and terms\nOutput JSON schema: IDs\nPassages:\nSegments'}]}
        generated = {'messages': [{}, {'content': 'Field and terms\nOutput JSON schema: Quotes\nPassages:\nFull chunk'}]}
        result = module.verbatim_request(original, generated)
        self.assertEqual(result['messages'][1]['content'], generated['messages'][1]['content'])
        self.assertTrue(result['messages'][0]['content'].startswith('Shared rules.\n'))
        self.assertNotIn('return evidence_ids', result['messages'][0]['content'])
        result['messages'] = original['messages']
        self.assertEqual(result, original)
        generated['messages'][1]['content'] = 'Changed definition\nOutput JSON schema: Quotes'
        with self.assertRaises(ValueError):
            module.verbatim_request(original, generated)
