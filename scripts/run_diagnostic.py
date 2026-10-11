"""Replay a prepared run without constrained generation or Qwen3 thinking."""
import argparse
import json
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
from openai import OpenAI

from slr_data_extraction.execution.audit import Audit, write_json
from slr_data_extraction.execution.cli import code_hash
from slr_data_extraction.pipeline import ExtractionPipeline


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepared-run', required=True, type=Path)
    parser.add_argument('--run-dir', required=True, type=Path)
    args = parser.parse_args()
    source, target = args.prepared_run, args.run_dir
    original = json.loads((source / 'manifest.json').read_text())
    if original['status'] != 'prepared' or original['source_sha256'] != code_hash():
        raise ValueError('Prepare a new run with the current code first')
    config = json.loads((source / 'config.json').read_text())
    article = json.loads((source / 'article.json').read_text())
    pipeline = ExtractionPipeline(source / 'schema.json', config)
    if original['prompt_version'] != pipeline.prompt_version:
        raise ValueError('Prompt version differs from preparation')
    _, prepared = pipeline.prepare(article)
    for index, item in enumerate(prepared):
        saved = json.loads((source / f'field-{index + 1:02d}.request.json').read_text())
        if item['request'] != saved:
            raise ValueError('Request differs from preparation')
        item['request'].pop('response_format', None)
        item['request'].setdefault('extra_body', {})['chat_template_kwargs'] = {
            'enable_thinking': False}
    shutil.copytree(source, target)  # Refuse to overwrite an existing run.
    shutil.copyfile(__file__, target / 'diagnostic-script.py')
    for index, item in enumerate(prepared):
        write_json(target / f'field-{index + 1:02d}.request.json', item['request'])
    manifest = {**original, 'status': 'running', 'source_run': str(source.resolve()),
                'started_at': datetime.now(timezone.utc).isoformat(),
                'changes': {'response_format': 'removed', 'enable_thinking': False,
                            'failure_policy': 'Continue after field failures; no retries'}}
    write_json(target / 'manifest.json', manifest)
    started = time.perf_counter()
    try:
        base = config['base_url'].rstrip('/')
        root = base.removesuffix('/v1')
        with httpx.Client(timeout=30, trust_env=False) as http:
            for endpoint, filename in [(root + '/version', 'server-version.json'),
                                       (base + '/models', 'server-models.json')]:
                response = http.get(endpoint)
                response.raise_for_status()
                write_json(target / filename, response.json())
            version = json.loads((target / 'server-version.json').read_text())
            models = json.loads((target / 'server-models.json').read_text())
            if version['version'] != config['vllm_version']:
                raise ValueError('Unexpected vLLM version')
            if config['model_id'] not in [m['id'] for m in models['data']]:
                raise ValueError('Configured model is not served')
            for index, item in enumerate(prepared):
                response = http.post(root + '/tokenize', json={
                    'model': config['model_id'], 'messages': item['request']['messages'],
                    'add_generation_prompt': True,
                    'chat_template_kwargs': {'enable_thinking': False}})
                write_json(target / f'field-{index + 1:02d}.tokenize.json', {
                    'status_code': response.status_code, 'body': response.text})
                response.raise_for_status()
                tokens = response.json()
                print(item['field'].name, 'input tokens:', tokens['count'], flush=True)
                if tokens['count'] + config['max_tokens'] > min(
                        config['max_model_len'], tokens['max_model_len']):
                    raise ValueError('Context overflow; no truncation applied')
        fields, errors = [], []
        with OpenAI(base_url=base, api_key='EMPTY', max_retries=0, timeout=300) as client:
            pipeline.client = client
            for index, item in enumerate(prepared):
                class IndexedAudit:
                    def field(self, unused_index, name):
                        return Audit(target).field(index, name)
                print(f"Extracting {index + 1}/{len(prepared)}: {item['field'].name}", flush=True)
                try:
                    fields.extend(pipeline.extract([item], article['pages'], IndexedAudit()))
                    print('  passed validation', flush=True)
                except Exception as exc:
                    errors.append({'field': item['field'].name, 'error': str(exc),
                                   'error_type': type(exc).__name__})
                    print('  failed:', exc, flush=True)
        write_json(target / 'errors.json', errors)
        write_json(target / 'validated-fields.json', [f.model_dump() for f in fields])
        if not errors:
            write_json(target / 'result.json', pipeline.result(article, fields).model_dump())
        manifest.update(status='completed_with_errors' if errors else 'completed',
                        passed_fields=len(fields), failed_fields=len(errors))
    except Exception as exc:
        manifest.update(status='failed', error=str(exc), error_type=type(exc).__name__)
        raise
    finally:
        manifest['elapsed_seconds'] = time.perf_counter() - started
        write_json(target / 'manifest.json', manifest)
        print('Saved:', target, flush=True)
        print(json.dumps(manifest, indent=2), flush=True)


if __name__ == '__main__':
    main()
