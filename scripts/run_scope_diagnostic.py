"""Replay a frozen batch with an optional generic category/scope instruction."""
import argparse
import copy
import re
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


SUPPLEMENT = (
    "\n\nWhen the field asks for categories or types and a passage enumerates distinct "
    "categories, return a separate concise value for each category supported by the "
    "passage. Do not substitute the cause, consequence, or mitigation for the category. "
    "Preserve expressions that denote a single concept. "
    "Apply the field definition's evidence requirements without adding an empirical "
    "observation requirement. When the definition accepts potential consequences or "
    "author discussion, explicit statements of those consequences qualify if they "
    "meet the field's scope. A statement that a problem compromises, reduces, or "
    "affects something can support a consequence without a numerical measurement. "
    "Do not infer consequences that the supplied passages do not state."
)


ITEM_SUPPLEMENT = (
    "\n\nEach value must directly answer the field definition and represent one "
    "independently identifiable item. When several items are enumerated in the "
    "evidence, represent each item separately. Multiple values may cite the same "
    "evidence ID. Keep compound expressions together when they name a single concept."
)
SUPPLEMENTS = {'baseline': '', 'clarified': SUPPLEMENT, 'individual-items': ITEM_SUPPLEMENT}


def variant_request(original, variant):
    request = copy.deepcopy(original)
    if variant not in SUPPLEMENTS:
        raise ValueError('Unknown variant')
    if SUPPLEMENTS[variant]:
        if request['messages'][0]['role'] != 'system':
            raise ValueError('Expected a system message')
        request['messages'][0]['content'] += SUPPLEMENTS[variant]
    return request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepared-run', type=Path, required=True)
    parser.add_argument('--run-dir', type=Path, required=True)
    parser.add_argument('--prepare-only', action='store_true')
    parser.add_argument('--field', required=True)
    parser.add_argument('--batch', type=int, default=2)
    parser.add_argument('--variant', choices=list(SUPPLEMENTS), required=True)
    args = parser.parse_args()
    source, target = args.prepared_run, args.run_dir
    schema = json.loads((source / 'schema.json').read_text())
    index = next(i for i, f in enumerate(schema['fields'], 1) if f['name'] == args.field)
    request_path = source / f'batch-{args.batch:02d}.field-{index:02d}.request.json'
    original = json.loads(request_path.read_text())
    if 'response_format' in original:
        raise ValueError('Expected the unconstrained comparison request')
    request = variant_request(original, args.variant)
    catalog = json.loads((source / 'evidence-catalog.json').read_text())
    passages = original['messages'][1]['content'].split('\nPassages:\n', 1)[1]
    ids = re.findall(r'^\[([^;\n]+); page ', passages, re.MULTILINE)
    if not ids or any(key not in catalog for key in ids):
        raise ValueError('Cannot identify the supplied evidence segments')
    selected = {key: catalog[key] for key in ids}
    config = json.loads((source / 'config.json').read_text())
    target.mkdir(parents=True, exist_ok=False)
    for name in ['config.json', 'schema.json', 'manifest.json']:
        shutil.copyfile(source / name, target / ('source-' + name))
    shutil.copyfile(__file__, target / 'diagnostic-script.py')
    shutil.copyfile(request_path, target / 'original.request.json')
    write_json(target / 'request.json', request)
    write_json(target / 'evidence-catalog.json', selected)
    manifest = {'status': 'prepared', 'started_at': datetime.now(timezone.utc).isoformat(),
                'purpose': 'Frozen-batch prompt diagnostic; not an end-to-end evaluation',
                'source_run': str(source.resolve()), 'evidence_ids': ids,
                'variant': args.variant, 'field': args.field, 'batch': args.batch,
                'changes': {'system_prompt_append': SUPPLEMENTS[args.variant]},
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
        if result.field_name != args.field:
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
