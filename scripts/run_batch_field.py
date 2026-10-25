"""Run one field across frozen batches; resume only never-attempted calls."""
import argparse
import fcntl
import hashlib
import json
from pathlib import Path
import shutil
from datetime import datetime, timezone

import httpx
from openai import OpenAI
from slr_data_extraction.execution.audit import Audit, write_json
from slr_data_extraction.execution.cli import code_hash
from slr_data_extraction.pipeline import ExtractionPipeline
from slr_data_extraction.definitions.result_definition import FieldExtraction
from slr_data_extraction.validation.evidence_validation import validate_field


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def consolidate(field_name, results):
    """Remove identical value/evidence objects only; retain batch provenance."""
    values, seen, provenance = [], {}, []
    for batch, result in results:
        for value in result.values:
            obj = value.model_dump()
            key = json.dumps(obj, sort_keys=True, ensure_ascii=False)
            if key not in seen:
                seen[key] = len(values)
                values.append(obj)
                provenance.append([])
            provenance[seen[key]].append(batch)
    field = FieldExtraction.model_validate({
        'field_name': field_name, 'status': 'extracted' if values else 'not_found_in_context',
        'values': values, 'notes': '\n'.join(
            f'Batch {batch}: {result.notes}' for batch, result in results if result.notes) or None})
    return field, provenance


