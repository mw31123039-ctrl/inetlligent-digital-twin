<?php

use App\Http\Middleware\PrivateApi;
use Illuminate\Auth\AuthenticationException;
use Illuminate\Database\Eloquent\ModelNotFoundException;
use Illuminate\Foundation\Application;
use Illuminate\Foundation\Configuration\Exceptions;
use Illuminate\Foundation\Configuration\Middleware;
use Illuminate\Http\Client\ConnectionException;
use Illuminate\Http\Client\RequestException;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Log;
use Illuminate\Validation\ValidationException;
use Symfony\Component\HttpFoundation\Response;
use Symfony\Component\HttpKernel\Exception\HttpExceptionInterface;

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
        $middleware->api(append: [PrivateApi::class]);
    })
    ->withExceptions(function (Exceptions $exceptions): void {
        $exceptions->report(function (Throwable $exception) {
            if (request()->is('api/*')) {
                Log::error('API exception', ['type' => $exception::class]);

                return false;
            }
        });
        $exceptions->render(function (Throwable $exception, Request $request) {
            if ($request->is('api/*') && ! ($exception instanceof ValidationException)
                && ! ($exception instanceof AuthenticationException)
                && ! ($exception instanceof ModelNotFoundException)
                && ! ($exception instanceof HttpExceptionInterface)) {
                return response()->json(['message' => 'The service could not complete this request. Please retry.'], 503);
            }
        });
        $exceptions->respond(function (Response $response) {
            if (request()->is('api/*')) {
                $response->headers->set('Cache-Control', 'no-store, private');
            }

            return $response;
        });
        // Never log raw provider/HTTP exceptions containing health request data.
        $exceptions->dontReport([RequestException::class, ConnectionException::class]);
        $exceptions->dontFlash(['password', 'password_confirmation', 'text', 'token', 'messages', 'assessment', 'payload', 'turns', 'reported', 'anatomy_explored', 'photo', 'photos', 'prompt', 'notes', 'question', 'reported_findings', 'subject_code', 'reviewer_code', 'crowns', 'visit_code', 'age_years', 'findings', 'classifications', 'review', 'rights_reference']);
        $exceptions->shouldRenderJsonWhen(
            fn (Request $request) => $request->is('api/*') || $request->expectsJson(),
        );
    })->create();
