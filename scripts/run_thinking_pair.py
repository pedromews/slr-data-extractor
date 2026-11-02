"""Four-call frozen P8 diagnostic; never retries or changes the extraction prompt."""
import argparse
import copy
import hashlib
import json
import re
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
from openai import OpenAI
from check_batch_tokens import check_requests
from slr_data_extraction.execution.audit import write_json
from slr_data_extraction.chunking.evidence_segments import resolve_selection


def separate_content(message, thinking):
    content = message.get('content') or ''
    reasoning = message.get('reasoning_content') or message.get('reasoning') or ''
    if '</think>' in content:
        if content.count('</think>') != 1:
            raise ValueError('Ambiguous reasoning boundary')
        prefix, content = content.split('</think>', 1)
        reasoning = prefix.removeprefix('<think>').strip()
    elif '<think>' in content:
        raise ValueError('Unfinished reasoning block')
    if thinking and not reasoning.strip():
        raise ValueError('Thinking requested but no reasoning captured')
    return reasoning, content.strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepared-run', required=True, type=Path)
    parser.add_argument('--run-dir', required=True, type=Path)
    parser.add_argument('--max-tokens', type=int, default=4096)
    args = parser.parse_args()
    if args.max_tokens < 1:
        parser.error('--max-tokens must be positive')
    source, target = args.prepared_run, args.run_dir
    config = json.loads((source / 'config.json').read_text())
    schema = json.loads((source / 'schema.json').read_text())
    field = 'reported_impacts'
    index = next(i for i, f in enumerate(schema['fields'], 1) if f['name'] == field)
    catalog = json.loads((source / 'evidence-catalog.json').read_text())
    base = config['base_url'].rstrip('/')
    if base != 'http://127.0.0.1:8000/v1' or config['model_id'] != 'Qwen/Qwen3-14B-AWQ':
        raise ValueError('Expected local Qwen3-14B-AWQ pilot server')
    target.mkdir(parents=True, exist_ok=False)
    for name in ('config.json', 'schema.json', 'manifest.json', 'batches.json', 'evidence-catalog.json'):
        shutil.copyfile(source / name, target / ('source-' + name))
    shutil.copyfile(__file__, target / 'diagnostic-script.py')
    jobs = []
    hashes = {}
    for batch in (3, 18):
        path = source / f'batch-{batch:02d}.field-{index:02d}.request.json'
        original = json.loads(path.read_text())
        if 'response_format' in original or original['model'] != config['model_id']:
            raise ValueError('Expected frozen unconstrained Qwen request')
        hashes[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
        shutil.copyfile(path, target / ('original-' + path.name))
        passages = original['messages'][1]['content'].split('\nPassages:\n', 1)[1]
        ids = re.findall(r'^\[([^;\n]+); page ', passages, re.MULTILINE)
        if not ids or any(i not in catalog for i in ids):
            raise ValueError('Unknown evidence IDs')
        for thinking in (False, True):
            name = f'batch-{batch:02d}-thinking-{str(thinking).lower()}'
            req = copy.deepcopy(original)
            req['max_tokens'] = args.max_tokens
            req['extra_body']['chat_template_kwargs']['enable_thinking'] = thinking
            write_json(target / (name + '.request.json'), req)
            jobs.append((name, req, thinking, {i: catalog[i] for i in ids}))
    manifest = {'status': 'checking_tokens', 'started_at': datetime.now(timezone.utc).isoformat(),
                'source_run': str(source.resolve()), 'original_request_sha256': hashes,
                'purpose': 'Development thinking comparison; frozen prompt/schema; two batches',
                'max_output_tokens_both_arms': args.max_tokens, 'planned_calls': 4,
                'generation_calls_attempted': 0, 'failure_policy': 'No retries; preserve each failure'}
    write_json(target / 'manifest.json', manifest)
    try:
        with httpx.Client(timeout=60, trust_env=False) as http:
            version = http.get(base.removesuffix('/v1') + '/version'); version.raise_for_status()
            models = http.get(base + '/models'); models.raise_for_status()
            write_json(target / 'server-version.json', version.json())
            write_json(target / 'server-models.json', models.json())
            if version.json()['version'] != config['vllm_version'] or config['model_id'] not in [m['id'] for m in models.json()['data']]:
                raise ValueError('Unexpected server')
            rows = check_requests(http, base.removesuffix('/v1'), config['model_id'],
                                  [(n + '.request.json', r) for n, r, _, _ in jobs],
                                  config['max_model_len'], target)
            write_json(target / 'token-counts.json', rows)
            if not all(r['fits'] for r in rows):
                raise ValueError('Context overflow; no generation performed')
        results = []
        with OpenAI(base_url=base, api_key='EMPTY', max_retries=0, timeout=600) as client:
            for name, req, thinking, selected in jobs:
                started = time.perf_counter()
                status = {'name': name, 'thinking': thinking, 'status': 'running'}
                manifest['generation_calls_attempted'] += 1
                write_json(target / 'manifest.json', manifest)
                try:
                    raw = client.chat.completions.with_raw_response.create(**req)
                    (target / (name + '.raw.json')).write_text(raw.text)
                    response = json.loads(raw.text)
                    choice = response['choices'][0]
                    status.update(finish_reason=choice['finish_reason'], usage=response.get('usage'))
                    if choice['finish_reason'] != 'stop' or choice['message'].get('refusal'):
                        raise ValueError('Incomplete/refused generation: ' + str(choice['finish_reason']))
                    reasoning, final = separate_content(choice['message'], thinking)
                    (target / (name + '.reasoning.txt')).write_text(reasoning)
                    (target / (name + '.final.txt')).write_text(final)
                    result = resolve_selection(final, selected)
                    if result.field_name != field:
                        raise ValueError('Unexpected field')
                    write_json(target / (name + '.result.json'), result.model_dump())
                    status.update(status='completed', value_count=len(result.values), reasoning_chars=len(reasoning))
                except Exception as exc:
                    status.update(status='failed', error=str(exc))
                status['elapsed_seconds'] = time.perf_counter() - started
                write_json(target / (name + '.status.json'), status)
                results.append(status)
                print(name, status['status'], status.get('error', ''), flush=True)
        write_json(target / 'summary.json', results)
        manifest['status'] = 'completed' if all(r['status'] == 'completed' for r in results) else 'completed_with_errors'
    except Exception as exc:
        manifest.update(status='failed', error=str(exc))
        raise
    finally:
        write_json(target / 'manifest.json', manifest)
        print('Saved:', target)


if __name__ == '__main__':
    main()
