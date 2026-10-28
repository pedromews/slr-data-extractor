import json
import unittest
from pathlib import Path
from slr_data_extraction.pipeline import ExtractionPipeline, SYSTEM_PROMPT

ROOT = Path(__file__).resolve().parents[1]

class PromptStyleTests(unittest.TestCase):
    def test_pair_preserves_controls_and_evidence(self):
        for mode in ('segment_ids',):
            for terms in (False, True):
                with self.subTest(mode=mode, terms=terms):
                    config = json.loads((ROOT/'config/models/qwen.json').read_text())
                    config.update(evidence_mode=mode, include_retrieval_terms_in_prompt=terms)
                    a = ExtractionPipeline(ROOT/'config/gender_and_beyond_schema.json', config)
                    b = ExtractionPipeline(ROOT/'config/gender_and_beyond_schema.json',
                                           dict(config, field_prompt_style='instruction'))
                    article = {'pages': [{'page': 1, 'text': 'Gender bias.', 'sections': []}]}
                    ca, pa = a.prepare(article)
                    cb, pb = b.prepare(article)
                    self.assertEqual(ca, cb)
                    self.assertEqual(a.prompt_version, b.prompt_version)
                    for x, y in zip(pa, pb):
                        ra, rb = x['request'], y['request']
                        self.assertEqual({k:v for k,v in ra.items() if k != 'messages'},
                                         {k:v for k,v in rb.items() if k != 'messages'})
                        self.assertEqual(ra['messages'][0], rb['messages'][0])
                        ua, ub = ra['messages'][1]['content'], rb['messages'][1]['content']
                        self.assertEqual(ua.split('Output JSON schema: ')[1],
                                         ub.split('Output JSON schema: ')[1])
                        self.assertIn(x['field'].definition, ub)
                        self.assertIn(a.review.title, ub)
                        self.assertEqual('Retrieval terms:' in ub, terms)
                        self.assertEqual(rb['messages'][0]['content'], SYSTEM_PROMPT)
                        self.assertIn(json.dumps(x['field'].name), ub)
                        self.assertNotIn('{field_definition}', ub)

    def test_json_style_requires_new_preparation(self):
        with self.assertRaisesRegex(ValueError, 'field_prompt_style'):
            ExtractionPipeline(ROOT/'config/gender_and_beyond_schema.json',
                               {'model_id': 'test', 'field_prompt_style': 'json'})

    def test_invalid_style(self):
        with self.assertRaisesRegex(ValueError, 'field_prompt_style'):
            ExtractionPipeline(ROOT/'config/gender_and_beyond_schema.json',
                               {'model_id': 'test', 'field_prompt_style': 'other'})

    def test_literal_mode_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Only segment_ids'):
            ExtractionPipeline(ROOT/'config/gender_and_beyond_schema.json',
                               {'model_id': 'test', 'evidence_mode': 'verbatim'})
