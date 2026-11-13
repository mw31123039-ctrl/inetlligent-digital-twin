"""Measure local source retrieval on synthetic software cases; not medical accuracy."""
import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.cancer_knowledge import RETRIEVAL_REVISION, KnowledgeQuestion, retrieve_knowledge


def run(args):
    fixture = ROOT.parent / 'research/cancer-retrieval-cases.v1.json'
    raw = fixture.read_bytes()
    cases = json.loads(raw)['cases']
    rows = []
    for case in cases:
        if args.split != 'all' and case['split'] != args.split:
            continue
        answer = retrieve_knowledge(ROOT / 'models/cancer-knowledge', KnowledgeQuestion(question=case['question'], consent_local=True))
        found = [item.record_id for item in answer.matches]
        rank = next((index + 1 for index, value in enumerate(found) if value in case['accepted']), None)
        rows.append({'case_id': case['id'], 'split': case['split'], 'accepted_records': case['accepted'],
                     'retrieved_records': found, 'top_one': rank == 1 if case['accepted'] else not found,
                     'top_three': rank is not None if case['accepted'] else not found,
                     'reciprocal_rank': 1 / rank if rank else 0,
                     'off_topic_abstained': not found if not case['accepted'] else None,
                     'safety_notice_correct': answer.safety_notice == case['safety_notice'] if 'safety_notice' in case else None,
                     'retrieval_ms': answer.retrieval_ms})
    aggregates = {}
    for split in ('development', 'holdout'):
        subset = [row for row in rows if row['split'] == split]
        if not subset:
            continue
        topical = [row for row in subset if row['accepted_records']]
        irrelevant = [row for row in subset if not row['accepted_records']]
        aggregates[split] = {'cases': len(subset), 'source_queries': len(topical),
                             'top_one_source_accuracy': sum(row['top_one'] for row in topical) / len(topical),
                             'top_three_source_recall': sum(row['top_three'] for row in topical) / len(topical),
                             'mean_reciprocal_rank': sum(row['reciprocal_rank'] for row in topical) / len(topical),
                             'irrelevant_queries': len(irrelevant),
                             'off_topic_abstention_rate': sum(row['off_topic_abstained'] for row in irrelevant) / len(irrelevant)}
    report = {'schema_version': 'humantwin-cancer-retrieval-evaluation-v1', 'created_at': datetime.now(timezone.utc).isoformat(),
              'cases_sha256': hashlib.sha256(raw).hexdigest(), 'model_version': answer.model_version,
              'weights_sha256': answer.weights_sha256, 'corpus_version': answer.corpus_version,
              'retrieval_revision': RETRIEVAL_REVISION,
              'retrieval_code_sha256': hashlib.sha256((ROOT / 'app/cancer_knowledge.py').read_bytes()).hexdigest(),
              'clinical_validation': False, 'interpretation': 'Synthetic source-navigation development checks. These rates are not cancer-detection accuracy, clinical answer correctness or patient validation.',
              'aggregates': aggregates, 'results': rows}
    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    print(json.dumps({'report': str(destination), 'aggregates': aggregates,
                      'failed_cases': [row for row in rows if not row['top_one'] or row['safety_notice_correct'] is False]}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--split', choices=('development', 'holdout', 'all'), default='development')
    parser.add_argument('--output', default='models/cancer-knowledge/evaluation.json')
    run(parser.parse_args())
