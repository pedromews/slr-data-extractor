"""Check every frozen batch request against vLLM; never call generation."""
import argparse
import hashlib
import json
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx
from slr_data_extraction.execution.audit import write_json


def check_requests(http, root, model_id, requests, context_limit, output):
    rows = []
    for filename, request in requests:
        if request['model'] != model_id:
            raise ValueError(f'Model mismatch in {filename}')
        kwargs = request.get('extra_body', {}).get('chat_template_kwargs', {})
        response = http.post(root + '/tokenize', json={
            'model': request['model'], 'messages': request['messages'],
            'add_generation_prompt': True, 'chat_template_kwargs': kwargs})
        write_json(output / filename.replace('.request.json', '.tokenize.json'), {
            'status_code': response.status_code, 'body': response.text})
        response.raise_for_status()
        data = response.json()
        limit = min(context_limit, data['max_model_len'])
        total = data['count'] + request['max_tokens']
        row = {'request': filename, 'input_tokens': data['count'],
               'reserved_output_tokens': request['max_tokens'], 'context_limit': limit,
               'remaining_tokens': limit - total, 'fits': total <= limit}
        rows.append(row)
        print(f"{filename}: input={data['count']}, remaining={limit-total}, fits={row['fits']}", flush=True)
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepared-run', required=True, type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    parser.add_argument('--expected-plan-sha256', required=True)
    args = parser.parse_args()
    run, output = args.prepared_run, args.output_dir
    plan_bytes = (run / 'batches.json').read_bytes()
    plan_hash = hashlib.sha256(plan_bytes).hexdigest()
    manifest = json.loads((run / 'manifest.json').read_text())
    if plan_hash != args.expected_plan_sha256 or plan_hash != manifest['batch_plan_sha256']:
        raise ValueError('Batch plan hash differs; do not change batches independently')
    config = json.loads((run / 'config.json').read_text())
    base = config['base_url'].rstrip('/')
    if urlparse(base).hostname not in {'localhost', '127.0.0.1', '::1'}:
        raise ValueError('Expected local server endpoint')
    root = base.removesuffix('/v1')
    files = sorted(run.glob('batch-*.field-*.request.json'))
    expected = {f'batch-{b:02d}.field-{f:02d}.request.json'
                for b in range(1, manifest['batch_count'] + 1)
                for f in range(1, manifest['field_count'] + 1)}
    if {p.name for p in files} != expected or len(files) != manifest['planned_calls']:
        raise ValueError('Incomplete or unexpected request matrix')
    requests = [(p.name, json.loads(p.read_text())) for p in files]
    output.mkdir(parents=True, exist_ok=False)
    summary = {'status': 'running', 'started_at': datetime.now(timezone.utc).isoformat(),
               'prepared_run': str(run.resolve()), 'batch_plan_sha256': plan_hash,
               'generation_calls_made': 0,
               'request_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in files}}
    write_json(output / 'summary.json', summary)
    try:
        with httpx.Client(timeout=60, trust_env=False) as http:
            for endpoint, filename in [(root + '/version', 'server-version.json'),
                                       (base + '/models', 'server-models.json')]:
                response = http.get(endpoint)
                response.raise_for_status()
                write_json(output / filename, response.json())
            version = json.loads((output / 'server-version.json').read_text())
            models = json.loads((output / 'server-models.json').read_text())
            if version['version'] != config['vllm_version']:
                raise ValueError('Unexpected vLLM version')
            if config['model_id'] not in [m['id'] for m in models['data']]:
                raise ValueError('Configured model is not served')
            rows = check_requests(http, root, config['model_id'], requests,
                                  config['max_model_len'], output)
        write_json(output / 'token-counts.json', rows)
        summary.update(status='passed' if all(r['fits'] for r in rows) else 'overflow',
                       checked_requests=len(rows),
                       overflow_requests=sum(not r['fits'] for r in rows),
                       minimum_remaining_tokens=min(r['remaining_tokens'] for r in rows))
    except Exception as exc:
        summary.update(status='failed', error=str(exc))
        raise
    finally:
        write_json(output / 'summary.json', summary)
        print('Saved:', output)
        print('Status:', summary['status'])
    if summary['status'] != 'passed':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
