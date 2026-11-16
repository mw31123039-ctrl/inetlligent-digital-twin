<?php

namespace App\Http\Controllers;

use App\Models\ClinicalAssessment;
use App\Models\PatientFact;
use App\Models\PatientMemoryConsent;
use App\Services\AuditLog;
use App\Services\ClinicalAiService;
use App\Services\PatientMemory;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Http\Response;
use Illuminate\Support\Facades\DB;
use Illuminate\Validation\Rule;

/**
 * Consented patient memory: the patient can inspect, add, correct (with history), confirm document
 * extracts, export and delete everything the assistant remembers. Revoking consent deletes it all.
 */
class PatientMemoryController extends Controller
{
    private const RETENTION_OPTIONS = [30, 90, 365, 730];

    public function __construct(private PatientMemory $memory, private AuditLog $audit, private ClinicalAiService $ai) {}

    public function show(Request $request): JsonResponse
    {
        $userId = $request->user()->id;
        $consent = $this->memory->consent($userId);
        $facts = PatientFact::where('user_id', $userId)->latest()->limit(200)->get();
        $this->audit->record('memory.viewed', $userId, $userId, 'patient_memory', null, ['items' => $facts->count()]);

        return response()->json([
            'consent' => $consent ? ['version' => $consent->consent_version, 'consented_at' => $consent->consented_at->toIso8601String(), 'retention_days' => $consent->retention_days] : null,
            'facts' => $facts->map(fn (PatientFact $fact) => $this->present($fact))->values(),
        ]);
    }

    public function consent(Request $request): JsonResponse
    {
        $data = $request->validate([
            'consent' => 'required|accepted',
            'consent_version' => ['required', Rule::in([PatientMemoryConsent::VERSION])],
            'retention_days' => ['required', 'integer', Rule::in(self::RETENTION_OPTIONS)],
        ]);
        $userId = $request->user()->id;
        PatientMemoryConsent::updateOrCreate(['user_id' => $userId], ['consent_version' => $data['consent_version'], 'consented_at' => now(), 'retention_days' => $data['retention_days']]);
        PatientFact::where('user_id', $userId)->whereNotNull('expires_at')->where('status', '!=', 'pending_confirmation')->update(['expires_at' => now()->addDays($data['retention_days'])]);
        $this->audit->record('memory.consent_granted', $userId, $userId, 'patient_memory', null, ['retention_days' => $data['retention_days']]);

        return response()->json(['consent' => true, 'retention_days' => $data['retention_days']]);
    }

    public function revoke(Request $request): Response
    {
        $userId = $request->user()->id;
        $deleted = DB::transaction(function () use ($userId) {
            $count = PatientFact::where('user_id', $userId)->delete();
            PatientMemoryConsent::where('user_id', $userId)->delete();

            return $count;
        });
        $this->audit->record('memory.consent_revoked_and_deleted', $userId, $userId, 'patient_memory', null, ['items_deleted' => $deleted]);

        return response()->noContent();
    }

    public function store(Request $request): JsonResponse
    {
        $data = $this->validateFact($request);
        $userId = $request->user()->id;
        abort_unless($this->memory->consent($userId), 403, 'Turn on patient memory before saving history.');
        $fact = PatientFact::create([
            'user_id' => $userId, 'kind' => $data['kind'], 'status' => $data['status'] ?? 'active', 'provenance' => 'patient_memory', 'source_type' => 'manual',
            'payload' => ['label' => $data['label'], 'details' => $data['details'] ?? null, 'anatomy_id' => $data['anatomy_id'] ?? null, 'recorded_at' => now()->toIso8601String(), 'location' => null, 'document_sha256' => null],
            'expires_at' => $this->memory->expiry($userId),
        ]);
        $this->audit->record('memory.fact_added', $userId, $userId, 'patient_fact', $fact->id, ['kind' => $fact->kind, 'source' => 'manual']);

        return response()->json($this->present($fact), 201);
    }

    /**
     * Copy selected answers (medicines, allergies, history) from a saved assessment into memory.
     */
    public function importFromAssessment(Request $request): JsonResponse
    {
        $data = $request->validate(['assessment_id' => 'required|uuid', 'fact_ids' => 'required|array|min:1|max:10', 'fact_ids.*' => 'string|max:120']);
        $userId = $request->user()->id;
        abort_unless($this->memory->consent($userId), 403, 'Turn on patient memory before saving history.');
        $record = ClinicalAssessment::where('user_id', $userId)->findOrFail($data['assessment_id']);
        $kinds = ['medication' => 'medication', 'allergy' => 'allergy', 'history' => 'condition'];
        $created = [];
        foreach ($record->payload['assessment']['patient_facts'] as $fact) {
            if (! in_array($fact['id'], $data['fact_ids'], true) || ! isset($kinds[$fact['kind']]) || $fact['status'] !== 'present' || $fact['provenance'] !== 'patient_answer') {
                continue;
            }
            $created[] = PatientFact::create([
                'user_id' => $userId, 'kind' => $kinds[$fact['kind']], 'status' => 'active', 'provenance' => 'patient_memory', 'source_type' => 'assessment', 'source_ref' => $record->id,
                'payload' => ['label' => mb_substr($fact['value'], 0, 200), 'details' => null, 'anatomy_id' => null, 'recorded_at' => $record->created_at->toIso8601String(), 'location' => null, 'document_sha256' => null],
                'expires_at' => $this->memory->expiry($userId),
            ]);
        }
        abort_if($created === [], 422, 'Only your own answers about medicines, allergies or past conditions can be remembered.');
        $this->audit->record('memory.facts_imported', $userId, $userId, 'clinical_assessment', $record->id, ['items' => count($created)]);

        return response()->json(['facts' => array_map(fn (PatientFact $fact) => $this->present($fact), $created)], 201);
    }

