import logging
import secrets
import re
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, Header, HTTPException, Depends
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic_settings import BaseSettings, SettingsConfigDict
from .schemas import AssessRequest, Assessment
from .engine import AssessmentEngine
from .evidence import EvidenceRetriever
from .provider import OpenAIProvider, DisabledProvider
from .dental_photo import PhotoDetectionRequest
from .dental_local import LocalSegmentRequest, detect_local_crowns, local_status, refine_local_outline
from .dental_local import TrainingExample
from .dental_public import public_status, detect_public_crowns
from .dental_learning import LearningConflict, LocalDentalLearning, TrainRequest
from .dental_screening import ScreeningRecord
from .dental_screening_store import list_screening_cases, save_screening_case, read_screening_case, remove_screening_case

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')
    service_key: str = ''
    ai_provider: str = 'disabled'
    openai_api_key: str = ''
    openai_model: str = ''
    allow_external_ai: bool = False
    ai_timeout_seconds: float = 18
    retrieval_timeout_seconds: float = 4
    dental_local_model_dir: str = 'models/dental-local'
    dental_public_model_dir: str = 'models/dental-public'
    dental_learning_dir: str = 'training-data/app'

settings = Settings()
configured = settings.ai_provider == 'openai' and bool(settings.openai_api_key and settings.openai_model and settings.allow_external_ai)
provider = OpenAIProvider(settings.openai_api_key, settings.openai_model, settings.ai_timeout_seconds) if configured else DisabledProvider()
engine = AssessmentEngine(provider, EvidenceRetriever(settings.retrieval_timeout_seconds), settings.ai_timeout_seconds)
learning = LocalDentalLearning(Path(settings.dental_learning_dir))

@asynccontextmanager
async def lifespan(_app):
    yield
    if isinstance(provider, OpenAIProvider):
        await provider.client.close()