def attempt_state(directory):
    if not directory.exists():
        return 'pending'
    status = directory / 'field-01.status.json'
    if status.exists():
        return json.loads(status.read_text())['status']
    # An interrupted request might have reached the server: never resend silently.
    return 'interrupted'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepared-run', type=Path, required=True)
    parser.add_argument('--token-check', type=Path, required=True)
    parser.add_argument('--run-dir', type=Path, required=True)
    parser.add_argument('--field', required=True)
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--batch', type=int, help='Run only this one-based batch as a partial diagnostic')
    args = parser.parse_args()
    source, target = args.prepared_run, args.run_dir
    manifest = json.loads((source / 'manifest.json').read_text())
    approval = json.loads((args.token_check / 'summary.json').read_text())
    if approval['status'] != 'passed' or approval['batch_plan_sha256'] != digest(source / 'batches.json'):
        raise ValueError('Missing token approval for this batch plan')
    if manifest['batch_plan_sha256'] != approval['batch_plan_sha256']:
        raise ValueError('Preparation manifest differs from plan')
    config = json.loads((source / 'config.json').read_text())
    article = json.loads((source / 'article.json').read_text())
    pipeline = ExtractionPipeline(source / 'schema.json', config)
    field_names = [f.name for f in pipeline.review.fields]
    if args.field not in field_names:
        raise ValueError('Unknown field')
    index = field_names.index(args.field)
    field = pipeline.review.fields[index]
    chunks, _ = pipeline.prepare(article)
    chunk_map = {c.chunk_id: c for c in chunks}
    batches = json.loads((source / 'batches.json').read_text())
    if [i for batch in batches for i in batch] != [c.chunk_id for c in chunks]:
        raise ValueError('Batch plan must cover each chunk exactly once in document order')
    items = []
    for bi, ids in enumerate(batches, 1):
        selected = [chunk_map[i] for i in ids]
        path = source / f'batch-{bi:02d}.field-{index+1:02d}.request.json'
        if approval['request_sha256'].get(path.name) != digest(path):
            raise ValueError('Request differs from token-approved request')
        request = json.loads(path.read_text())
        expected = pipeline._request(field, selected, article['pages'])
        expected.pop('response_format', None)
        expected['extra_body']['chat_template_kwargs'] = {'enable_thinking': False}
        if request != expected:
            raise ValueError('Current code/config cannot reproduce approved request')
        items.append({'field': field, 'selected': selected, 'request': request})
    if args.batch is not None and not 1 <= args.batch <= len(items):
        raise ValueError('Batch number is outside the prepared plan')
    selected_batches = [args.batch] if args.batch is not None else list(range(1, len(items) + 1))
    identity = {'selected_batches': selected_batches, 'field': args.field, 'source_sha256': code_hash(),
                'runner_sha256': digest(Path(__file__)),
                'inputs': {p.name: digest(p) for p in sorted(source.glob('*.json'))},
                'token_approval_sha256': digest(args.token_check / 'summary.json')}
    if args.resume:
        if json.loads((target / 'identity.json').read_text()) != identity:
            raise ValueError('Resume inputs or code changed; use a new run')
    else:
        target.mkdir(parents=True, exist_ok=False)
        write_json(target / 'identity.json', identity)
        shutil.copytree(source, target / 'prepared')
        shutil.copytree(args.token_check, target / 'token-check')
        shutil.copyfile(__file__, target / 'runner.py')
    # Kernel releases the lock after termination; the lock file can remain.
    with (target / '.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        results, errors = [], []
        summary = {'status': 'running', 'field': args.field, 'planned_calls': len(selected_batches),
                   'selected_batches': selected_batches, 'article_complete': args.batch is None,
                   'started_at': datetime.now(timezone.utc).isoformat(),
                   'new_calls_this_invocation': 0, 'failure_policy': 'No retries; resume pending only'}
        write_json(target / 'manifest.json', summary)
        try:
            base = config['base_url'].rstrip('/')
            with httpx.Client(timeout=30, trust_env=False) as http:
                for endpoint, name in [(base.removesuffix('/v1') + '/version', 'server-version'),
                                       (base + '/models', 'server-models')]:
                    response = http.get(endpoint)
                    response.raise_for_status()
                    value = response.json()
                    if name == 'server-version' and value['version'] != config['vllm_version']:
                        raise ValueError('Server version changed')
                    if name == 'server-models' and config['model_id'] not in [m['id'] for m in value['data']]:
                        raise ValueError('Configured model is not served')
                    write_json(target / f'{name}.json', value)
            with OpenAI(base_url=base, api_key='EMPTY', max_retries=0, timeout=300) as client:
                pipeline.client = client
                for bi in selected_batches:
                    item = items[bi - 1]
                    directory = target / f'batch-{bi:02d}'
                    state = attempt_state(directory)
                    print(f'Batch {bi}/{len(items)}: {state}', flush=True)
                    try:
                        if state == 'pending':
                            directory.mkdir()
                            write_json(directory / 'request.json', item['request'])
                            summary['new_calls_this_invocation'] += 1
                            result = pipeline.extract([item], article['pages'], Audit(directory))[0]
                        elif state == 'completed':
                            result = FieldExtraction.model_validate_json(
                                (directory / 'field-01.validated.json').read_text())
                            validate_field(result, field, item['selected'], article['pages'])
                        else:
                            raise ValueError(f'Previously {state}; preserved without retry')
                        results.append((bi, result))
                        print('  passed validation', flush=True)
                    except Exception as exc:
                        errors.append({'batch': bi, 'error': str(exc)})
                        print('  failed:', exc, flush=True)
            consolidated, provenance = consolidate(args.field, results)
            report = {'complete': not errors and args.batch is None, 'selected_batches': selected_batches, 'validated_batches': [b for b, _ in results],
                      'errors': errors, 'value_batch_provenance': provenance,
                      'field': consolidated.model_dump()}
            write_json(target / 'consolidated-review.json', report)
            # An incomplete run must never look like an article-wide absence.
            if not errors and args.batch is None:
                write_json(target / 'field-result.json', consolidated.model_dump())
            summary.update(status='completed_with_errors' if errors else 'completed',
                           passed_batches=len(results), failed_batches=len(errors))
        except BaseException as exc:
            summary.update(status='interrupted_or_failed', error=str(exc))
            raise
        finally:
            write_json(target / 'manifest.json', summary)
            print('Saved:', target)
            print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
