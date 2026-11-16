<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Concerns\HasUuids;
use Illuminate\Database\Eloquent\Model;

/**
 * A consented, server-recomputed clinical assessment v2 snapshot.
 *
 * @property array{messages: array<int, array<string, mixed>>, assessment: array<string, mixed>, locale: string, anatomy: array{id: string, side: string}, previous_id: string|null} $payload
 */
class ClinicalAssessment extends Model
{
    use HasUuids;

    protected $guarded = [];

    protected function casts(): array
    {
        return ['payload' => 'encrypted:array', 'consented_at' => 'datetime', 'review_shared_at' => 'datetime'];
    }
}
