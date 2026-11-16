"""FastAPI routes for clinical assessment v2 (mounted by app.main behind the service-key dependency)."""
import asyncio
import base64
import binascii
import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from .documents import ExtractRequest, ExtractResult, extract_report
from .engine import ENGINE_VERSION, Engine, RequestError
from .kb import load_kb
from .schemas import Assessment, AssessRequest

router = APIRouter()
engine = Engine()


def configure(language_model):
    engine.language_model = language_model


@router.get('/v2/clinical/catalog')
def catalog():
    """Anatomy, symptom labels and coverage for the UI. Contains no patient data."""
    kb = load_kb()
    return {
        'versions': {'engine': ENGINE_VERSION, 'anatomy': kb.anatomy_version, 'symptoms': kb.symptoms_doc['version'], 'knowledge': kb.knowledge['version'], 'snapshot': kb.snapshot['version']},
        'anatomy': list(kb.anatomy.values()),
        'symptoms': [{'id': s['id'], 'label': s['label'], 'group': s['group']} for s in kb.symptoms.values()],
        'coverage': coverage(),
        'imaging_scope': kb.knowledge['imaging_scope'],
    }


@router.get('/v2/clinical/coverage')
def coverage():
    kb = load_kb()
    by_region = {}
    for condition in kb.conditions:
        for region in sorted({kb.region(a) for a in condition['anatomy'] if a in kb.anatomy}):
            by_region.setdefault(region, []).append({'id': condition['id'], 'name': condition['name'], 'urgent_condition': condition['urgent_condition'],
                                                     'sources': condition['sources'], 'review_status': condition['review_status']})
    overdue = [sid for sid in kb.snapshot['sources'] if kb.review_overdue(sid)]
    return {'conditions': len(kb.conditions), 'red_flags': len(kb.red_flags), 'sources': len(kb.snapshot['sources']), 'chunks': len(kb.chunks),
            'unbound_evidence': kb.unbound, 'sources_review_overdue': overdue, 'by_region': by_region, 'known_gaps': kb.knowledge['coverage_gaps'],
            'clinical_review_status': kb.knowledge['clinical_review_status'], 'snapshot_version': kb.snapshot['version'], 'built_at': kb.snapshot['built_at']}


@router.post('/v2/clinical/assess', response_model=Assessment)
async def assess(request: AssessRequest):
    try:
        return await engine.assess(request)
    except RequestError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None


@router.post('/v2/clinical/assess/stream')
async def assess_stream(request: AssessRequest):
    """NDJSON: {"type":"stage",...}* then one {"type":"result","assessment":{...}} or {"type":"error"}.
    Stages are emitted as each step actually completes; nothing is invented to look busy."""
    queue: asyncio.Queue = asyncio.Queue()

    async def progress(name):
        await queue.put({'type': 'stage', 'stage': name})

    async def run():
        try:
            result = await engine.assess(request, progress)
            await queue.put({'type': 'result', 'assessment': json.loads(result.model_dump_json())})
        except RequestError as error:
            await queue.put({'type': 'error', 'status': 422, 'message': str(error)})
        except Exception:
            await queue.put({'type': 'error', 'status': 503, 'message': 'The assessment could not be completed.'})
        await queue.put(None)

    async def body():
        task = asyncio.create_task(run())
        try:
            while True:
                item = await queue.get()
                if item is None:
                    break
                yield json.dumps(item, ensure_ascii=False) + '\n'
        finally:
            task.cancel()

    return StreamingResponse(body(), media_type='application/x-ndjson', headers={'Cache-Control': 'no-store, private', 'X-Accel-Buffering': 'no'})


@router.post('/v2/clinical/documents/extract', response_model=ExtractResult)
def extract_document(request: ExtractRequest):
    try:
        raw = base64.b64decode(request.content_base64, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(status_code=422, detail='The document encoding is invalid.') from None
    if len(raw) > 5_000_000:
        raise HTTPException(status_code=413, detail='Reports up to 5 MB are supported.')
    return extract_report(raw, request.media_type)
