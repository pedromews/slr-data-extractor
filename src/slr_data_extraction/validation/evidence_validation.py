"""Structural and source-evidence validation, independent of the model client."""
import re


def normalize(text):
    return " ".join(text.split())


def validate_evidence(evidence, selected, pages):
    chunks = {c.chunk_id: c for c in selected}
    page_map = {p['page']: p for p in pages}
    chunk = chunks.get(evidence.chunk_id)
    if chunk is None:
        raise ValueError('Unknown evidence chunk')
    quote = normalize(evidence.quote)
    if not quote:
        raise ValueError('Whitespace-only evidence')
    # Match exact case; normalize only whitespace. Use local offsets for
    # actual page attribution, rather than trusting the chunk page range.
    matches = []
    for match in re.finditer(re.escape(quote), chunk.text):
        source_pages = [page for start, end, page in chunk.page_spans
                        if start < match.end() and end > match.start()]
        if source_pages:
            matches.append((source_pages[0], source_pages[-1]))
    if (evidence.page_start, evidence.page_end) not in matches:
        raise ValueError('Evidence quote/page range does not match the source chunk')
    if evidence.section is not None:
        relevant = []
        for number in range(evidence.page_start, evidence.page_end + 1):
            page = page_map[number]
            relevant.extend(page['text'][s['start']:s['end']]
                            for s in page.get('sections', [])
                            if s['section'] == evidence.section)
        if quote not in normalize(' '.join(relevant)):
            raise ValueError('Evidence section is not supported by parser annotations')


def validate_field(result, field, selected, pages):
    if result.field_name != field.name:
        raise ValueError('Returned field_name differs from requested field')
    for value in result.values:
        for evidence in value.evidence:
            validate_evidence(evidence, selected, pages)
    return result
