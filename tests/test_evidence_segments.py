import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from tempfile import TemporaryDirectory
from slr_data_extraction.chunking.chunking_creation import Chunk
from slr_data_extraction.chunking.evidence_segments import build_catalog, resolve_selection
from slr_data_extraction.pipeline import ExtractionPipeline
from slr_data_extraction.execution.audit import Audit
from slr_data_extraction.execution.cli import save_preparation

ROOT = Path(__file__).resolve().parents[1]

class EvidenceSegmentsTests(unittest.TestCase):
    def test_coverage_offsets_pages_and_long_tokens(self):
        first = 'First sentence. ' + 'word ' * 130 + 'x' * 450
        second = 'Another page with soci- etal bias.'
        text = first + ' ' + second
        c = Chunk('chunk-0001', 1, 2, text,
                  ((0, len(first), 1), (len(first)+1, len(text), 2)), 'Discussion')
        catalog = build_catalog([c])
        self.assertEqual(catalog, build_catalog([c]))
        covered = set()
        for e in catalog.values():
            self.assertLessEqual(len(e['quote']), 400)
            self.assertEqual(e['quote'], text[e['start']:e['end']])
            self.assertEqual(e['page_start'], e['page_end'])
            covered.update(range(e['start'], e['end']))
        self.assertTrue(all(i in covered for i, ch in enumerate(text) if not ch.isspace()))

    def test_resolution_rejects_unknown_ids_and_invalid_status(self):
        c = Chunk('c', 1, 1, 'Evidence.', ((0, 9, 1),))
        catalog = build_catalog([c])
        payload = {'field_name': 'f', 'status': 'extracted', 'values': [
            {'value': 'Summary', 'evidence_ids': ['missing']}]}
        with self.assertRaisesRegex(ValueError, 'Unknown'):
            resolve_selection(json.dumps(payload), catalog)
        payload['values'][0]['evidence_ids'] = list(catalog)
        result = resolve_selection(json.dumps(payload), catalog)
        self.assertEqual(result.values[0].evidence[0].quote, 'Evidence.')
        payload['status'] = 'not_found_in_context'
        with self.assertRaises(ValueError):
            resolve_selection(json.dumps(payload), catalog)

    def test_pipeline_audits_raw_ids_and_resolves_final_evidence(self):
        config = json.loads((ROOT/'config/models/qwen.json').read_text())
        config['evidence_mode'] = 'segment_ids'
        pipeline = ExtractionPipeline(ROOT/'config/gender_and_beyond_schema.json', config)
        article = {'pages': [{'page': 1, 'text': 'Gender bias.', 'sections': []}]}
        with TemporaryDirectory() as temp:
            directory = Path(temp)
            chunks, prepared = save_preparation(directory, pipeline, article)
            self.assertTrue((directory/'evidence-catalog.json').exists())
            item = prepared[0]
            self.assertIn('evidence_ids', item['request']['messages'][1]['content'])
            catalog = build_catalog(item['selected'])
            content = json.dumps({'field_name': item['field'].name, 'status': 'extracted',
                'values': [{'value': 'Gender bias', 'evidence_ids': list(catalog)}]})
            raw = SimpleNamespace(text='original response', parse=lambda: SimpleNamespace(
                choices=[SimpleNamespace(finish_reason='stop', message=SimpleNamespace(
                    refusal=None, content=content))]))
            pipeline.client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(
                with_raw_response=SimpleNamespace(create=lambda **kwargs: raw))))
            result = pipeline.extract([item], article['pages'], Audit(directory))
            self.assertEqual(result[0].values[0].evidence[0].quote, 'Gender bias.')
            self.assertEqual((directory/'field-01.raw.txt').read_text(), 'original response')
