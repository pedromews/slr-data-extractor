"""Run one exploratory Qwen2.5 pilot with local Ollama, independently of vLLM."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import time

import httpx

from .audit import Audit, write_json
from .cli import code_hash, save_preparation
from ..pipeline import ExtractionPipeline, PROMPT_VERSION
from ..definitions.result_definition import FieldExtraction
from ..validation.evidence_validation import validate_field


def native_request(request, config):
    """Render the Qwen2.5 ChatML template explicitly to bound the entire input.

    Qwen2.5 uses byte-level BPE: UTF-8 bytes conservatively bound token count.
    Raw mode avoids an uncounted server-side template or silent chat truncation.
    This adapter deliberately supports only Qwen2.5, not arbitrary templates.
    """
    if not config['model_id'].startswith('qwen2.5:'):
        raise ValueError('This exploratory adapter supports only Qwen2.5')
    prompt = ''.join('<|im_start|>' + m['role'] + '\n' + m['content'] +
                     '<|im_end|>\n' for m in request['messages'])
    prompt += '<|im_start|>assistant\n'
    bound = len(prompt.encode('utf-8')) + 32
    if bound + config['max_tokens'] > config['max_model_len']:
        raise ValueError('Conservative context bound exceeded; refusing truncation')
    return {
        'model': config['model_id'], 'prompt': prompt, 'raw': True,
        'stream': False, 'keep_alive': '10m',
        'format': request['response_format']['json_schema']['schema'],
        'options': {
            'num_ctx': config['max_model_len'], 'num_predict': config['max_tokens'],
            'temperature': config['temperature'], 'seed': config['seed'],
            'top_p': config['top_p'], 'top_k': config['sampling_top_k'],
            'min_p': config['min_p'], 'repeat_penalty': config['repetition_penalty'],
            'frequency_penalty': config['frequency_penalty'],
            'presence_penalty': config['presence_penalty'],
            'stop': ['<|im_end|>', '<|endoftext|>'],
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True)
    parser.add_argument('--schema', default='config/gender_and_beyond_schema.json')
    parser.add_argument('--config', default='config/pilot-ollama.json')
    parser.add_argument('--run-dir', required=True)
    args = parser.parse_args()
    directory = Path(args.run_dir)
    directory.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    manifest = dict(status='running', backend='ollama', purpose='exploratory_local_pilot',
                    started_at=datetime.now(timezone.utc).isoformat(),
                    python=platform.python_version(), platform=platform.platform(),
                    source_sha256=code_hash(), prompt_version=PROMPT_VERSION,
                    context_check='UTF-8 byte upper bound for explicit Qwen2.5 ChatML',
                    comparison_note='Quantized Metal execution; not the PCAD BF16 experiment')
    write_json(directory / 'manifest.json', manifest)
    try:
        config = json.loads(Path(args.config).read_text())
        if config['base_url'] != 'http://127.0.0.1:11434':
            raise ValueError('Local pilot requires http://127.0.0.1:11434')
        article_bytes = Path(args.input).read_bytes()
        article = json.loads(article_bytes)
        manifest['input_sha256'] = hashlib.sha256(article_bytes).hexdigest()
        pipeline = ExtractionPipeline(args.schema, config)
        for name, obj in [('config', config), ('article', article), ('schema', pipeline.schema)]:
            write_json(directory / (name + '.json'), obj)
        _, prepared = save_preparation(directory, pipeline, article)
        requests = [native_request(item['request'], config) for item in prepared]
        for i, body in enumerate(requests):
            write_json(directory / f'field-{i+1:02d}.ollama-request.json', body)
        fields, errors = [], []
        with httpx.Client(base_url=config['base_url'], timeout=1800, trust_env=False) as client:
            for endpoint, name in [('/api/version', 'server-version'), ('/api/tags', 'server-models')]:
                response = client.get(endpoint)
                response.raise_for_status()
                write_json(directory / (name + '.json'), response.json())
            models = response.json()['models']
            model = next(m for m in models if m['name'] == config['model_id'])
            manifest['model_digest'] = model['digest']
            response = client.post('/api/show', json={'model': config['model_id']})
            response.raise_for_status()
            info = response.json()
            write_json(directory / 'model-info.json', info)
            if info['details']['family'] != 'qwen2':
                raise ValueError('Unexpected model family')
            if info['model_info']['qwen2.context_length'] < config['max_model_len']:
                raise ValueError('Configured context exceeds model capability')
            audit = Audit(directory)
            for i, (item, body) in enumerate(zip(prepared, requests)):
                print(f"Extracting {i+1}/{len(prepared)}: {item['field'].name}", flush=True)
                try:
                    with audit.field(i, item['field'].name) as record:
                        response = client.post('/api/generate', json=body)
                        record.raw(response.text)
                        response.raise_for_status()
                        output = response.json()
                        if not output.get('done') or output.get('done_reason') != 'stop':
                            raise ValueError('Incomplete generation: ' + str(output.get('done_reason')))
                        if output.get('prompt_eval_count', 0) + config['max_tokens'] > config['max_model_len']:
                            raise ValueError('Reported token budget exceeds configured context')
                        result = FieldExtraction.model_validate_json(output['response'])
                        validate_field(result, item['field'], item['selected'], article['pages'])
                        record.validated(result.model_dump())
                        fields.append(result)
                except (ValueError, httpx.HTTPError) as exc:
                    errors.append({'field': item['field'].name, 'error': str(exc)})
                    print(f"Validation/request failed: {exc}", flush=True)
            response = client.get('/api/ps')
            write_json(directory / 'server-processes.json', response.json())
        if errors:
            write_json(directory / 'errors.json', errors)
            manifest['status'] = 'completed_with_errors'
            manifest['failed_fields'] = len(errors)
        else:
            write_json(directory / 'result.json', pipeline.result(article, fields).model_dump())
            manifest['status'] = 'completed'
        print(manifest['status'], directory, flush=True)
        return 1 if errors else 0
    except Exception as exc:
        manifest.update(status='failed', error=str(exc), error_type=type(exc).__name__)
        raise
    finally:
        manifest['elapsed_seconds'] = time.perf_counter() - started
        write_json(directory / 'manifest.json', manifest)


if __name__ == '__main__':
    raise SystemExit(main())
