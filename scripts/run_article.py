"""Official full-article execution: freeze, count tokens, extract, consolidate."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from datetime import datetime, timezone

from slr_data_extraction.execution.audit import write_json
from slr_data_extraction.pipeline import ExtractionPipeline
from slr_data_extraction.definitions.result_definition import FieldExtraction


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--study-id')
    parser.add_argument('--schema', type=Path, default=Path('config/gender_and_beyond_schema.json'))
    parser.add_argument('--config', type=Path, default=Path('config/models/qwen3-14b-awq-final.json'))
    parser.add_argument('--run-dir', type=Path, required=True)
    parser.add_argument('--prepare-only', action='store_true', help='Prepare and check all tokens, without generation')
    parser.add_argument('--field', help='One field only, for a partial smoke check')
    parser.add_argument('--batch', type=int, help='One batch only, requires --field; never emits an article result')
    args = parser.parse_args()
    if args.batch is not None and args.field is None:
        parser.error('--batch requires --field')
    config = json.loads(args.config.read_text())
    if (config.get('enable_thinking') is not True or
            config.get('constrained_generation') is not False or config['max_tokens'] != 4096):
        parser.error('Official profile requires thinking=true, constrained_generation=false, max_tokens=4096')
    pipeline = ExtractionPipeline(args.schema, config)
    names = [f.name for f in pipeline.review.fields]
    if args.field and args.field not in names:
        parser.error('Unknown field')
    args.run_dir.mkdir(parents=True, exist_ok=False)
    target = args.run_dir.resolve()
    source, prepared, tokens = target/'source-preparation', target/'prepared', target/'tokens'
    root = Path(__file__).resolve().parents[1]
    env = dict(os.environ, PYTHONPATH=str(root/'src'))
    status = {'status': 'preparing', 'started_at': datetime.now(timezone.utc).isoformat(),
              'article_complete': False, 'failure_policy': 'No retries; preserve failures',
              'selected_fields': [args.field] if args.field else names, 'selected_batch': args.batch}
    shutil.copyfile(__file__, target/'runner.py')
    write_json(target/'manifest.json', status)

    def run(*command):
        subprocess.run([sys.executable, *map(str, command)], env=env, check=True)

    try:
        command = ['-m', 'slr_data_extraction.execution.cli', '--input', args.input.resolve(),
                   '--schema', args.schema.resolve(), '--config', args.config.resolve(),
                   '--run-dir', source, '--prepare-only']
        if args.study_id:
            command.extend(['--study-id', args.study_id])
        run(*command)
        run(root/'scripts/prepare_full_article.py', '--source-run', source,
            '--chunks-per-batch', '1', '--run-dir', prepared)
        plan_hash = hashlib.sha256((prepared/'batches.json').read_bytes()).hexdigest()
        if args.batch is not None and not 1 <= args.batch <= len(json.loads((prepared/'batches.json').read_text())):
            raise ValueError('Batch number outside prepared plan')
        run(root/'scripts/check_batch_tokens.py', '--prepared-run', prepared,
            '--output-dir', tokens, '--expected-plan-sha256', plan_hash)
        if args.prepare_only:
            status['status'] = 'prepared_token_verified'
            return
        status['status'] = 'extracting'
        write_json(target/'manifest.json', status)
        fields, failures = [], []
        for name in status['selected_fields']:
            directory = target/'fields'/name
            command = [root/'scripts/run_batch_field.py', '--prepared-run', prepared,
                       '--token-check', tokens, '--field', name, '--run-dir', directory]
            if args.batch is not None:
                command.extend(['--batch', args.batch])
            run(*command)
            field_status = json.loads((directory/'manifest.json').read_text())
            if field_status['status'] != 'completed':
                failures.append(name)
            elif args.batch is None:
                fields.append(FieldExtraction.model_validate_json((directory/'field-result.json').read_text()))
        status.update(status='completed_with_errors' if failures else 'completed', failed_fields=failures)
        if not failures and args.field is None:
            article = json.loads((prepared/'article.json').read_text())
            write_json(target/'result.json', pipeline.result(article, fields).model_dump())
            status['article_complete'] = True
    except BaseException as exc:
        status.update(status='interrupted_or_failed', error=str(exc))
        raise
    finally:
        write_json(target/'manifest.json', status)
        print('Saved:', target, flush=True)


if __name__ == '__main__':
    main()