app = FastAPI(title='HumanTwin private AI service', docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
# Suppress HTTP/provider debug logs even if a parent process enables DEBUG.
for name in ['openai', 'httpx', 'httpcore']:
    logger = logging.getLogger(name)
    logger.handlers = [logging.NullHandler()]
    logger.propagate = False

def authorize(x_service_key: str = Header(default='')):
    if len(settings.service_key) < 32 or not secrets.compare_digest(x_service_key, settings.service_key):
        raise HTTPException(status_code=401, detail='Unauthorized service request.')

@app.exception_handler(RequestValidationError)
async def invalid_request(_request, _error):
    # FastAPI's default validation response echoes rejected health input.
    return JSONResponse(status_code=422, content={'detail': 'Invalid assessment request.'}, headers={'Cache-Control': 'no-store'})

@app.middleware('http')
async def private_response(request, call_next):
    try:
        response = await call_next(request)
    except Exception:
        response = JSONResponse(status_code=503, content={'detail': 'Assessment service unavailable.'})
    response.headers['Cache-Control'] = 'no-store, private'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    return response

@app.get('/health', dependencies=[Depends(authorize)])
def health():
    return {'available': True, 'provider_configured': configured, 'clinical_review_required': True}

@app.post('/v1/assess', response_model=Assessment, dependencies=[Depends(authorize)])
async def assess(request: AssessRequest):
    return await engine.assess(request)

@app.post('/v1/dental/review', dependencies=[Depends(authorize)])
async def dental_review():
    raise HTTPException(status_code=503, detail='External dental AI is disabled. Use the local sourced learning library.')

@app.post('/v1/dental/detect', dependencies=[Depends(authorize)])
def dental_detect(request: PhotoDetectionRequest, x_dental_owner: str = Header(default='')):
    try:
        directory = learning.model_path(x_dental_owner) if x_dental_owner else Path(Settings().dental_local_model_dir)
        if local_status(directory)['provider_configured']:
            return detect_local_crowns(directory, request)
        return detect_public_crowns(Path(Settings().dental_public_model_dir), request)
    except Exception:
        return JSONResponse(status_code=503, content={'detail': 'The local model is not trained or could not return a draft. Use assisted or manual outlining.'})

@app.post('/v1/dental/segment', dependencies=[Depends(authorize)])
def dental_segment(request: LocalSegmentRequest):
    try:
        return refine_local_outline(request)
    except Exception:
        return JSONResponse(status_code=422, content={'detail': 'The local outline could not be refined. Try a clearer rough outline.'})

@app.get('/v1/dental/detection-status', dependencies=[Depends(authorize)])
def dental_detection_status(x_dental_owner: str = Header(default='')):
    directory = learning.model_path(x_dental_owner) if x_dental_owner else Path(Settings().dental_local_model_dir)
    personal = local_status(directory)
    if personal['provider_configured']:
        return personal
    return public_status(Path(Settings().dental_public_model_dir)) or personal

def learning_owner(x_dental_owner: str = Header(default='')):
    if not re.fullmatch('[a-f0-9]{64}', x_dental_owner):
        raise HTTPException(status_code=401, detail='An authenticated teaching-set owner is required.')
    return x_dental_owner

@app.get('/v1/dental/learning', dependencies=[Depends(authorize)])
def dental_learning_status(owner: str = Depends(learning_owner)):
    return learning.status(owner)

@app.post('/v1/dental/learning/examples', dependencies=[Depends(authorize)])
def dental_learning_save(request: TrainingExample, owner: str = Depends(learning_owner)):
    try:
        return learning.save(owner, request)
    except LearningConflict as error:
        raise HTTPException(status_code=409, detail=str(error)) from None
    except ValueError:
        raise HTTPException(status_code=422, detail='Check the JPEG photograph and distinct crown outlines with sufficient foreground and background.') from None

@app.delete('/v1/dental/learning/examples/{example_id}', dependencies=[Depends(authorize)])
def dental_learning_remove(example_id: str, owner: str = Depends(learning_owner)):
    try:
        return learning.remove(owner, example_id)
    except KeyError:
        raise HTTPException(status_code=404, detail='Teaching example not found.') from None
    except LearningConflict as error:
        raise HTTPException(status_code=422, detail=str(error)) from None

@app.post('/v1/dental/learning/train', dependencies=[Depends(authorize)])
def dental_learning_train(request: TrainRequest, owner: str = Depends(learning_owner)):
    try:
        return learning.start(owner)
    except LearningConflict as error:
        raise HTTPException(status_code=409, detail=str(error)) from None

@app.get('/v1/dental/screening/cases', dependencies=[Depends(authorize)])
def dental_screening_cases(owner: str = Depends(learning_owner)):
    return list_screening_cases(learning, owner)

@app.post('/v1/dental/screening/cases', dependencies=[Depends(authorize)])
def dental_screening_save(request: ScreeningRecord, owner: str = Depends(learning_owner)):
    try:
        return save_screening_case(learning, owner, request)
    except LearningConflict:
        raise HTTPException(status_code=409, detail='Check explicit storage permission, patient/visit assignments and patient-level partitions.') from None

@app.get('/v1/dental/screening/cases/{case_id}', dependencies=[Depends(authorize)])
def dental_screening_read(case_id: str, owner: str = Depends(learning_owner)):
    if not re.fullmatch('[a-f0-9]{64}', case_id):
        raise HTTPException(status_code=404, detail='Screening visit not found.')
    try:
        return read_screening_case(learning, owner, case_id)
    except KeyError:
        raise HTTPException(status_code=404, detail='Screening visit not found.') from None

@app.delete('/v1/dental/screening/cases/{case_id}', dependencies=[Depends(authorize)])
def dental_screening_remove(case_id: str, owner: str = Depends(learning_owner)):
    if not re.fullmatch('[a-f0-9]{64}', case_id):
        raise HTTPException(status_code=404, detail='Screening visit not found.')
    try:
        return remove_screening_case(learning, owner, case_id)
    except KeyError:
        raise HTTPException(status_code=404, detail='Screening visit not found.') from None
