# HumanTwin Laravel API

See ../README.md and ../CLINICAL_REVIEW.md for setup, credentials, privacy and limitations. Laravel 13 uses Sanctum first-party cookie authentication and CSRF protection. No patient name, birth date, address or medical profile is requested at signup.

Routes: routes/api.php. Services: app/Services (private Python adapter, JSON Schema validation and authenticated encrypted draft tokens). Saved health records use an encrypted array cast; all record access and deletion is owner scoped. Draft metadata contains no symptoms, region or transcript. Save requires explicit consent and policy version health-storage-v1.

Run php artisan migrate, then php artisan serve --host=127.0.0.1 --port=8000 --no-reload. Run php artisan test --compact for isolated in-memory SQLite tests; HTTP doubles are test-only. The provider key belongs in Python, not this API. AI_SERVICE_KEY is the separate private service credential.

In production, configure HTTPS, secure cookies, trusted first-party domains and the scheduler. Expired non-health session metadata is pruned hourly via conversations:prune. Establish a reviewed maximum retention and backup deletion policy before real patient use. API errors/results are no-store; exception reporting omits bodies, SQL and upstream text.
