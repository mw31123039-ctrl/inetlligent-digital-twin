<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;

/**
 * Append-only access/change log. Never contains health content: only who, what action, which record.
 */
class AuditEvent extends Model
{
    public const UPDATED_AT = null;

    protected $guarded = [];

    protected function casts(): array
    {
        return ['meta' => 'array', 'created_at' => 'datetime'];
    }
}
