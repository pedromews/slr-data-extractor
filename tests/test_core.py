import unittest

from slr_data_extraction.chunking import Chunk, PageText, build_chunks, rank_chunks
from slr_data_extraction.definitions.result_definition import Evidence, ExtractedValue, FieldExtraction


class CoreTests(unittest.TestCase):
    def test_chunking_preserves_text_without_overlap(self):
        text = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        chunks = build_chunks([PageText(1, text)], max_chars=10, overlap_chars=0)
        self.assertEqual("".join(c.text for c in chunks), text)
        self.assertTrue(all((c.page_start, c.page_end) == (1, 1) for c in chunks))

    def test_chunking_respects_limit_across_pages(self):
        chunks = build_chunks([PageText(1, "abc"), PageText(2, "defghijk")],
                              max_chars=10, overlap_chars=0)
        self.assertTrue(all(len(c.text) <= 10 for c in chunks))
        self.assertEqual("".join(c.text for c in chunks), "abc defghijk")
        self.assertEqual([(c.page_start, c.page_end) for c in chunks], [(1, 2), (2, 2)])

    def test_chunking_overlap_preserves_text(self):
        text = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        chunks = build_chunks([PageText(1, text)], max_chars=10, overlap_chars=3)
        reconstructed = chunks[0].text
        for previous, current in zip(chunks, chunks[1:]):
            self.assertEqual(previous.text[-3:], current.text[:3])
            reconstructed += current.text[3:]
        self.assertEqual(reconstructed, text)
        self.assertTrue(all(len(c.text) <= 10 for c in chunks))

    def test_overlap_preserves_all_contributing_pages(self):
        chunks = build_chunks([PageText(1, "abcdef"), PageText(2, "gh"),
                               PageText(3, "ijklmn")], max_chars=10, overlap_chars=6)
        self.assertEqual((chunks[1].page_start, chunks[1].page_end), (1, 3))
        self.assertIn("ef", chunks[1].text)
        self.assertIn("gh", chunks[1].text)
        self.assertIn("ij", chunks[1].text)

    def test_exact_boundary_does_not_emit_overlap_only_chunk(self):
        chunks = build_chunks([PageText(1, "abcdefghij")], max_chars=10, overlap_chars=3)
        self.assertEqual([c.text for c in chunks], ["abcdefghij"])

    def test_empty_input(self):
        self.assertEqual(build_chunks([], max_chars=100, overlap_chars=10), [])

    def test_invalid_chunking_parameters(self):
        for maximum, overlap in [(0, 0), (10, -1), (10, 10)]:
            with self.subTest(maximum=maximum, overlap=overlap):
                with self.assertRaises(ValueError):
                    build_chunks([PageText(1, "abc")], max_chars=maximum, overlap_chars=overlap)

    def test_chunking_is_deterministic_with_unique_ids(self):
        pages = [PageText(1, "abcdefghijklmnopqrstuvwxyz")]
        chunks = build_chunks(pages, max_chars=10, overlap_chars=3)
        self.assertEqual(chunks, build_chunks(pages, max_chars=10, overlap_chars=3))
        self.assertEqual(len({c.chunk_id for c in chunks}), len(chunks))

    def test_retrieval_prefers_matching_chunk(self):
        unrelated = Chunk("c1", 1, 1, "unrelated text")
        partial = Chunk("c2", 2, 2, "gender representation")
        relevant = Chunk("c3", 3, 3, "gender bias fairness")
        self.assertEqual(rank_chunks([unrelated, partial, relevant], ["gender bias"], top_k=1),
                         [relevant])

    def test_retrieval_ties_preserve_input_order(self):
        chunks = [Chunk("c1", 1, 1, "gender bias"), Chunk("c2", 2, 2, "gender bias")]
        self.assertEqual(rank_chunks(chunks, ["gender bias"], top_k=2), chunks)

    def test_absence_and_values_are_mutually_exclusive(self):
        value = ExtractedValue(
            raw_value="gender bias", normalized_value=None, qualifiers={},
            evidence=[Evidence(quote="gender bias", page_start=1, page_end=1, chunk_id="c1")],
        )
        with self.assertRaises(ValueError):
            FieldExtraction(field_name="bias_types", values=[value], status="not_found_in_context")


if __name__ == "__main__":
    unittest.main()
