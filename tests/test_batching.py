import unittest
from slr_data_extraction.chunking.batching import plan_batches
from slr_data_extraction.chunking.chunking_creation import Chunk


def request(field, chunks):
    return {'messages': [{'content': field + ''.join(c.text for c in chunks)}]}


class BatchTests(unittest.TestCase):
    def test_coverage_order_shared_fields_and_exact_limit(self):
        chunks = [Chunk(str(i), 1, 1, 'abc') for i in range(5)]
        batches = plan_batches(chunks, request, ['x', 'long'], max_message_chars=10)
        self.assertEqual([len(b) for b in batches], [2, 2, 1])
        self.assertEqual([c for b in batches for c in b], chunks)
        self.assertEqual(batches, plan_batches(chunks, request, ['x', 'long'], max_message_chars=10))

    def test_overflow_is_explicit_not_truncation(self):
        chunks = [Chunk('a', 1, 1, 'x'), Chunk('b', 1, 1, 'x' * 20)]
        with self.assertRaisesRegex(ValueError, 'Single chunk'):
            plan_batches(chunks, request, ['field'], max_message_chars=10)
        with self.assertRaises(ValueError):
            plan_batches([chunks[0], chunks[0]], request, ['x'])

    def test_empty_and_invalid(self):
        self.assertEqual(plan_batches([], request, ['x']), [])
        with self.assertRaises(ValueError):
            plan_batches([], request, [])
        with self.assertRaises(ValueError):
            plan_batches([], request, ['x'], max_message_chars=0)
