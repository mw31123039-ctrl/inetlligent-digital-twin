<?php

namespace App\Http\Middleware;

use Closure;
use Illuminate\Http\Request;
use Symfony\Component\HttpFoundation\Response;

class PrivateApi
{
    public function handle(Request $request, Closure $next): Response
    {
        abort_if((int) $request->header('Content-Length', 0) > 500000, 413, 'Request too large.');
        try {
            $response = $next($request);
        } catch (\Illuminate\Validation\ValidationException|\Illuminate\Auth\AuthenticationException|\Illuminate\Database\Eloquent\ModelNotFoundException|\Symfony\Component\HttpKernel\Exception\HttpExceptionInterface $exception) {
            throw $exception;
        } catch (\Throwable $exception) {
            // Operational visibility without message, stack arguments, request body or SQL.
            \Illuminate\Support\Facades\Log::error('API operation failed', ['type' => $exception::class]);
            $response = response()->json(['message' => 'The service could not complete this request. Please retry.'], 503);
        }
        $response->headers->set('Cache-Control', 'no-store, private');
        $response->headers->set('X-Content-Type-Options', 'nosniff');
        $response->headers->set('Referrer-Policy', 'no-referrer');
        return $response;
    }
}
