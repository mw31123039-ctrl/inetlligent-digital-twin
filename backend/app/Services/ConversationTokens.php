<?php

namespace App\Services;

use Illuminate\Support\Facades\Crypt;
use Illuminate\Support\Facades\DB;
use Throwable;

class ConversationTokens
{
    public function encode(array $state): string
    {
        return Crypt::encryptString(json_encode($state, JSON_THROW_ON_ERROR));
    }

    public function decode(string $token, int $userId, string $id): array
    {
        try {
            $state = json_decode(Crypt::decryptString($token), true, flags: JSON_THROW_ON_ERROR);
        } catch (Throwable) {
            abort(422, 'Invalid conversation token. Start a new assessment.');
        }
        // Authorization precedes access to the stored metadata or payload.
        abort_unless(($state['user_id'] ?? null) === $userId && ($state['id'] ?? null) === $id, 404);
        $session = DB::table('conversation_sessions')->where('id', $id)->where('user_id', $userId)->first();
        abort_unless($session && now()->lt($session->expires_at), 410, 'This conversation expired or was deleted. Start a new assessment.');
        abort_unless($session->revision === $state['revision'], 409, 'This conversation has changed. Start a new assessment if the last reply was lost.');
        return $state;
    }
}
