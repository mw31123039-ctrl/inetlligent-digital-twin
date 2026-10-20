<?php

use Illuminate\Foundation\Application;
use Illuminate\Foundation\Configuration\Exceptions;
use Illuminate\Foundation\Configuration\Middleware;
use Illuminate\Http\Request;

return Application::configure(basePath: dirname(__DIR__))
    ->withRouting(
        web: __DIR__.'/../routes/web.php',
        api: __DIR__.'/../routes/api.php',
        commands: __DIR__.'/../routes/console.php',
        health: '/up',
    )
    ->withMiddleware(function (Middleware $middleware): void {
        $middleware->statefulApi();
        $middleware->redirectGuestsTo(null);
        $middleware->api(append: [\App\Http\Middleware\PrivateApi::class]);
    })
    ->withExceptions(function (Exceptions $exceptions): void {
        $exceptions->report(function (\Throwable $exception) {
            if (request()->is('api/*')) {
                \Illuminate\Support\Facades\Log::error('API exception', ['type' => $exception::class]);
                return false;
            }
        });
        $exceptions->render(function (\Throwable $exception, Request $request) {
            if ($request->is('api/*') && !($exception instanceof \Illuminate\Validation\ValidationException)
                && !($exception instanceof \Illuminate\Auth\AuthenticationException)
                && !($exception instanceof \Illuminate\Database\Eloquent\ModelNotFoundException)
                && !($exception instanceof \Symfony\Component\HttpKernel\Exception\HttpExceptionInterface)) {
                return response()->json(['message' => 'The service could not complete this request. Please retry.'], 503);
            }
        });
        $exceptions->respond(function (\Symfony\Component\HttpFoundation\Response $response) {
            if (request()->is('api/*')) $response->headers->set('Cache-Control', 'no-store, private');
            return $response;
        });
        // Never log raw provider/HTTP exceptions containing health request data.
        $exceptions->dontReport([\Illuminate\Http\Client\RequestException::class, \Illuminate\Http\Client\ConnectionException::class]);
        $exceptions->dontFlash(['password', 'password_confirmation', 'text', 'token', 'messages', 'assessment', 'payload']);
        $exceptions->shouldRenderJsonWhen(
            fn (Request $request) => $request->is('api/*') || $request->expectsJson(),
        );
    })->create();
