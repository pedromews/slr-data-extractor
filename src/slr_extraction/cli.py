from __future__ import annotations

import argparse
import json
from pathlib import Path

from .pipeline import ExtractionPipeline


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--schema", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    article = json.loads(Path(args.input).read_text(encoding="utf-8"))
    result = ExtractionPipeline(args.schema, args.model).run(article)
    Path(args.output).write_text(
        result.model_dump_json(indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()

