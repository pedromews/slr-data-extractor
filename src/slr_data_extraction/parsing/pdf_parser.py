"""PDF ingestion only: no chunking, retrieval or model calls."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import logging
import re
import sys
import time
from pathlib import Path

import pypdf
from pypdf import PdfReader

PARSER_VERSION = "2"
# Deliberately conservative: an entire line must be a recognizable heading.
HEADING = re.compile(
    r"^(?:(?:\d+(?:\.\d+)*|[IVX]+)[.)]?\s+)?"
    r"(?:abstract|introduction|background|related work|methodology|methods|"
    r"experimental setup|results|discussion|limitations|threats to validity|"
    r"conclusions?|conclusions? and future work|references)\s*$", re.I
)


def section_spans(text: str, current: str | None) -> tuple[list[dict], str | None]:
    """Offsets index exact extracted page text; sections are heuristic labels."""
    spans = []
    start = 0
    offset = 0
    lines = text.splitlines(keepends=True)
    index = 0
    while index < len(lines):
        line = lines[index]
        candidate = line.strip()
        numbered = bool(re.match(r'^(?:[IVX]+\.|\d{1,2}(?:\.\d{1,2})*[.)]?)\s+[A-Z]', candidate))
        # Avoid treating numbered citations or prose sentences as headings.
        numbered = numbered and len(candidate) <= 150 and not re.search(r'[,;“”"]', candidate)
        subsection = bool(re.match(r'^[A-Z]\.\s+[A-Z]', candidate))
        parent = current.split(' > ')[0] if current else None
        subsection = (subsection and parent is not None and
                      'REFERENCES' not in parent.upper() and
                      len(candidate) <= 150 and not re.search(r'[,;“”"]', candidate))
        recognized = bool(HEADING.fullmatch(candidate)) or numbered or subsection
        if recognized:
            # Join wrapped uppercase main headings; text offsets remain unchanged.
            consumed = len(line)
            if numbered and candidate.isupper():
                while index + 1 < len(lines):
                    continuation = lines[index + 1].strip()
                    if (not continuation or not continuation.isupper() or
                        re.match(r'^(?:[IVX]+\.|[A-Z]\.|\d|TABLE|FIG)', continuation) or
                        len(candidate) + len(continuation) > 200):
                        break
                    index += 1
                    consumed += len(lines[index])
                    candidate += ' ' + continuation
            if offset > start:
                spans.append({'start': start, 'end': offset, 'section': current})
            start = offset
            current = parent + ' > ' + candidate if subsection and not numbered else candidate
            offset += consumed
        else:
            offset += len(line)
        index += 1
    if text:
        spans.append({"start": start, "end": len(text), "section": current})
    return spans, current


class _Warnings(logging.Handler):
    def __init__(self):
        super().__init__(logging.WARNING)
        self.messages = []

    def emit(self, record):
        self.messages.append(record.getMessage())


def parse_pdf(path: str | Path, *, study_id: str, title: str | None = None) -> dict:
    if not study_id.strip():
        raise ValueError("study_id must not be blank")
    path = Path(path)
    data = path.read_bytes()
    started = time.perf_counter()
    captured = _Warnings()
    logger = logging.getLogger("pypdf")
    logger.addHandler(captured)
    try:
        reader = PdfReader(io.BytesIO(data), strict=False)
        if reader.is_encrypted:
            raise ValueError("Encrypted PDF: supply an unencrypted source PDF")
        if not reader.pages:
            raise ValueError("PDF has no pages")
        pages = []
        current = None
        for number, page in enumerate(reader.pages, 1):
            try:
                text = page.extract_text(extraction_mode="plain") or ""
                status = "ok" if text.strip() else "empty"
                error = None
            except Exception as exc:
                text, status = "", "error"
                error = f"{type(exc).__name__}: {exc}"
            spans, current = section_spans(text, current)
            pages.append({"page": number, "text": text, "status": status,
                          "error": error, "sections": spans})
        metadata = reader.metadata
        resolved_title = title or (metadata.title if metadata else None) or path.stem
        return {
            "study_id": study_id, "title": resolved_title, "pages": pages,
            "source": {"filename": path.name, "sha256": hashlib.sha256(data).hexdigest()},
            "parser": {"name": "pypdf", "version": pypdf.__version__,
                       "implementation_version": PARSER_VERSION, "extraction_mode": "plain",
                       "section_method": "numbered-heading-lines-v2",
                       "page_numbering": "physical PDF pages, one-based",
                       "elapsed_seconds": time.perf_counter() - started,
                       "warnings": captured.messages},
            "requires_review": bool(captured.messages) or any(p["status"] != "ok" for p in pages),
        }
    finally:
        logger.removeHandler(captured)


def main() -> int:
    parser = argparse.ArgumentParser(description="Convert one PDF to auditable page JSON (no OCR).")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--study-id", required=True)
    parser.add_argument("--title")
    args = parser.parse_args()
    try:
        result = parse_pdf(args.input, study_id=args.study_id, title=args.title)
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("x", encoding="utf-8") as stream:
            json.dump(result, stream, ensure_ascii=False, indent=2)
    except Exception as exc:
        print(f"PDF conversion failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(f"Saved {len(result['pages'])} pages to {output}")
    if result["requires_review"]:
        print("Review required: empty/failed pages or parser warnings; see JSON.", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
