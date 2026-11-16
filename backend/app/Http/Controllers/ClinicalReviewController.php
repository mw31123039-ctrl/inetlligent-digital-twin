<?php

namespace App\Http\Controllers;

use App\Models\ClinicalAssessment;
use App\Models\ReviewItem;
use App\Services\AuditLog;
use App\Services\ClinicalAiService;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Validation\Rule;

/**
 * Expert feedback queue. Reviewers (role assigned server-side) propose corrections to findings, citations,
 * anatomical mappings, question selection, red flags or translations; a different reviewer decides.
 * Reviewers only see assessments that patients explicitly shared, in a de-identified form.
 */
class ClinicalReviewController extends Controller
{
    public function __construct(private AuditLog $audit, private ClinicalAiService $ai) {}

    private function reviewer(Request $request): int
    {
        abort_unless($request->user()->isReviewer(), 403, 'Only assigned clinical reviewers can use the review queue.');

        return $request->user()->id;
    }

    public function index(Request $request): JsonResponse
    {
        $this->reviewer($request);
        $status = $request->validate(['status' => ['sometimes', Rule::in(['pending', 'accepted', 'rejected'])]])['status'] ?? 'pending';
        $items = ReviewItem::where('status', $status)->latest()->limit(200)->get();

        return response()->json(['items' => $items->map(fn (ReviewItem $item) => $this->present($item))->values()]);
    }

    public function store(Request $request): JsonResponse
    {
        $reviewerId = $this->reviewer($request);
        $data = $request->validate([
            'target_type' => ['required', Rule::in(ReviewItem::TARGET_TYPES)],
            'target_ref' => ['required', 'string', 'regex:/\A[A-Za-z0-9_.:#~\-]{1,120}\z/'],
            'current' => 'nullable|string|max:1000',
            'proposed' => 'required|string|min:3|max:2000',
            'rationale' => 'required|string|min:10|max:2000',
            'evidence_url' => 'nullable|url:https|max:500',
            'shared_assessment_id' => 'nullable|uuid',
        ]);
        if (isset($data['shared_assessment_id'])) {
            abort_unless(ClinicalAssessment::whereNotNull('review_shared_at')->whereKey($data['shared_assessment_id'])->exists(), 404);
        }
        $versions = $this->ai->catalog()['versions'];
        $item = ReviewItem::create([
            'reviewer_id' => $reviewerId, 'target_type' => $data['target_type'], 'target_ref' => $data['target_ref'],
            'knowledge_version' => $versions['knowledge'], 'engine_version' => $versions['engine'] ?? 'unknown',
            'shared_assessment_id' => $data['shared_assessment_id'] ?? null, 'status' => 'pending',
            'payload' => ['current' => $data['current'] ?? null, 'proposed' => $data['proposed'], 'rationale' => $data['rationale'], 'evidence_url' => $data['evidence_url'] ?? null],
        ]);
        $this->audit->record('review.item_created', null, $reviewerId, 'review_item', $item->id, ['target_type' => $item->target_type]);

        return response()->json($this->present($item), 201);
    }

    public function decide(Request $request, string $id): JsonResponse
    {
        $reviewerId = $this->reviewer($request);
        $data = $request->validate(['decision' => ['required', Rule::in(['accepted', 'rejected'])], 'note' => 'nullable|string|max:1000']);
        $item = ReviewItem::findOrFail($id);
        abort_if($item->reviewer_id === $reviewerId, 403, 'A different reviewer must decide on this correction.');
        abort_unless($item->status === 'pending', 409, 'This correction was already decided.');
        $item->update(['status' => $data['decision'], 'decided_by' => $reviewerId, 'decided_at' => now(), 'payload' => [...$item->payload, 'decision_note' => $data['note'] ?? null]]);
        $this->audit->record('review.item_decided', null, $reviewerId, 'review_item', $item->id, ['decision' => $data['decision']]);

        return response()->json($this->present($item));
    }

    /**
     * De-identified view of patient-shared assessments: structured findings only, no free text, quotes or
     * account details, owner identifiers or exact dates. The case code is a keyed hash for discussion.
     */
    public function cases(Request $request): JsonResponse
    {
        $reviewerId = $this->reviewer($request);
        $records = ClinicalAssessment::whereNotNull('review_shared_at')->latest('review_shared_at')->limit(100)->get();
        foreach ($records as $record) {
            $this->audit->record('review.case_viewed', $record->user_id, $reviewerId, 'clinical_assessment', $record->id);
        }

        return response()->json(['cases' => $records->map(fn (ClinicalAssessment $record) => $this->deidentified($record))->values()]);
    }

    /**
     * @return array<string, mixed>
     */
    private function deidentified(ClinicalAssessment $record): array
    {
        $assessment = $record->payload['assessment'];
        $structured = ['symptom', 'attribute', 'trigger', 'screen'];

        return [
            'case_code' => substr(hash_hmac('sha256', 'review-case:'.$record->id, config('app.key')), 0, 16),
            'assessment_id' => $record->id,
            'shared_month' => $record->review_shared_at->format('Y-m'),
            'locale' => $record->payload['locale'],
            'anatomy' => $assessment['anatomy'],
            'urgency' => ['level' => $assessment['urgency']['level'], 'rule_ids' => array_column($assessment['urgency']['reasons'], 'rule_id')],
            'facts' => array_values(array_map(fn (array $fact) => ['id' => $fact['id'], 'kind' => $fact['kind'], 'key' => $fact['key'], 'status' => $fact['status'], 'provenance' => $fact['provenance'], 'extractor' => $fact['extractor']],
                array_filter($assessment['patient_facts'], fn (array $fact) => in_array($fact['kind'], $structured, true)))),
            'questions_asked' => array_values(array_filter(array_column(array_filter($record->payload['messages'], fn (array $m) => $m['role'] === 'assistant'), 'question_id'))),
            'explanations' => array_map(fn (array $item) => ['condition_id' => $item['condition_id'], 'fit' => $item['fit'], 'supporting' => array_map(fn (array $e) => $e['citation_ids'], $item['supporting'])], $assessment['possible_explanations']),
            'citations' => array_map(fn (array $c) => ['id' => $c['id'], 'chunk_id' => $c['chunk_id'], 'quote' => $c['quote']], $assessment['citations']),
            'versions' => $assessment['versions'],
        ];
    }

    /**
     * @return array<string, mixed>
     */
    private function present(ReviewItem $item): array
    {
        return [
            'id' => $item->id, 'reviewer_id' => $item->reviewer_id, 'target_type' => $item->target_type, 'target_ref' => $item->target_ref,
            'knowledge_version' => $item->knowledge_version, 'engine_version' => $item->engine_version, 'shared_assessment_id' => $item->shared_assessment_id,
            'status' => $item->status, 'decided_by' => $item->decided_by, 'decided_at' => $item->decided_at?->toIso8601String(), 'created_at' => $item->created_at->toIso8601String(),
            ...$item->payload,
        ];
    }
}
