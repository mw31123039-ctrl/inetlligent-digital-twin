<?php

namespace App\Http\Middleware;

use Closure;
use Illuminate\Auth\AuthenticationException;
use Illuminate\Database\Eloquent\ModelNotFoundException;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Log;
use Illuminate\Validation\ValidationException;
use Symfony\Component\HttpFoundation\Response;
use Symfony\Component\HttpKernel\Exception\HttpExceptionInterface;

class PrivateApi
{
    public function handle(Request $request, Closure $next): Response
    {
        $maxBytes = $request->isMethod('POST') && $request->path() === 'api/dental/screening/cases' ? 2300000 : 500000;
        if ($request->isMethod('POST') && $request->path() === 'api/cancer/analyze') {
            $maxBytes = 1600000;
        }
        if ($request->isMethod('POST') && $request->path() === 'api/clinical/documents') {
            $maxBytes = 5400000;
        }
        if ($request->isMethod('POST') && str_starts_with($request->path(), 'api/clinical/sessions/')) {
            $maxBytes = 480000; // encrypted conversation token plus one answer
        }
        abort_if((int) $request->header('Content-Length', 0) > $maxBytes, 413, 'Request too large.');
        try {
            $response = $next($request);
        } catch (ValidationException|AuthenticationException|ModelNotFoundException|HttpExceptionInterface $exception) {
            throw $exception;
        } catch (\Throwable $exception) {
            // Operational visibility without message, stack arguments, request body or SQL.
            Log::error('API operation failed', ['type' => $exception::class]);
            $response = response()->json(['message' => 'The service could not complete this request. Please retry.'], 503);
        }
        $response->headers->set('Cache-Control', 'no-store, private');
        $response->headers->set('X-Content-Type-Options', 'nosniff');
        $response->headers->set('Referrer-Policy', 'no-referrer');

        return $response;
    }
}
