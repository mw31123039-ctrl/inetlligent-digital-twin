# HumanTwin private Python service

See the root README and CLINICAL_REVIEW.md. FastAPI requires `X-Service-Key` for Laravel requests. General symptom inference remains stateless; explicitly consented dental teaching uses private account-scoped SQLite files. Bind only to loopback/private networking.

```powershell
uv sync --frozen --python 3.12
.venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8001 --no-access-log
.venv/Scripts/python.exe -m pytest -q
```

The root setup script creates matching internal service keys. The separate general symptom provider optionally uses AI_PROVIDER, OPENAI_API_KEY, OPENAI_MODEL and ALLOW_EXTERNAL_AI. Dental tools never use an external provider. Restart after environment/rule changes. No test provider is used during normal execution.

- `app/schemas.py`: strict decisions, facts, sources and assessment contract.
- `app/engine.py`: verbatim evidence validation, questions and guarded explanations.
- `app/triage.py`, `app/rules/triage.v1.json`: independent draft warning rules.
- `app/evidence.py`: bounded allowlisted NHS retrieval, host-restricted redirects, public-text-only cache.
- `app/provider.py`: official SDK adapter and provider protocol.

POST `/v1/assess` receives region, side, trusted history and prior urgency from Laravel. GET `/health` reports availability/configuration only. Both require the service key. Validation errors do not echo inputs and provider exceptions are not logged.

Regenerate the shared schema after changing Assessment with `.venv/Scripts/python.exe scripts/export-schema.py`; tests detect drift. Laravel independently checks that schema. No credentialed model call has been verified; test doubles do not establish clinical performance.

Dental local tools: /v1/dental/segment fits one user-drawn crown with GrabCut. /v1/dental/detect first uses the account's own trained forest, or the separate operator forest for ownerless internal calls. If none is trained, it uses the experimental public-data ONNX tooth detector at DENTAL_PUBLIC_MODEL_DIR (default models/dental-public), with per-box GrabCut refinement. Both require local-processing consent and the internal service key. Train the public model with `uv sync --group dental-training` and `python scripts/train-dental-public.py --download --epochs 30`; see the root README for source/license/validation limits. The Windows helper `scripts/train-dental-public.ps1` uses the installed managed interpreter and project dependencies. No dental weights are bundled in Git. Status does not claim clinical validation or supervised mask accuracy for the public detector. Ordinary inference saves no photo and updates no model.

In-app teaching uses /v1/dental/learning with authenticated owner headers derived by Laravel, local SQLite under DENTAL_LEARNING_DIR, and a single background worker. It saves examples only on explicit teaching consent and starts training only on a separate request. Run one Uvicorn worker. Models/inference are account-scoped; standalone CLI/operator models remain separate. Teaching status never includes photo bytes. Data changes invalidate saved model versions and discard in-flight results. See root README for the browser workflow.

Orthodontic screening annotations use owner-scoped /v1/dental/screening/cases (GET/POST) and /{case_id} (GET/DELETE), the strict screening-case schema, and separate SQLite case tables. Every patient visit remains in one split across this store and crown teaching. Explicit photo/storage/research rights are required. There is no orthodontic condition classifier; saves never invoke training. Taxonomy review remains pending and recorded review is self-attested.
