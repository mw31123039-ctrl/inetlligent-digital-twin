<?php

return [
    'url' => env('AI_SERVICE_URL', 'http://127.0.0.1:8001'),
    'key' => env('AI_SERVICE_KEY', ''),
    'timeout' => 28,
    'conversation_minutes' => 60,
    // Clinical v2: upper bound on interview questions so urgent or complete cases never become a long questionnaire.
    'clinical_max_questions' => (int) env('CLINICAL_MAX_QUESTIONS', 12),
    // Days before unconfirmed report extracts are discarded.
    'pending_extract_days' => 14,
];
