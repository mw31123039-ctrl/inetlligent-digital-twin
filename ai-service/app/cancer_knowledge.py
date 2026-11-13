"""Real local sentence embeddings retrieve approved source IDs, never invent medical prose."""
import hashlib
import json
import re
import threading
import time
from pathlib import Path
from typing import Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, field_validator

CORPUS_PATH = Path(__file__).resolve().parents[2] / 'contracts/cancer-knowledge.v1.json'
_lock = threading.Lock()
_cache = {}
RETRIEVAL_REVISION = 'semantic-v2-explicit-topic-reranking'
# Source-navigation aliases, never symptom-to-diagnosis rules. Rerank only the
# encoder's three already-relevant records and preserve their real cosine scores.
TOPIC_TERMS = {
    'skin': ('skin', 'melanoma', 'dermoscopy'),
    'oral': ('oral', 'mouth', 'tongue', 'gums'),
    'lung': ('lung', 'pulmonary'),
    'breast': ('breast', 'mammogram', 'mammography'),
    'colorectal': ('colorectal', 'colon', 'rectal', 'bowel', 'colonoscopy'),
    'prostate': ('prostate', 'psa'),
    'cervical': ('cervical', 'cervix', 'hpv', 'colposcopy'),
    'ovarian': ('ovarian', 'ovary', 'ovaries'),
    'pancreatic': ('pancreatic', 'pancreas'),
    'liver': ('liver', 'hepatocellular'),
    'kidney': ('kidney', 'renal'),
    'brain': ('brain', 'glioma', 'cns'),
    'bladder': ('bladder', 'cystoscopy'),
    'thyroid': ('thyroid',),
    'leukemia': ('leukemia', 'leukaemia', 'myeloid'),
    'lymphoma': ('lymphoma', 'hodgkin'),
}
RecordId = Literal['skin', 'oral', 'lung', 'breast', 'colorectal', 'prostate', 'cervical', 'ovarian',
                   'pancreatic', 'liver', 'kidney', 'brain', 'bladder', 'thyroid', 'leukemia', 'lymphoma',
                   'upload-image', 'understand-scores', 'choose-treatment', 'urgent-concerns']


class KnowledgeQuestion(BaseModel):
    model_config = ConfigDict(extra='forbid')
    question: str = Field(min_length=3, max_length=600)
    consent_local: Literal[True]

    @field_validator('question')
    @classmethod
    def nonempty_question(cls, value):
        value = value.strip()
        if len(value) < 3:
            raise ValueError('Enter a question of at least three characters.')
        return value


