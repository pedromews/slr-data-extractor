import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from slr_data_extraction.definitions.result_definition import FieldExtraction

spec = importlib.util.spec_from_file_location('run_batch_field', Path(__file__).resolve().parents[1] / 'scripts/run_batch_field.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def result(value='bias', quote='Bias.', notes=None):
    return FieldExtraction.model_validate({'field_name': 'bias_types', 'status': 'extracted',
        'notes': notes, 'values': [{'value': value, 'evidence': [{'quote': quote,
        'page_start': 1, 'page_end': 1, 'chunk_id': 'chunk-0001'}]}]})


class BatchExecutionTests(unittest.TestCase):
    def test_dedup_is_exact_and_keeps_provenance_and_notes(self):
        merged, provenance = module.consolidate('bias_types', [
            (1, result(notes='Proposed')), (2, result()),
            (3, result(value='Bias')), (4, result(quote='Other evidence.'))])
        self.assertEqual(len(merged.values), 3)
        self.assertEqual(provenance, [[1, 2], [3], [4]])
        self.assertEqual(merged.notes, 'Batch 1: Proposed')

    def test_empty_batch_does_not_erase_other_findings(self):
        empty = FieldExtraction(field_name='bias_types', status='not_found_in_context', values=[])
        merged, _ = module.consolidate('bias_types', [(1, empty), (2, result())])
        self.assertEqual(merged.status, 'extracted')

    def test_resume_only_never_attempted(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'batch'
            self.assertEqual(module.attempt_state(p), 'pending')
            p.mkdir()
            self.assertEqual(module.attempt_state(p), 'interrupted')
            status = p / 'field-01.status.json'
            for state in ['failed', 'completed']:
                status.write_text(json.dumps({'status': state}))
                self.assertEqual(module.attempt_state(p), state)
