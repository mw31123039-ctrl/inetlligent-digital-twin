<?php

use App\Models\PatientFact;
use App\Models\User;
use App\Services\AuditLog;
use Illuminate\Foundation\Inspiring;
use Illuminate\Support\Facades\Artisan;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schedule;

Artisan::command('conversations:prune', function () {
    DB::table('conversation_sessions')->where('expires_at', '<', now())->delete();
    $this->info('Expired non-health session metadata removed.');
});
Schedule::command('conversations:prune')->hourly();

Artisan::command('clinical:prune', function () {
    DB::table('clinical_sessions')->where('expires_at', '<', now())->delete();
    $expired = PatientFact::whereNotNull('expires_at')->where('expires_at', '<', now())->delete();
    if ($expired > 0) {
        app(AuditLog::class)->record('memory.retention_expired', null, null, 'patient_memory', null, ['items_deleted' => $expired]);
    }
    $this->info("Expired clinical drafts removed; {$expired} memory items past retention deleted.");
})->purpose('Remove expired clinical drafts and patient-memory items past their retention period');
Schedule::command('clinical:prune')->hourly();

Artisan::command('humantwin:reviewer {email} {--revoke}', function (string $email) {
    $user = User::where('email', $email)->first();
    if (! $user) {
        $this->error('No account with that email.');

        return 1;
    }
    $user->forceFill(['role' => $this->option('revoke') ? 'patient' : 'reviewer'])->save();
    app(AuditLog::class)->record($this->option('revoke') ? 'review.role_revoked' : 'review.role_granted', $user->id, null, 'user', (string) $user->id);
    $this->info($this->option('revoke') ? 'Reviewer role removed.' : 'Reviewer role granted. Verify the person\'s professional registration separately.');

    return 0;
})->purpose('Grant or revoke the clinical reviewer role (server-side only)');

Artisan::command('inspire', function () {
    $this->comment(Inspiring::quote());
})->purpose('Display an inspiring quote');