    /**
     * Corrections never overwrite history: a new item supersedes the old one, which stays visible as corrected.
     */
    public function update(Request $request, string $id): JsonResponse
    {
        $data = $this->validateFact($request, partial: true);
        $userId = $request->user()->id;
        $old = PatientFact::where('user_id', $userId)->whereIn('status', ['active', 'resolved'])->findOrFail($id);
        $new = DB::transaction(function () use ($old, $data, $userId) {
            $old->update(['status' => 'corrected']);

            return PatientFact::create([
                'user_id' => $userId, 'kind' => $data['kind'] ?? $old->kind, 'status' => $data['status'] ?? $old->status, 'provenance' => 'patient_memory', 'source_type' => 'correction',
                'source_ref' => $old->source_ref, 'supersedes_id' => $old->id,
                'payload' => [...$old->payload, 'label' => $data['label'] ?? $old->payload['label'], 'details' => array_key_exists('details', $data) ? $data['details'] : $old->payload['details'], 'recorded_at' => now()->toIso8601String()],
                'confirmed_at' => $old->confirmed_at, 'expires_at' => $this->memory->expiry($userId),
            ]);
        });
        $this->audit->record('memory.fact_corrected', $userId, $userId, 'patient_fact', $new->id, ['supersedes' => $old->id]);

        return response()->json($this->present($new));
    }

    public function confirm(Request $request, string $id): JsonResponse|Response
    {
        $data = $request->validate(['decision' => ['required', Rule::in(['confirm', 'reject'])], 'label' => 'sometimes|string|min:1|max:200']);
        $userId = $request->user()->id;
        $fact = PatientFact::where('user_id', $userId)->where('status', 'pending_confirmation')->findOrFail($id);
        if ($data['decision'] === 'reject') {
            $fact->delete();
            $this->audit->record('memory.extract_rejected', $userId, $userId, 'patient_fact', $id);

            return response()->noContent();
        }
        $fact->update(['status' => 'active', 'confirmed_at' => now(), 'expires_at' => $this->memory->expiry($userId),
            'payload' => [...$fact->payload, 'label' => $data['label'] ?? $fact->payload['label']]]);
        $this->audit->record('memory.extract_confirmed', $userId, $userId, 'patient_fact', $fact->id, ['edited' => isset($data['label'])]);

        return response()->json($this->present($fact));
    }

    public function destroy(Request $request, string $id): Response
    {
        $userId = $request->user()->id;
        $fact = PatientFact::where('user_id', $userId)->findOrFail($id);
        $ids = [$fact->id];
        $cursor = $fact;
        while ($cursor->supersedes_id && ($cursor = PatientFact::where('user_id', $userId)->find($cursor->supersedes_id))) {
            $ids[] = $cursor->id; // deleting an item also deletes its correction history
        }
        PatientFact::where('user_id', $userId)->whereIn('id', $ids)->delete();
        $this->audit->record('memory.fact_deleted', $userId, $userId, 'patient_fact', $id, ['items_deleted' => count($ids)]);

        return response()->noContent();
    }

    public function export(Request $request): JsonResponse
    {
        $userId = $request->user()->id;
        $this->audit->record('memory.exported', $userId, $userId, 'patient_memory');

        return response()->json([
            'exported_at' => now()->toIso8601String(),
            'consent' => $this->memory->consent($userId)?->only(['consent_version', 'consented_at', 'retention_days']),
            'facts' => PatientFact::where('user_id', $userId)->oldest()->get()->map(fn (PatientFact $fact) => $this->present($fact))->values(),
        ], 200, ['Content-Disposition' => 'attachment; filename="humantwin-patient-memory.json"']);
    }

    /**
     * @return array<string, mixed>
     */
    private function validateFact(Request $request, bool $partial = false): array
    {
        $required = $partial ? 'sometimes' : 'required';

        return $request->validate([
            'kind' => [$required, Rule::in(PatientFact::KINDS)],
            'label' => [$required, 'string', 'min:1', 'max:200'],
            'details' => 'sometimes|nullable|string|max:500',
            'status' => ['sometimes', Rule::in(['active', 'resolved'])],
            'anatomy_id' => ['sometimes', 'nullable', Rule::in($this->ai->anatomyIds())],
        ]);
    }

    /**
     * @return array<string, mixed>
     */
    private function present(PatientFact $fact): array
    {
        return [
            'id' => $fact->id, 'kind' => $fact->kind, 'status' => $fact->status, 'provenance' => $fact->provenance, 'source_type' => $fact->source_type,
            'source_ref' => $fact->source_ref, 'supersedes_id' => $fact->supersedes_id, 'label' => $fact->payload['label'], 'details' => $fact->payload['details'] ?? null,
            'anatomy_id' => $fact->payload['anatomy_id'] ?? null, 'location' => $fact->payload['location'] ?? null,
            'confirmed_at' => $fact->confirmed_at?->toIso8601String(), 'expires_at' => $fact->expires_at?->toIso8601String(),
            'created_at' => $fact->created_at->toIso8601String(), 'updated_at' => $fact->updated_at->toIso8601String(),
        ];
    }
}
