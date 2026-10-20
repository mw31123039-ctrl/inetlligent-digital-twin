# Clinical and deployment review required

This is a development prototype. No clinician has reviewed or validated its rules, questions, evidence matching, urgency decisions or AI outputs. Software tests do not establish clinical safety or diagnostic accuracy. Use synthetic inputs until the intended use, clinical protocol and deployment are independently reviewed.

## Draft triage

`ai-service/app/rules/triage.v1.json` is a separately versioned artifact (`draft-2026-10-20.1`) with public NHS references. It covers a limited selection of breathing, chest, neurological, eye, abdominal, circulation, injury and allergy warning signs, including some cross-message combinations. Urgent matches bypass retrieval/provider calls and stop normal questions. Corrections preserve earlier urgent guidance; review a safe process for retracting mistaken reports.

The engine uses English regex with limited negation and historical-context handling. It can miss paraphrases, misspellings, mixed languages, subtle combinations and changing conditions, and it can over-escalate. A non-match is not evidence of safety: urgency remains not established. Review sensitivity/specificity with realistic cases, particularly children, older adults, pregnancy/postpartum, immunocompromised and postoperative patients. Age, pregnancy, vital signs and examination findings are not systematically collected.

Review the optional history/medication/allergy relevance heuristics in `app/questions.py`. Confirm that skipped fields are appropriate for each symptom and population. A selected body region is navigation context, not proof that the cause is confined there.

## Evidence and model

The corpus has two public NHS condition pages per region and is not an exhaustive differential. Citation existence and symptom-word overlap establish provenance, not individual clinical relevance or entailment. A clinician must evaluate explanations against the user's history and supporting excerpts. Review source selection, content drift, review cadence, outages and unsupported cases.

Verbatim quotes do not guarantee correct field classification. Evaluate contradictions, corrections, prompt injection in user/reference text, refusals, long conversations, under-triage, uncertainty and provider failures. The model may raise urgency but cannot lower a rule-triggered warning. It cannot return unrestricted clinical prose, medication/dosage advice or personal probability fields.

No paid model was called during implementation because credentials/model are missing. Provider/source doubles are confined to tests. Evaluate the actual configured model, SDK behavior, refusal handling, timeouts, cost and clinical performance separately before use. Passing tests is not clinical validation.

## Privacy and operations

Review applicable jurisdiction, medical-device obligations, consent, access control, provider health-data processing terms and retention. No compliance certification is claimed. `store=False` is not a guarantee of zero provider retention. Primary application deletion and token revocation are implemented; provider retention, exports and backups require separate reviewed policies.

Production needs HTTPS, secure first-party cookies, trusted Sanctum domains, private Python networking, secret management and rotation, encrypted/access-controlled backups, request/concurrency limits, scheduled expiry pruning, incident response and independent security evaluation. Account recovery, email verification, MFA, explicit maximum retention and region-appropriate emergency pathways remain production work.

Keep health content, tokens and provider request/response bodies out of reverse-proxy logs, analytics, crash reporting, APM and traces. The application suppresses them, but infrastructure can reintroduce exposure. Do not enable verbose SDK logging or Laravel inspection tools on health requests without reviewed redaction.
