"""Prepare fixed full-article batches from a saved run. Never generates output."""
import argparse
from dataclasses import asdict
import hashlib
import json
import math
from pathlib import Path
import shutil

from slr_data_extraction.chunking.batching import BATCHING_VERSION, message_chars, plan_batches
from slr_data_extraction.chunking.evidence_segments import build_catalog, SEGMENT_VERSION
from slr_data_extraction.execution.audit import write_json
from slr_data_extraction.execution.cli import code_hash
from slr_data_extraction.pipeline import ExtractionPipeline


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-run', required=True, type=Path)
    parser.add_argument('--run-dir', required=True, type=Path)
    parser.add_argument('--max-message-chars', type=int, default=14000)
    parser.add_argument('--batch-plan', type=Path, help='Reuse frozen chunk IDs; token verification still required')
    parser.add_argument('--schema', type=Path, help='Override the saved review schema explicitly')
    parser.add_argument('--include-retrieval-terms', action='store_true',
                        help='Include retrieval terms in the prompt for a controlled comparison')
    parser.add_argument('--config', type=Path, help='Use an explicit model configuration')
    args = parser.parse_args()
    source, target = args.source_run, args.run_dir
    article = json.loads((source / 'article.json').read_text())
    config_path = args.config or source / 'config.json'
    config = json.loads(config_path.read_text())
    if args.include_retrieval_terms:
        config['include_retrieval_terms_in_prompt'] = True
    if config.get('evidence_mode') != 'segment_ids':
        raise ValueError('Use a source run configured for segment_ids')
    schema_path = args.schema or source / 'schema.json'
    pipeline = ExtractionPipeline(schema_path, config)
    chunks, _ = pipeline.prepare(article)
    saved_chunks = json.loads((source / 'chunks.json').read_text())
    if json.loads(json.dumps([asdict(c) for c in chunks])) != saved_chunks:
        raise ValueError('Chunks differ from source run; investigate before comparison')

    def request(field, selected):
        result = pipeline._request(field, selected, article['pages'])
        result.pop('response_format', None)
        result['extra_body']['chat_template_kwargs'] = {'enable_thinking': False}
        return result

    if args.batch_plan:
        frozen = json.loads(args.batch_plan.read_text())
        if (not isinstance(frozen, list) or not frozen or
                any(not isinstance(batch, list) or not batch for batch in frozen) or
                [i for batch in frozen for i in batch] != [c.chunk_id for c in chunks]):
            raise ValueError('Frozen plan must cover all chunks once in document order')
        by_id = {c.chunk_id: c for c in chunks}
        batches = [[by_id[i] for i in batch] for batch in frozen]
    else:
        batches = plan_batches(chunks, request, pipeline.review.fields,
                               max_message_chars=args.max_message_chars)
    ids = [[c.chunk_id for c in batch] for batch in batches]
    assert [i for batch in ids for i in batch] == [c.chunk_id for c in chunks]
    target.mkdir(parents=True, exist_ok=False)
    for filename in ['article.json', 'input.pdf']:
        if (source / filename).exists():
            shutil.copyfile(source / filename, target / filename)
    shutil.copyfile(schema_path, target / 'schema.json')
    shutil.copyfile(__file__, target / 'preparation-script.py')
    package = Path(__file__).resolve().parents[1] / 'src/slr_data_extraction'
    for path in package.rglob('*.py'):
        dest = target / 'source' / path.relative_to(package)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, dest)
    write_json(target / 'config.json', config)
    write_json(target / 'chunks.json', saved_chunks)
    write_json(target / 'evidence-catalog.json', build_catalog(chunks))
    write_json(target / 'batches.json', ids)
    rows = []
    for bi, batch in enumerate(batches, 1):
        for fi, field in enumerate(pipeline.review.fields, 1):
            req = request(field, batch)
            name = f'batch-{bi:02d}.field-{fi:02d}.request.json'
            write_json(target / name, req)
            chars = message_chars(req)
            rows.append({'batch': bi, 'field': field.name, 'request': name,
                         'message_chars': chars,
                         'rough_input_tokens_chars_div_4': math.ceil(chars / 4),
                         'rough_input_tokens_chars_div_3': math.ceil(chars / 3)})
    write_json(target / 'request-estimates.json', rows)
    manifest = {
        'status': 'prepared_pending_tokenization', 'source_run': str(source.resolve()),
        'config_source': str(config_path.resolve()),
        'schema_source': str(schema_path.resolve()),
        'schema_sha256': hashlib.sha256((target / 'schema.json').read_bytes()).hexdigest(),
        'source_sha256': code_hash(), 'prompt_version': pipeline.prompt_version,
        'batching_version': BATCHING_VERSION, 'segment_version': SEGMENT_VERSION,
        'context_policy': 'all chunks in fixed document-order batches; no retrieval filtering',
        'max_message_chars': None if args.batch_plan else args.max_message_chars,
        'reused_batch_plan': str(args.batch_plan.resolve()) if args.batch_plan else None,
        'batch_plan_sha256': hashlib.sha256((target / 'batches.json').read_bytes()).hexdigest(),
        'source_chunks_sha256': hashlib.sha256((source / 'chunks.json').read_bytes()).hexdigest(),
        'all_chunks_covered_once': True, 'chunk_count': len(chunks),
        'batch_count': len(batches), 'field_count': len(pipeline.review.fields),
        'planned_calls': len(rows), 'max_output_tokens_per_call': config['max_tokens'],
        'generation_calls_made': 0, 'token_budget_verified': False,
        'notes': 'Character ratios are rough estimates, not bounds; tokenizer and chat-template overhead are unverified. No inference or consolidation implemented.'}
    write_json(target / 'manifest.json', manifest)
    report = ['# P1 full-article batch preparation', '',
              f'{len(chunks)} chunks; {len(batches)} batches; {len(rows)} planned calls. No inference.', '',
              'All chunks, including References, are retained once in the batch plan. Original chunk overlap remains.', '',
              'Token estimates use message characters / 4 and / 3. They are not guaranteed bounds and exclude chat-template overhead. Verify every request with the served tokenizer before inference.', '',
              '| Batch | Chunks | Message characters across fields | Rough input token estimates across fields |',
              '| --- | --- | --- | --- |']
    for bi, batch_ids in enumerate(ids, 1):
        batch_rows = [x for x in rows if x['batch'] == bi]
        report.append(f"| {bi} | {', '.join(batch_ids)} | {min(x['message_chars'] for x in batch_rows)}–{max(x['message_chars'] for x in batch_rows)} | {min(x['rough_input_tokens_chars_div_4'] for x in batch_rows)}–{max(x['rough_input_tokens_chars_div_3'] for x in batch_rows)} |")
    report += ['', f"Output reservation: {config['max_tokens']} tokens per call; model context: {config['max_model_len']}.",
               '', 'Freeze batches.json for comparisons. Do not repack independently by model. If any model fails the token check, revise the common plan before starting any model runs.',
               '', 'Full chunk coverage does not guarantee semantic completeness; sentences can cross chunk boundaries and relevant context can span batches. Aggregation and semantic review remain pending.']
    (target / 'preparation.md').write_text('\n'.join(report) + '\n')
    print(json.dumps(manifest, indent=2))


if __name__ == '__main__':
    main()
