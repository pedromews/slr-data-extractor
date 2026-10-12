"""P1 diagnostic: replay one request with two manually selected evidence segments."""
import argparse
import hashlib
import json
import shutil
import time
from pathlib import Path
from datetime import datetime, timezone

import httpx
from openai import OpenAI
from slr_data_extraction.execution.audit import write_json
from slr_data_extraction.chunking.evidence_segments import resolve_selection


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepared-run', type=Path, required=True)
    parser.add_argument('--run-dir', type=Path, required=True)
    parser.add_argument('--prepare-only', action='store_true')
    args = parser.parse_args()
    source, target = args.prepared_run, args.run_dir
    schema = json.loads((source / 'schema.json').read_text())
    index = next(i for i, f in enumerate(schema['fields'], 1) if f['name'] == 'reported_impacts')
    request_path = source / f'batch-01.field-{index:02d}.request.json'
    request = json.loads(request_path.read_text())
    catalog = json.loads((source / 'evidence-catalog.json').read_text())
    ids = ['chunk-0002-e006', 'chunk-0002-e007']
    selected = {key: catalog[key] for key in ids}
    passages = [f'[{key}; page {entry["page_start"]}; section: {json.dumps(entry["section"])}] {entry["quote"]}'
                for key, entry in selected.items()]
    prefix, original_passages = request['messages'][1]['content'].split('\nPassages:\n', 1)
    if not all(p in original_passages for p in passages):
        raise ValueError('Selected passages must occur unchanged in the original request')
    request['messages'][1]['content'] = prefix + '\nPassages:\n' + '\n\n'.join(passages)
    config = json.loads((source / 'config.json').read_text())
    target.mkdir(parents=True, exist_ok=False)
    for name in ['config.json', 'schema.json', 'manifest.json']:
        shutil.copyfile(source / name, target / ('source-' + name))
    shutil.copyfile(__file__, target / 'diagnostic-script.py')
    shutil.copyfile(request_path, target / 'original.request.json')
    write_json(target / 'request.json', request)
    write_json(target / 'evidence-catalog.json', selected)
    manifest = {'status': 'prepared', 'started_at': datetime.now(timezone.utc).isoformat(),
                'purpose': 'Manually selected P1 context diagnostic; not an end-to-end evaluation',
                'source_run': str(source.resolve()), 'evidence_ids': ids,
                'changes': 'Only passages reduced; original IDs and text preserved',
                'original_request_sha256': hashlib.sha256(request_path.read_bytes()).hexdigest(),
                'request_sha256': hashlib.sha256((target / 'request.json').read_bytes()).hexdigest(),
                'generation_calls_made': 0}
    write_json(target / 'manifest.json', manifest)
    if args.prepare_only:
        print('Prepared:', target)
        return
    started = time.perf_counter()
    try:
        base = config['base_url'].rstrip('/')
        if base != 'http://127.0.0.1:8000/v1':
            raise ValueError('Expected the pilot local endpoint')
        with httpx.Client(timeout=60, trust_env=False) as http:
            for endpoint, name in [('/version', 'server-version'), ('/v1/models', 'server-models')]:
                response = http.get(base.removesuffix('/v1') + endpoint)
                response.raise_for_status()
                write_json(target / (name + '.json'), response.json())
            version = json.loads((target / 'server-version.json').read_text())
            models = json.loads((target / 'server-models.json').read_text())
            if version['version'] != config['vllm_version'] or request['model'] not in [m['id'] for m in models['data']]:
                raise ValueError('Unexpected model or vLLM version')
            response = http.post(base.removesuffix('/v1') + '/tokenize', json={
                'model': request['model'], 'messages': request['messages'],
                'add_generation_prompt': True,
                'chat_template_kwargs': request['extra_body']['chat_template_kwargs']})
            response.raise_for_status()
            tokens = response.json()
            write_json(target / 'tokenize.json', tokens)
            if tokens['count'] + request['max_tokens'] > min(config['max_model_len'], tokens['max_model_len']):
                raise ValueError('Context overflow')
        with OpenAI(base_url=base, api_key='EMPTY', max_retries=0, timeout=300) as client:
            manifest['generation_calls_made'] = 1
            manifest['status'] = 'running'
            write_json(target / 'manifest.json', manifest)
            raw = client.chat.completions.with_raw_response.create(**request)
            (target / 'raw.txt').write_text(raw.text)
            choice = raw.parse().choices[0]
        if choice.finish_reason != 'stop' or choice.message.refusal:
            raise ValueError(f'Incomplete/refused generation: {choice.finish_reason}')
        result = resolve_selection(choice.message.content or '', selected)
        if result.field_name != 'reported_impacts':
            raise ValueError('Unexpected field')
        write_json(target / 'field-result.json', result.model_dump())
        print(json.dumps(result.model_dump(), indent=2, ensure_ascii=False))
        manifest['status'] = 'completed'
    except Exception as exc:
        manifest.update(status='failed', error=str(exc))
        raise
    finally:
        manifest['elapsed_seconds'] = time.perf_counter() - started
        write_json(target / 'manifest.json', manifest)
        print('Saved:', target)


if __name__ == '__main__':
    main()
