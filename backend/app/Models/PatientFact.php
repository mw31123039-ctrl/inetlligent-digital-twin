<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Concerns\HasUuids;
use Illuminate\Database\Eloquent\Model;

/**
 * One item of consented patient memory (condition, medication, allergy, procedure or risk factor).
 *
 * Plain columns hold only authorization/retention metadata. Labels, details and document locations
 * live in the encrypted payload.
 *
 * @property array{label: string, details: string|null, anatomy_id: string|null, recorded_at: string|null, location: array<string, mixed>|null, document_sha256: string|null} $payload
 */
class PatientFact extends Model
{
    use HasUuids;

    public const KINDS = ['condition', 'medication', 'allergy', 'procedure', 'risk_factor'];

    public const STATUSES = ['active', 'resolved', 'pending_confirmation', 'corrected', 'rejected'];

    protected $guarded = [];

    protected function casts(): array
    {
        return ['payload' => 'encrypted:array', 'confirmed_at' => 'datetime', 'expires_at' => 'datetime'];
    }
}
