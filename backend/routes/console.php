<?php

use Illuminate\Foundation\Inspiring;
use Illuminate\Support\Facades\Artisan;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schedule;

Artisan::command('conversations:prune', function () {
    DB::table('conversation_sessions')->where('expires_at', '<', now())->delete();
    $this->info('Expired non-health session metadata removed.');
});
Schedule::command('conversations:prune')->hourly();

Artisan::command('inspire', function () {
    $this->comment(Inspiring::quote());
})->purpose('Display an inspiring quote');
