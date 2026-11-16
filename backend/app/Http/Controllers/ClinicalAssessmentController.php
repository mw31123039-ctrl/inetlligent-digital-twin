<?php

namespace App\Http\Controllers;

use App\Models\ClinicalAssessment;
use App\Services\AuditLog;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Http\Response;
use Illuminate\Validation\Rule;

/**
 * Saved clinical assessments: owner-only timeline, detail, deletion and optional sharing of a
 * de-identified copy with expert reviewers.
 */
class ClinicalAssessmentController extends Controller
{
    public const REVIEW_CONSENT_VERSION = 'clinical-review-share-v1';

    public function __construct(private AuditLog $audit) {}

    public function index(Request $request): JsonResponse
    {
        $records = ClinicalAssessment::where('user_id', $request->user()->id)->latest()->limit(100)->get();

        return response()->json(['assessments' => $records->map(fn (ClinicalAssessment $record) => $this->summary($record))->values()]);
    }

    public function show(Request $request, string $id): JsonResponse
    {
        $record = ClinicalAssessment::where('user_id', $request->user()->id)->findOrFail($id);
        $this->audit->record('clinical.assessment_viewed', $record->user_id, $request->user()->id, 'clinical_assessment', $record->id);

        return response()->json([...$this->summary($record), 'messages' => $record->payload['messages'], 'assessment' => $record->payload['assessment']]);
    }

    public function destroy(Request $request, string $id): Response
    {
        $record = ClinicalAssessment::where('user_id', $request->user()->id)->findOrFail($id);
        $record->delete();
        $this->audit->record('clinical.assessment_deleted', $request->user()->id, $request->user()->id, 'clinical_assessment', $id);

        return response()->noContent();
    }

    public function share(Request $request, string $id): JsonResponse
    {
        $data = $request->validate(['consent' => 'required|accepted', 'consent_version' => ['required', Rule::in([self::REVIEW_CONSENT_VERSION])]]);
        $record = ClinicalAssessment::where('user_id', $request->user()->id)->findOrFail($id);
        $record->update(['review_shared_at' => now(), 'review_consent_version' => $data['consent_version']]);
        $this->audit->record('clinical.assessment_shared_for_review', $record->user_id, $request->user()->id, 'clinical_assessment', $record->id);

        return response()->json(['id' => $record->id, 'review_shared' => true]);
    }

    public function unshare(Request $request, string $id): JsonResponse
    {
        $record = ClinicalAssessment::where('user_id', $request->user()->id)->findOrFail($id);
        $record->update(['review_shared_at' => null, 'review_consent_version' => null]);
        $this->audit->record('clinical.assessment_review_share_withdrawn', $record->user_id, $request->user()->id, 'clinical_assessment', $record->id);

        return response()->json(['id' => $record->id, 'review_shared' => false]);
    }

    /**
     * @return array<string, mixed>
     */
    private function summary(ClinicalAssessment $record): array
    {
        $assessment = $record->payload['assessment'];

        return [
            'id' => $record->id,
            'created_at' => $record->created_at->toIso8601String(),
            'locale' => $record->payload['locale'],
            'anatomy' => $assessment['anatomy'],
            'anatomy_label' => collect($assessment['anatomical_references'])->firstWhere('role', 'selected')['label'] ?? $assessment['anatomy']['id'],
            'urgency' => $assessment['urgency']['level'],
            'pathway_label' => $assessment['urgency']['pathway_label'],
            'explanations' => array_map(fn (array $item) => ['condition_id' => $item['condition_id'], 'name' => $item['name'], 'fit' => $item['fit']], $assessment['possible_explanations']),
            'versions' => $assessment['versions'],
            'previous_id' => $record->payload['previous_id'] ?? null,
            'review_shared' => $record->review_shared_at !== null,
        ];
    }
}
