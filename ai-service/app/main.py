import logging
import secrets
from contextlib import asynccontextmanager
from fastapi import FastAPI, Header, HTTPException, Depends
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic_settings import BaseSettings, SettingsConfigDict
from .schemas import AssessRequest, Assessment
from .engine import AssessmentEngine
from .evidence import EvidenceRetriever
from .provider import OpenAIProvider, DisabledProvider

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')
    service_key: str = ''
    ai_provider: str = 'disabled'
    openai_api_key: str = ''
    openai_model: str = ''
    allow_external_ai: bool = False
    ai_timeout_seconds: float = 18
    retrieval_timeout_seconds: float = 4

settings = Settings()
configured = settings.ai_provider == 'openai' and bool(settings.openai_api_key and settings.openai_model and settings.allow_external_ai)
provider = OpenAIProvider(settings.openai_api_key, settings.openai_model, settings.ai_timeout_seconds) if configured else DisabledProvider()
engine = AssessmentEngine(provider, EvidenceRetriever(settings.retrieval_timeout_seconds), settings.ai_timeout_seconds)

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
