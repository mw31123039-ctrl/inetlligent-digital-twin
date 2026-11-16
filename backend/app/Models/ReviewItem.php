<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Concerns\HasUuids;
use Illuminate\Database\Eloquent\Model;

/**
 * An expert correction awaiting a second reviewer's decision. Accepted items are applied to the
 * versioned knowledge contracts by a maintainer; they never change model weights automatically.
 *
 * @property array{current: string|null, proposed: string, rationale: string, evidence_url: string|null} $payload
 */
class ReviewItem extends Model
{
    use HasUuids;

    public const TARGET_TYPES = ['finding', 'citation', 'anatomy_mapping', 'question_selection', 'red_flag', 'translation'];

    protected $guarded = [];

    protected function casts(): array
    {
        return ['payload' => 'encrypted:array', 'decided_at' => 'datetime'];
    }
}
