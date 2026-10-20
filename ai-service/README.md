# HumanTwin private Python service

See the root README and CLINICAL_REVIEW.md. FastAPI is stateless, has no database, and requires `X-Service-Key` for Laravel requests. Bind only to loopback/private networking.

```powershell
uv sync --frozen --python 3.12
.venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8001 --no-access-log
.venv/Scripts/python.exe -m pytest -q
```

The root setup script creates matching internal service keys. Real AI additionally requires AI_PROVIDER=openai, OPENAI_API_KEY, OPENAI_MODEL and ALLOW_EXTERNAL_AI=true in this server's `.env`. Restart after environment/rule changes. No test provider is used during normal execution.

- `app/schemas.py`: strict decisions, facts, sources and assessment contract.
- `app/engine.py`: verbatim evidence validation, questions and guarded explanations.
- `app/triage.py`, `app/rules/triage.v1.json`: independent draft warning rules.
- `app/evidence.py`: bounded allowlisted NHS retrieval, host-restricted redirects, public-text-only cache.
- `app/provider.py`: official SDK adapter and provider protocol.

POST `/v1/assess` receives region, side, trusted history and prior urgency from Laravel. GET `/health` reports availability/configuration only. Both require the service key. Validation errors do not echo inputs and provider exceptions are not logged.

Regenerate the shared schema after changing Assessment with `.venv/Scripts/python.exe scripts/export-schema.py`; tests detect drift. Laravel independently checks that schema. No credentialed model call has been verified; test doubles do not establish clinical performance.
