"""Verify the local server and context budget before generation."""
import httpx

from ..execution.audit import write_json


def preflight(config, prepared, directory):
    base = config['base_url'].rstrip('/')
    root = base.removesuffix('/v1')
    with httpx.Client(timeout=30, trust_env=False) as client:
        response = client.get(root + '/version')
        response.raise_for_status()
        version = response.json()
        write_json(directory / 'server-version.json', version)
        if version.get('version') != config['vllm_version']:
            raise ValueError('Server vLLM version differs from configured version')
        response = client.get(base + '/models')
        response.raise_for_status()
        models = response.json()
        write_json(directory / 'server-models.json', models)
        if config['model_id'] not in [m['id'] for m in models['data']]:
            raise ValueError('Configured model is not served')
        for index, item in enumerate(prepared):
            response = client.post(root + '/tokenize', json={
                'model': config['model_id'], 'messages': item['request']['messages'],
                'add_generation_prompt': True})
            write_json(directory / f'field-{index + 1:02d}.tokenize.json',
                       {'status_code': response.status_code, 'body': response.text})
            response.raise_for_status()
            tokens = response.json()
            limit = min(config['max_model_len'], tokens['max_model_len'])
            if tokens['count'] + config['max_tokens'] > limit:
                raise ValueError(f"Context overflow for {item['field'].name}; "
                                 'no truncation or model-dependent retrieval adjustment applied')

