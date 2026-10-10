from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
from importlib.metadata import distributions
import json
from pathlib import Path
import platform
import re
import sys
import time
from urllib.parse import urlparse

from openai import OpenAI

from .audit import Audit, write_json
from ..validation.preflight import preflight
from ..pipeline import ExtractionPipeline, PROMPT_VERSION
from ..definitions.schema_definition import fingerprint
from ..definitions.result_definition import OUTPUT_VERSION


def code_hash():
    digest = hashlib.sha256()
    source_root = Path(__file__).resolve().parents[1]
    for path in sorted(source_root.rglob('*.py')):
        digest.update(path.relative_to(source_root).as_posix().encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()




def save_preparation(directory, pipeline, article):
    snapshot = directory / 'source'
    snapshot.mkdir()
    source_root = Path(__file__).resolve().parents[1]
    for source in sorted(source_root.rglob('*.py')):
        target = snapshot / source.relative_to(source_root)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())
    chunks, prepared = pipeline.prepare(article)
    write_json(directory / 'chunks.json', [asdict(c) for c in chunks])
    for index, item in enumerate(prepared):
        write_json(directory / f'field-{index + 1:02d}.request.json', item['request'])
    write_json(directory / 'retrieval.json', [
        {'field': item['field'].name, 'selected': [c.chunk_id for c in item['selected']],
         'not_selected': [c.chunk_id for c in chunks if c not in item['selected']]}
        for item in prepared])
    return chunks, prepared


def main():
    parser = argparse.ArgumentParser(description='Prepare or execute one auditable local-model pilot.')
    parser.add_argument('--input', required=True)
    parser.add_argument('--schema', default='config/gender_and_beyond_schema.json')
    parser.add_argument('--config', default='config/models/qwen.json')
    parser.add_argument('--run-dir', required=True)
    parser.add_argument('--prepare-only', action='store_true')
    args = parser.parse_args()
    directory = Path(args.run_dir)
    # Never overwrite an earlier run.
    directory.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    manifest = {'started_at': datetime.now(timezone.utc).isoformat(), 'status': 'running',
                'python': platform.python_version(), 'platform': platform.platform(),
                'source_sha256': code_hash(),
                'packages': {d.metadata['Name']: d.version for d in distributions()}}
    write_json(directory / 'manifest.json', manifest)
    try:
        article_bytes = Path(args.input).read_bytes()
        article = json.loads(article_bytes)
        config = json.loads(Path(args.config).read_text())
        write_json(directory / 'config.json', config)
        write_json(directory / 'article.json', article)
        manifest['input_sha256'] = hashlib.sha256(article_bytes).hexdigest()
        host = urlparse(config['base_url']).hostname
        if host not in {'127.0.0.1', 'localhost', '::1'}:
            raise ValueError('Pilot endpoint must be local (use an SSH tunnel if necessary)')
        pipeline = ExtractionPipeline(args.schema, config)
        write_json(directory / 'schema.json', pipeline.schema)
        manifest.update(schema_id=pipeline.review.schema_id,
                        schema_version=pipeline.review.schema_version,
                        schema_sha256=fingerprint(pipeline.schema),
                        output_version=OUTPUT_VERSION, prompt_version=PROMPT_VERSION)
        chunks, prepared = save_preparation(directory, pipeline, article)
        if args.prepare_only:
            manifest['status'] = 'prepared'
        else:
            if not re.fullmatch(r'[0-9a-f]{40}', config.get('model_revision') or ''):
                raise ValueError('Set model_revision to the exact 40-character Hugging Face commit SHA')
            # Revision is a declared launch parameter, not discoverable from /models.
            manifest['model_revision_verification'] = 'operator-declared; verify against server launch log'
            preflight(config, prepared, directory)
            with OpenAI(base_url=config['base_url'], api_key='local', max_retries=0,
                        timeout=180) as client:
                pipeline.client = client
                fields = pipeline.extract(prepared, article['pages'], Audit(directory))
            write_json(directory / 'result.json', pipeline.result(article, fields).model_dump())
            manifest['status'] = 'completed'
        print(f"{manifest['status']}: {directory}")
        return 0
    except Exception as exc:
        manifest.update(status='failed', error_type=type(exc).__name__, error=str(exc))
        print(f'Pilot failed: {exc}', file=sys.stderr)
        return 1
    finally:
        manifest['elapsed_seconds'] = time.perf_counter() - started
        write_json(directory / 'manifest.json', manifest)


if __name__ == '__main__':
    raise SystemExit(main())
