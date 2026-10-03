"""Run in the separate PCAD vLLM environment; retain server launch evidence."""
import argparse
from datetime import datetime, timezone
from importlib.metadata import version
import json
from pathlib import Path
import re
import subprocess
import sys

parser = argparse.ArgumentParser()
parser.add_argument('--config', default='config/pilot.json')
parser.add_argument('--log-dir', required=True)
args = parser.parse_args()
config = json.loads(Path(args.config).read_text())
if version('vllm') != config['vllm_version']:
    raise SystemExit('Install the configured vLLM version in this server environment')
if not re.fullmatch(r'[0-9a-f]{40}', config.get('model_revision') or ''):
    raise SystemExit('Set model_revision to an exact Hugging Face commit SHA first')
directory = Path(args.log_dir)
directory.mkdir(parents=True, exist_ok=False)
command = [sys.executable, '-m', 'vllm.entrypoints.openai.api_server',
           '--model', config['model_id'], '--revision', config['model_revision'],
           '--tokenizer-revision', config['model_revision'], '--dtype', config['dtype'],
           '--max-model-len', str(config['max_model_len']),
           '--generation-config', config['generation_config'], '--seed', str(config['seed']),
           '--host', '127.0.0.1', '--port', '8000', '--max-num-seqs', '1',
           '--gpu-memory-utilization', '0.90']
(directory / 'launch.json').write_text(json.dumps({
    'started_at': datetime.now(timezone.utc).isoformat(), 'config': config,
    'command': command, 'vllm_version': version('vllm'), 'python': sys.version}, indent=2))
for name, diagnostic in [('environment.txt', [sys.executable, '-m', 'pip', 'freeze']),
                         ('gpu.txt', ['nvidia-smi'])]:
    with (directory / name).open('w') as stream:
        subprocess.run(diagnostic, stdout=stream, stderr=subprocess.STDOUT, check=False)
print(f'Server logs: {directory / "server.log"}', flush=True)
with (directory / 'server.log').open('w') as stream:
    result = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT)
(directory / 'exit.json').write_text(json.dumps({'returncode': result.returncode}))
raise SystemExit(result.returncode)
