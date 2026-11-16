"""Related-reading retrieval over the approved snapshot.

Ranking = BM25 relevance x anatomical relevance x source tier x freshness. Chunks flagged as containing
instruction-like text are excluded. The query is built from canonical English concept labels, so Arabic and
Kurdish conversations retrieve the same evidence as English ones.
"""
from dataclasses import dataclass

TIER = {'A': 1.0, 'B': .85, 'C': .7}


@dataclass
class Retrieved:
    chunk_id: str
    unit_index: int
    score: float


def retrieve(kb, concepts: list[str], regions: set[str], exclude_chunks: set[str], limit=3) -> list[Retrieved]:
    query = kb.bm25.tokenise(' '.join(concepts))
    if not query:
        return []
    ranked = []
    for chunk_id in kb.bm25.tokens:
        chunk = kb.chunks[chunk_id]
        if chunk_id in exclude_chunks or chunk['injection_flags'] or chunk.get('duplicate_of'):
            continue
        source = kb.source(chunk['source_id'])
        if not source or source.get('status') != 'active':
            continue
        relevance = kb.bm25.score(query, chunk_id)
        if relevance <= 0:
            continue
        anatomy = set(source.get('anatomy') or [])
        if anatomy and not anatomy & regions:
            continue  # anatomically irrelevant pages are never offered as related reading
        anatomical = 1.0 if anatomy else .7
        fresh = .8 if kb.review_overdue(chunk['source_id']) else 1.0
        care_bonus = 1.1 if chunk.get('care_level') else 1.0
        ranked.append((relevance * anatomical * TIER.get(source.get('tier', 'B'), .8) * fresh * care_bonus, chunk_id))
    ranked.sort(reverse=True)
    out, seen_sources = [], set()
    for score, chunk_id in ranked:
        chunk = kb.chunks[chunk_id]
        if chunk['source_id'] in seen_sources:
            continue  # diversity: one passage per source page
        seen_sources.add(chunk['source_id'])
        best_unit, best_overlap = 0, -1
        for index, unit in enumerate(chunk['units']):
            overlap = len(set(kb.bm25.tokenise(unit['text'])) & set(query))
            if overlap > best_overlap:
                best_unit, best_overlap = index, overlap
        out.append(Retrieved(chunk_id, best_unit, round(score, 4)))
        if len(out) == limit:
            break
    return out
