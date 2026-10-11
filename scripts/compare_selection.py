"""Compare lexical and BM25 selection offline using a saved run; no model calls."""
import argparse
import json
from pathlib import Path
from slr_data_extraction.pipeline import ExtractionPipeline
from slr_data_extraction.chunking.chunk_selection import bm25_scores, rank_chunks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-run', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    config = json.loads((args.source_run / 'config.json').read_text())
    article = json.loads((args.source_run / 'article.json').read_text())
    config['selection_method'] = 'lexical'
    baseline = ExtractionPipeline(args.source_run / 'schema.json', config)
    chunks, old = baseline.prepare(article)
    variant = ExtractionPipeline(args.source_run / 'schema.json', {**config, 'selection_method': 'bm25'})
    _, new = variant.prepare(article)
    rows = []
    for before, after in zip(old, new):
        scores = bm25_scores(chunks, after['field'].retrieval_terms)
        rows.append({'field': before['field'].name,
                     'lexical': [c.chunk_id for c in before['selected']],
                     'bm25': [c.chunk_id for c in after['selected']],
                     'bm25_ranking': [{'chunk': c.chunk_id, 'score': scores[chunks.index(c)]}
                                      for c in rank_chunks(chunks, after['field'].retrieval_terms,
                                                           len(chunks), method='bm25')],
                     'lexical_request_chars': len(json.dumps(before['request'])),
                     'bm25_request_chars': len(json.dumps(after['request']))})
    with args.output.open('x') as stream:
        json.dump(rows, stream, indent=2)
        stream.write('\n')
    print('Saved:', args.output)


if __name__ == '__main__':
    main()
