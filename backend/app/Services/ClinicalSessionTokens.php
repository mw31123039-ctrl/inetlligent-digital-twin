<?php

namespace App\Services;

use Illuminate\Support\Facades\Crypt;
use Illuminate\Support\Facades\DB;
use Throwable;

/**
 * Draft clinical conversations live in an encrypted, owner-bound client token. The database keeps only
 * the session id, owner, revision and expiry, so no draft health content is stored before consent.
 */
class ClinicalSessionTokens
{
    /**
     * @param  array<string, mixed>  $state
     */
    public function encode(array $state): string
    {
        return Crypt::encryptString(json_encode($state, JSON_THROW_ON_ERROR));
    }

    /**
     * @return array<string, mixed>
     */
    public function decode(string $token, int $userId, string $id): array
    {
        try {
            $state = json_decode(Crypt::decryptString($token), true, flags: JSON_THROW_ON_ERROR);
        } catch (Throwable) {
            abort(422, 'Invalid conversation token. Start a new assessment.');
        }
        abort_unless(($state['user_id'] ?? null) === $userId && ($state['id'] ?? null) === $id && ($state['kind'] ?? null) === 'clinical-v2', 404);
        $session = DB::table('clinical_sessions')->where('id', $id)->where('user_id', $userId)->first();
        abort_unless($session && now()->lt($session->expires_at), 410, 'This conversation expired or was deleted. Start a new assessment.');
        abort_unless((int) $session->revision === $state['revision'], 409, 'This conversation has changed. Start a new assessment if the last reply was lost.');

        return $state;
    }

    public function advance(string $id, int $userId, int $revision): bool
    {
        return DB::table('clinical_sessions')->where('id', $id)->where('user_id', $userId)->where('revision', $revision)
            ->update(['revision' => $revision + 1]) === 1;
    }
}
