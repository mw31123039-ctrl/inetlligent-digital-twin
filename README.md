# Intelligent Digital Twin of the Human Body

Vue/Three.js human explorer with an authenticated Laravel API and private Python symptom-assistant service.

**Development prototype; not clinically validated. Use synthetic inputs.** No external AI key or model is configured. The interface reports **AI not configured** and offers limited, explicitly labeled rule-based intake, without AI explanations. The original questionnaire remains under **Scripted demo**. Test doubles are used only in tests.

## Local setup

Requirements: Node.js 22.12+, PHP 8.4+ with SQLite/OpenSSL/mbstring/DOM/curl/ZIP, Composer, and [uv](https://docs.astral.sh/uv/) for Python 3.12. The Composer lock uses Symfony 8 and requires PHP 8.4+.

```powershell
powershell -File scripts/setup.ps1
```

The setup script installs dependencies, preserves existing environments, generates matching internal service secrets without printing them, and migrates SQLite. It does not configure or enable a paid AI provider. Use `-SkipInstall` for existing dependencies. Run these commands in three separate terminals, starting from the project root:

```powershell
# Terminal 1
cd ai-service
.venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8001 --no-access-log
# Terminal 2
cd backend
php artisan serve --host=127.0.0.1 --port=8000 --no-reload
# Terminal 3
cd frontend
npm run dev
```

Open http://127.0.0.1:5173. Create an account using a test email and a password of at least 12 characters. Acknowledge processing, select a body area and describe a synthetic symptom. Correct answer edits an earlier answer and removes derived later answers. Changing region or side starts fresh intake. Start over clears the on-screen draft. Save with consent is optional. Assessments/History show only the authenticated owner's saved records; deletion removes the saved record and invalidates the draft token.

## Configure the real provider

Set these **only in `ai-service/.env`**, then restart Python:

```dotenv
AI_PROVIDER=openai
OPENAI_API_KEY=your-server-key
OPENAI_MODEL=your-account-model-supporting-structured-outputs
ALLOW_EXTERNAL_AI=true
```

Keep Python SERVICE_KEY equal to Laravel AI_SERVICE_KEY; these are internal credentials distinct from the external AI key. No key belongs in Vue or a `VITE_` variable. No paid model call was made during implementation, so the credentialed provider path still requires integration evaluation. Unsupported/incomplete configuration remains disabled. `DecisionProvider` is the adapter boundary for additional providers using their official SDKs. No model training is implemented.

The OpenAI adapter uses its official Python SDK: `responses.parse(..., text_format=ModelDecision, store=False)`. [Official structured output documentation](https://developers.openai.com/api/docs/guides/structured-outputs).

## Architecture and privacy

```text
Vue chatbot -> Laravel /api -> private Python /v1/assess -> validated structured assessment
frontend/     dashboard, real rigged human, AI chat, explicit scripted demo
backend/      Laravel 13, Sanctum cookie auth/CSRF, owner-scoped encrypted records
ai-service/   FastAPI, Pydantic, independent triage rules, NHS retrieval, official SDK adapter
contracts/    shared assessment JSON Schema independently checked by Laravel
```

The full-stack repository is [mw31123039-ctrl/inetlligent-digital-twin](https://github.com/mw31123039-ctrl/inetlligent-digital-twin), including `frontend/`, `backend/`, `ai-service/`, `contracts/` and setup/review files. The root `.gitignore` excludes local credentials, databases, dependencies and generated archives.

Python has no database. Laravel passes no account email/name to Python or the provider. Draft health content stays in browser memory and an authenticated encrypted client-held token. Before save consent, Laravel stores only random session ID, owner ID, revision and expiry in `conversation_sessions`, without symptoms/body region. Tokens are owner-bound, expire after one hour, reject stale revisions, and are revoked by deletion. A lost network reply can leave a stale token; the UI asks for a new assessment rather than replaying an answer.

Saving requires consent and policy version `health-storage-v1`. Only then is a Laravel encrypted-array payload stored in `health_assessments`. Account email/password hashes, auth sessions and rate-limit metadata are separate. No active transcript/result is written to browser storage. Only the chat-mode preference is in sessionStorage; explicitly consented scripted-demo saves remain browser-local. Saved snapshots are read-only; start a new conversation for further answers.

Application deletion removes primary records and clears the current screen; it does not promise deletion from external-provider retention, backups or user exports. `store=False` is not a zero-retention guarantee. Review provider processing terms before external AI is enabled. Laravel reports API exception class only, without request/SQL/upstream content; Python HTTP/provider debug and access logs are suppressed. Infrastructure logging/APM still needs review.

The Vite development proxy forwards `/api` and `/sanctum` to Laravel. Production needs HTTPS, secure cookies, the correct Sanctum first-party domains, an equivalent reverse proxy, and private access to Python. Run Laravel's scheduler (`schedule:run`) to prune expired non-health session metadata hourly.

## Safety and evidence

- `ai-service/app/rules/triage.v1.json` contains **draft, unvalidated English rules**, separately versioned and linked to NHS references. Screening runs throughout the conversation before retrieval/model calls. Urgent matches stop normal questions and return immediate guidance. Corrections cannot silently downgrade previously raised urgent guidance.
- Facts require exact user-message quotes. AI explanations are constrained to current-region allowlisted NHS pages actually retrieved, with verified excerpts and a reported-symptom overlap check. These checks establish provenance, **not clinical entailment or validation**. Retrieval failure is explicit; no sources are invented. Urgent guidance bypasses retrieval so it is not delayed.
- The model selects relevant question fields and uncertain explanation candidates. It cannot inject unrestricted diagnostic prose, personal probability percentages, prescriptions or dosages. The app formats conservative uncertainty and next actions. Reported diagnoses remain user-reported facts.
- Pydantic validates decisions and results; Laravel validates the final result against the shared schema. Provider refusal, timeout, malformed data, source failure and missing credentials lead to honest limited-intake/unavailable states.

Read [CLINICAL_REVIEW.md](CLINICAL_REVIEW.md) before considering real patient use.

## Tests

```powershell
cd ai-service
.venv/Scripts/python.exe -m pytest -q
cd ../backend
php artisan test --compact
cd ../frontend
npm run build
npm test
npm run test:e2e
```

Install Chromium with `npx playwright install chromium` if needed. Full-stack browser tests require all three services and run only with AI disabled; no paid calls occur. Unit tests use test-only provider/source doubles. Tests cover context, follow-ups, corrections, urgency, insufficient information, unsupported explanations, malformed outputs, failures, consent, encryption, deletion, isolation and the existing body viewer. Passing software tests does not establish clinical performance.

Human model/license: [asset attribution](frontend/ASSET_ATTRIBUTIONS.md). No new model file is needed. Existing zip/tar deployment archives remain older frontend snapshots, not updated releases.
