import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject

from slr_extraction.pdf_parser import parse_pdf, section_spans
from slr_extraction.chunking import PageText, build_chunks


def make_pdf(path, texts):
    writer = PdfWriter()
    for text in texts:
        page = writer.add_blank_page(width=612, height=792)
        if text is None:
            continue
        font = DictionaryObject({NameObject('/Type'): NameObject('/Font'),
                                 NameObject('/Subtype'): NameObject('/Type1'),
                                 NameObject('/BaseFont'): NameObject('/Helvetica')})
        page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'): DictionaryObject({
            NameObject('/F1'): writer._add_object(font)})})
        content = DecodedStreamObject()
        lines = [line.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')
                 for line in text.splitlines()]
        content.set_data(('BT /F1 12 Tf 50 740 Td 14 TL ' +
                          ' T* '.join(f'({line}) Tj' for line in lines) + ' ET').encode('ascii'))
        page[NameObject('/Contents')] = writer._add_object(content)
    writer.add_metadata({'/Title': 'Fixture paper'})
    with path.open('wb') as stream:
        writer.write(stream)


class ParserTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'paper.pdf'

    def test_real_pdf_preserves_pages_text_hash_and_sections(self):
        make_pdf(self.path, ['1 Introduction\nUnique first page.', None,
                             '2 Results\nUnique final page.'])
        article = parse_pdf(self.path, study_id='TEST')
        self.assertEqual([p['page'] for p in article['pages']], [1, 2, 3])
        self.assertEqual([p['status'] for p in article['pages']], ['ok', 'empty', 'ok'])
        self.assertIn('Unique first page.', article['pages'][0]['text'])
        self.assertIn('Unique final page.', article['pages'][2]['text'])
        self.assertEqual(article['pages'][1]['text'], '')
        self.assertEqual(article['pages'][2]['sections'][0]['section'], '2 Results')
        self.assertEqual(article['source']['sha256'], hashlib.sha256(self.path.read_bytes()).hexdigest())
        self.assertEqual(article['title'], 'Fixture paper')
        self.assertTrue(article['requires_review'])
        chunks = build_chunks([PageText(p['page'], p['text']) for p in article['pages']], max_chars=6000, overlap_chars=600)
        self.assertEqual((chunks[0].page_start, chunks[0].page_end), (1, 3))

    def test_sections_cover_exact_text_and_continue_across_pages(self):
        text = 'Preface\n1 Introduction\nText.\n2 Results\nMore.'
        spans, current = section_spans(text, None)
        self.assertEqual(''.join(text[s['start']:s['end']] for s in spans), text)
        self.assertIsNone(spans[0]['section'])
        following, _ = section_spans('Continued result.', current)
        self.assertEqual(following[0]['section'], '2 Results')
        self.assertIsNone(section_spans('The results show an effect.', None)[0][0]['section'])

    def test_small_caps_and_unrecognized_section_reset(self):
        spans, current = section_spans('I. I NTRODUCTION\nText.', None)
        self.assertEqual(current, 'I. I NTRODUCTION')
        spans, current = section_spans('II. D ESIGN PRINCIPLES\nText.', current)
        self.assertIsNone(current)
        self.assertIsNone(spans[0]['section'])

    def test_page_exception_is_recorded_not_dropped(self):
        make_pdf(self.path, ['Text'])
        with patch('pypdf._page.PageObject.extract_text', side_effect=RuntimeError('broken page')):
            article = parse_pdf(self.path, study_id='TEST')
        self.assertEqual(len(article['pages']), 1)
        self.assertEqual(article['pages'][0]['status'], 'error')
        self.assertIn('broken page', article['pages'][0]['error'])
        self.assertTrue(article['requires_review'])

    def test_invalid_pdf_fails_explicitly(self):
        self.path.write_bytes(b'not a PDF')
        with self.assertRaises(Exception):
            parse_pdf(self.path, study_id='TEST')

    def test_encrypted_pdf_is_rejected(self):
        writer = PdfWriter()
        writer.add_blank_page(width=100, height=100)
        writer.encrypt('secret')
        writer.write(self.path)
        with self.assertRaisesRegex(ValueError, 'Encrypted'):
            parse_pdf(self.path, study_id='TEST')

    def test_cli_writes_json_and_signals_review(self):
        make_pdf(self.path, [None])
        output = Path(self.tmp.name) / 'pages.json'
        command = [sys.executable, '-m', 'slr_extraction.pdf_parser', '--input', str(self.path),
                   '--output', str(output), '--study-id', 'TEST']
        result = subprocess.run(command, capture_output=True, text=True, env=os.environ.copy())
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(json.loads(output.read_text())['pages'][0]['status'], 'empty')
        original = output.read_bytes()
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(output.read_bytes(), original)
