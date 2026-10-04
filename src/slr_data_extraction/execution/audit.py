"""Persist requests/results even when generation or validation fails."""
import json
import time
from contextlib import contextmanager
from pathlib import Path


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


class FieldRecord:
    def __init__(self, directory, index):
        self.prefix = directory / f'field-{index + 1:02d}'

    def raw(self, text):
        self.prefix.with_suffix('.raw.txt').write_text(text, encoding='utf-8')

    def validated(self, value):
        write_json(self.prefix.with_suffix('.validated.json'), value)


class Audit:
    def __init__(self, directory):
        self.directory = Path(directory)

    @contextmanager
    def field(self, index, name):
        started = time.perf_counter()
        record = FieldRecord(self.directory, index)
        status = {'field': name, 'status': 'running'}
        try:
            yield record
            status['status'] = 'completed'
        except Exception as exc:
            status.update(status='failed', error_type=type(exc).__name__, error=str(exc))
            raise
        finally:
            status['elapsed_seconds'] = time.perf_counter() - started
            write_json(record.prefix.with_suffix('.status.json'), status)
