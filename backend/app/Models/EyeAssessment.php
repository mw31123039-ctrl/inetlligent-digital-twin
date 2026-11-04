<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;

class EyeAssessment extends Model
{
    protected $guarded = [];
    public $incrementing = false;
    protected $keyType = 'string';

    protected function casts(): array
    {
        return ['payload' => 'encrypted:array', 'consented_at' => 'datetime'];
    }
}
