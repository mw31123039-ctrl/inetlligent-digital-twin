<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Concerns\HasUuids;
use Illuminate\Database\Eloquent\Model;

/**
 * A saved research report: the exact model output returned to this user, a small preview
 * image and an optional note, encrypted at rest and stored only with explicit consent.
 *
 * @property array{result: array<string, mixed>, thumbnail_data_url: string, note: string|null} $payload
 */
class CancerReport extends Model
{
    use HasUuids;

    protected $guarded = [];

    protected function casts(): array
    {
        return ['payload' => 'encrypted:array', 'consented_at' => 'datetime'];
    }
}
