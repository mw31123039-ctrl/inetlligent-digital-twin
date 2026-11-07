"""Train only from explicitly exported, reviewed local examples; no downloads."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.dental_local import TrainingExample, train_local_model


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', type=Path, required=True, help='Private directory containing exported JSON examples.')
    parser.add_argument('--output', type=Path, default=Path('models/dental-local'))
    args = parser.parse_args()
    try:
        files = sorted(args.dataset.glob('*.json'))
        if not 3 <= len(files) <= 200 or any(file.stat().st_size > 400000 for file in files):
            raise ValueError('Use 3–200 local training JSON files, each at most 400 KB.')
        examples = [TrainingExample.model_validate_json(file.read_text(encoding='utf-8')) for file in files]
        report = train_local_model(examples, args.output)
    except Exception:
        # Pydantic errors may contain complete patient inputs: never print them.
        print('Training was not completed. Check reviewed exports, permissions, image fingerprints, non-overlapping crowns, and separate subjects in train/validation partitions. No previous model was replaced.', file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
