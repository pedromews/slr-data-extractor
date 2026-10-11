import math
import unittest
from slr_data_extraction.chunking.chunking_creation import Chunk
from slr_data_extraction.chunking.chunk_selection import rank_chunks, bm25_scores, bm25_tokens


def chunk(identifier, text):
    return Chunk(identifier, 1, 1, text)


class BM25Tests(unittest.TestCase):
    def test_formula_and_query_deduplication(self):
        chunks = [chunk('a', 'metric metric'), chunk('b', 'other other')]
        expected = math.log(2) * 5 / 3.5
        self.assertAlmostEqual(bm25_scores(chunks, ['metrics'])[0], expected)
        self.assertEqual(bm25_scores(chunks, ['metrics', 'metric']), bm25_scores(chunks, ['metric']))
        self.assertEqual(bm25_scores(chunks, ['metric'])[1], 0)

    def test_length_normalization(self):
        chunks = [chunk('long', 'metric ' + 'other ' * 20), chunk('short', 'metric')]
        self.assertEqual(rank_chunks(chunks, ['metric'], 1, method='bm25')[0].chunk_id, 'short')

    def test_plural_and_stable_ties(self):
        self.assertEqual(bm25_tokens('Metrics datasets strategies bias fairness'),
                         ['metric', 'dataset', 'strategy', 'bias', 'fairness'])
        chunks = [chunk('a', 'metrics'), chunk('b', 'metric')]
        self.assertEqual(rank_chunks(chunks, ['metric'], 2, method='bm25'), chunks)
        self.assertEqual(rank_chunks(chunks, ['unknown'], 2, method='bm25'), chunks)
        self.assertEqual(rank_chunks(chunks, ['metric'], 1)[0].chunk_id, 'b')

    def test_empty_and_invalid(self):
        self.assertEqual(bm25_scores([], ['test']), [])
        self.assertEqual(bm25_scores([chunk('a', '')], ['test']), [0.0])
        with self.assertRaises(ValueError):
            rank_chunks([], [], 1, method='invalid')
        with self.assertRaises(ValueError):
            rank_chunks([], [], 0, method='bm25')
