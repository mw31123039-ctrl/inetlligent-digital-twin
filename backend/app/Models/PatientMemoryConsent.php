<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;

/**
 * Explicit, revocable consent for the assistant to remember a patient's history between sessions.
 */
class PatientMemoryConsent extends Model
{
    public const VERSION = 'patient-memory-v1';

    protected $primaryKey = 'user_id';

    public $incrementing = false;

    protected $guarded = [];

    protected function casts(): array
    {
        return ['consented_at' => 'datetime', 'retention_days' => 'integer'];
    }
}
