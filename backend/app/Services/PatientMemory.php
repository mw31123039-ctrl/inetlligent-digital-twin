<?php

namespace App\Services;

use App\Models\PatientFact;
use App\Models\PatientMemoryConsent;

/**
 * Consented patient history that may be shared with the assessment engine for continuity.
 * Only active or confirmed items are shared; pending document extracts never are.
 */
class PatientMemory
{
    public function consent(int $userId): ?PatientMemoryConsent
    {
        return PatientMemoryConsent::find($userId);
    }

    /**
     * @return array<int, array{id: string, kind: string, label: string, status: string, provenance: string, recorded_at: string|null}>
     */
    public function context(int $userId): array
    {
        if (! $this->consent($userId)) {
            return [];
        }

        return PatientFact::where('user_id', $userId)->whereIn('status', ['active', 'resolved'])
            ->where(fn ($query) => $query->whereNull('expires_at')->orWhere('expires_at', '>', now()))
            ->latest()->limit(60)->get()
            ->map(fn (PatientFact $fact) => [
                'id' => $fact->id,
                'kind' => $fact->kind,
                'label' => mb_substr($fact->payload['label'], 0, 200),
                'status' => $fact->status === 'resolved' ? 'resolved' : 'active',
                'provenance' => $fact->provenance === 'clinician_confirmed' ? 'clinician_confirmed' : ($fact->provenance === 'document_extract' ? 'document_extract' : 'patient_memory'),
                'recorded_at' => $fact->created_at?->toIso8601String(),
            ])->values()->all();
    }

    public function expiry(int $userId): ?\DateTimeInterface
    {
        $consent = $this->consent($userId);

        return $consent ? now()->addDays($consent->retention_days) : null;
    }
}