class KnowledgeMatch(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    record_id: RecordId
    similarity: float = Field(ge=-1, le=1)


class KnowledgeAnswer(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    schema_version: Literal['humantwin-cancer-retrieval-v1']
    method: Literal['local-semantic-retrieval']
    corpus_version: Literal['oncology-reference-2026-11-13']
    model_version: str = Field(pattern=r'^[a-zA-Z0-9._-]{1,80}$')
    weights_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    question_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    matches: list[KnowledgeMatch] = Field(max_length=3)
    retrieval_ms: float = Field(ge=0)
    safety_notice: Literal['none', 'urgent-terms', 'emergency-terms']
    question_saved: Literal[False]
    external_requests: Literal[False]
    clinical_validation: Literal[False]


def pooled_embedding(hidden, attention):
    values = np.asarray(hidden, np.float32)
    mask = np.asarray(attention, np.float32)
    if values.ndim != 3 or values.shape[:2] != mask.shape or values.shape[2] != 384 or not np.isfinite(values).all():
        raise ValueError('Invalid encoder output.')
    pooled = (values * mask[:, :, None]).sum(axis=1) / np.maximum(mask.sum(axis=1, keepdims=True), 1)
    norms = np.linalg.norm(pooled, axis=1, keepdims=True)
    if not np.isfinite(norms).all() or (norms < 1e-9).any():
        raise ValueError('Invalid pooled embedding.')
    return pooled / norms


def encode(session, tokenizer, texts):
    batches = []
    names = [item.name for item in session.get_inputs()]
    for start in range(0, len(texts), 4):
        tokens = tokenizer.encode_batch(texts[start:start + 4])
        inputs = {'input_ids': np.array([item.ids for item in tokens], np.int64),
                  'attention_mask': np.array([item.attention_mask for item in tokens], np.int64),
                  'token_type_ids': np.array([item.type_ids for item in tokens], np.int64)}
        if set(names) - set(inputs):
            raise ValueError('Unsupported encoder inputs.')
        outputs = session.run(None, {name: inputs[name] for name in names})
        batches.append(pooled_embedding(outputs[0], inputs['attention_mask']))
    return np.concatenate(batches, axis=0)


def load_encoder(root: Path):
    import onnxruntime as ort
    from tokenizers import Tokenizer
    manifest_path, weights_path, tokenizer_path = root / 'manifest.json', root / 'model.onnx', root / 'tokenizer.json'
    sizes = [manifest_path.stat().st_size, weights_path.stat().st_size, tokenizer_path.stat().st_size]
    if not 0 < sizes[0] < 12000 or not 0 < sizes[1] < 80 * 1024 * 1024 or not 0 < sizes[2] < 2 * 1024 * 1024:
        raise ValueError('Unexpected encoder artifact size.')
    corpus_raw = CORPUS_PATH.read_bytes()
    key = (str(root.resolve()), *(path.stat().st_mtime_ns for path in [manifest_path, weights_path, tokenizer_path]), hashlib.sha256(corpus_raw).hexdigest())
    if key in _cache:
        return _cache[key]
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    weights, tokenizer_bytes = weights_path.read_bytes(), tokenizer_path.read_bytes()
    if manifest.get('format') != 'humantwin-cancer-encoder-v1' or manifest.get('clinical_validation') is not False or manifest.get('pooling') != 'attention-masked-mean-l2-normalized' or manifest.get('maximum_tokens') != 256 or manifest.get('embedding_dimensions') != 384:
        raise ValueError('Unsupported encoder contract.')
    if hashlib.sha256(weights).hexdigest() != manifest['model_sha256'] or hashlib.sha256(tokenizer_bytes).hexdigest() != manifest['tokenizer_sha256']:
        raise ValueError('Encoder artifact fingerprint mismatch.')
    corpus = json.loads(corpus_raw)
    if corpus.get('version') != 'oncology-reference-2026-11-13' or corpus.get('clinical_validation') is not False:
        raise ValueError('Unsupported source corpus.')
    records = []
    for topic in corpus['topics']:
        text = '. '.join([topic['name'], topic['overview'], *topic['symptoms'], *topic['investigations'], *topic['treatment'], *topic['keywords']])
        records.append((topic['id'], text))
    records.extend((item['id'], item['title'] + '. ' + item['text']) for item in corpus['faqs'])
    if len(records) != 20 or len({item[0] for item in records}) != 20:
        raise ValueError('The approved source corpus is incomplete or duplicated.')
    # Pydantic enforces the same closed ID set in the public result contract.
    for identifier, _ in records:
        KnowledgeMatch(record_id=identifier, similarity=0)
    options = ort.SessionOptions()
    options.intra_op_num_threads = 2
    options.inter_op_num_threads = 1
    options.log_severity_level = 4
    session = ort.InferenceSession(weights, sess_options=options, providers=['CPUExecutionProvider'])
    tokenizer = Tokenizer.from_str(tokenizer_bytes.decode('utf-8'))
    tokenizer.enable_truncation(max_length=256)
    tokenizer.enable_padding(pad_id=0, pad_token='[PAD]')
    embeddings = encode(session, tokenizer, [item[1] for item in records])
    for prior in list(_cache):
        if prior[0] == key[0]:
            del _cache[prior]
    _cache[key] = (manifest, corpus, session, tokenizer, records, embeddings)
    return _cache[key]


def knowledge_status(root: Path):
    try:
        with _lock:
            manifest, corpus, *_ = load_encoder(root)
        return {'available': True, 'configured': True, 'method': 'local-semantic-retrieval',
                'model_version': manifest['model_version'], 'corpus_version': corpus['version'],
                'clinical_validation': False, 'external_requests': False}
    except Exception:
        return {'available': False, 'configured': False, 'method': 'local-semantic-retrieval',
                'clinical_validation': False, 'external_requests': False}


def safety_terms(question):
    text = question.lower()
    if re.search(r"(can.?t|cannot|severe).{0,28}(breath|breathe)|gasping|choking|bleed.{0,25}(won.?t stop|not stop)|more than.{0,20}(streak|blood)", text):
        return 'emergency-terms'
    if re.search(r'(cough|spit).{0,24}blood|blood.{0,24}(cough|phlegm)', text):
        return 'urgent-terms'
    return 'none'


def rank_source_records(similarities, records, question):
    values = np.asarray(similarities, np.float64)
    if values.shape != (len(records),) or not np.isfinite(values).all():
        raise ValueError('Invalid retrieval scores.')
    # A software relevance threshold, not a clinical probability or safety cutoff.
    eligible = [int(index) for index in np.argsort(-values, kind='stable')[:3] if values[index] >= .22]
    text = question.casefold()

    def explicitly_named(index):
        return any(re.search(r'(?<!\w)' + re.escape(term) + r'(?!\w)', text)
                   for term in TOPIC_TERMS.get(records[index][0], ()))

    return sorted(eligible, key=lambda index: (not explicitly_named(index), -values[index]))


def retrieve_knowledge(root: Path, request: KnowledgeQuestion):
    started = time.perf_counter()
    with _lock:
        manifest, corpus, session, tokenizer, records, embeddings = load_encoder(root)
        vector = encode(session, tokenizer, [request.question])[0]
        similarities = embeddings @ vector
    ranked = rank_source_records(similarities, records, request.question)
    matches = [KnowledgeMatch(record_id=records[index][0], similarity=float(np.clip(similarities[index], -1, 1)))
               for index in ranked]
    return KnowledgeAnswer(schema_version='humantwin-cancer-retrieval-v1', method='local-semantic-retrieval',
                           corpus_version=corpus['version'], model_version=manifest['model_version'],
                           weights_sha256=manifest['model_sha256'], question_sha256=hashlib.sha256(request.question.encode()).hexdigest(),
                           matches=matches, retrieval_ms=round((time.perf_counter() - started) * 1000, 2), safety_notice=safety_terms(request.question),
                           question_saved=False, external_requests=False, clinical_validation=False)
