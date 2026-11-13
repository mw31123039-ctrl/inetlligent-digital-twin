"""Review any compatible 2D cancer classifier; reports only unless --activate passes every gate."""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.cancer import MODALITIES
from app.cancer_release import review_upgrade


def run(args):
    dataset = Path(args.cohort).resolve(strict=True)
    if dataset.stat().st_size > 16 * 1024 * 1024:
        raise ValueError('The cohort manifest exceeds the resource limit.')
    cohort = json.loads(dataset.read_text(encoding='utf-8'))
    result = review_upgrade(ROOT / 'models', args.modality, Path(args.candidate).resolve(), cohort,
                            Path(args.image_root), activate=args.activate)
    output = Path(args.output) if args.output else ROOT / 'models/cancer-releases' / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.json')
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix('.part')
    temporary.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    temporary.replace(output)
    print(json.dumps({'report': str(output), 'eligible': result['eligible'], 'activated': result['activated'],
                      'reasons': result['reasons'], 'clinical_validation': False}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--modality', required=True, choices=[value for values in MODALITIES.values() for value in values])
    parser.add_argument('--candidate', required=True, help='Staged model directory inside ai-service/models.')
    parser.add_argument('--cohort', required=True, help='Labelled cohort manifest including train/validation/test identities.')
    parser.add_argument('--image-root', required=True, help='Explicit directory containing the permitted cohort images.')
    parser.add_argument('--output')
    parser.add_argument('--activate', action='store_true')
    args = parser.parse_args()
    try:
        run(args)
    except Exception:
        print('Review or activation failed. Check the cohort, model artifacts, release lock and any saved activation journal before retrying.', file=sys.stderr)
        sys.exit(2)
