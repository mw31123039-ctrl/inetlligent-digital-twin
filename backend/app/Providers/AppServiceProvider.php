<?php

namespace App\Providers;

use Illuminate\Support\ServiceProvider;

class AppServiceProvider extends ServiceProvider
{
    /**
     * Register any application services.
     */
    public function register(): void
    {
        //
    }

    /**
     * Bootstrap any application services.
     */
    public function boot(): void
    {
        $limiter = \Illuminate\Support\Facades\RateLimiter::class;
        $limiter::for('auth-login', fn (\Illuminate\Http\Request $request) => [
            \Illuminate\Cache\RateLimiting\Limit::perMinute(6)->by('login:'.$request->ip().':'.hash('sha256', strtolower((string) $request->input('email')))),
            \Illuminate\Cache\RateLimiting\Limit::perMinute(30)->by('login-ip:'.$request->ip()),
        ]);
        $limiter::for('auth-register', fn (\Illuminate\Http\Request $request) => \Illuminate\Cache\RateLimiting\Limit::perMinute(6)->by('register:'.$request->ip()));
        $limiter::for('service-status', fn (\Illuminate\Http\Request $request) => \Illuminate\Cache\RateLimiting\Limit::perMinute(60)->by('status:'.$request->ip()));
        $limiter::for('private-api', fn (\Illuminate\Http\Request $request) => \Illuminate\Cache\RateLimiting\Limit::perMinute(60)->by('api:'.$request->user()?->id));
        $limiter::for('ai-turns', fn (\Illuminate\Http\Request $request) => \Illuminate\Cache\RateLimiting\Limit::perMinute(20)->by('turn:'.$request->user()?->id));
    }
}
