<?php

namespace App\Services;

class DentalOwner
{
    public static function token(int $userId): string
    {
        return hash_hmac('sha256', 'dental-owner:'.$userId, (string) config('app.key'));
    }
}
