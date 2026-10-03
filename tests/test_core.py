import unittest

from slr_extraction.chunking import PageText, build_chunks
from slr_extraction.models import Evidence, ExtractedValue, FieldExtraction
from slr_extraction.retrieval import rank_chunks


class CoreTests(unittest.TestCase):
    def test_chunking_preserves_pages(self):
        chunks = build_chunks(
            [PageText(1, "alpha " * 30), PageText(2, "beta " * 30)],
            max_chars=100,
            overlap_chars=10,
        )
        self.assertGreaterEqual(len(chunks), 2)
        self.assertEqual(chunks[0].page_start, 1)
        self.assertEqual(chunks[-1].page_end, 2)

    def test_retrieval_prefers_matching_chunk(self):
        chunks = build_chunks(
            [PageText(1, "unrelated text"), PageText(2, "gender bias fairness")],
            max_chars=50,
            overlap_chars=0,
        )
        ranked = rank_chunks(chunks, ["gender bias"], top_k=1)
        self.assertIn("gender", ranked[0].text)

    def test_absence_and_values_are_mutually_exclusive(self):
        value = ExtractedValue(
            raw_value="gender bias",
            evidence=[Evidence(quote="gender bias", page_start=1, page_end=1, chunk_id="c1")],
        )
        with self.assertRaises(ValueError):
            FieldExtraction(field_name="bias_types", values=[value], not_reported=True)


if __name__ == "__main__":
    unittest.main()

