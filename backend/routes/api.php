<?php

use App\Http\Controllers\ConversationController;
use App\Http\Controllers\SessionController;
use App\Services\AiService;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Route;

Route::get('/status', fn (AiService $ai) => $ai->status())->middleware('throttle:service-status');
Route::post('/register', [SessionController::class, 'register'])->middleware('throttle:auth-register');
Route::post('/login', [SessionController::class, 'login'])->middleware('throttle:auth-login');
Route::middleware(['auth:sanctum', 'throttle:private-api'])->group(function () {
    Route::get('/me', fn (Request $request) => ['user' => ['id' => $request->user()->id, 'email' => $request->user()->email]]);
    Route::post('/logout', [SessionController::class, 'logout']);
    Route::post('/conversations', [ConversationController::class, 'store']);
    Route::post('/conversations/{id}/turns', [ConversationController::class, 'turn'])->middleware('throttle:ai-turns');
    Route::post('/conversations/{id}/save', [ConversationController::class, 'save']);
    Route::delete('/conversations/{id}', [ConversationController::class, 'destroy']);
    Route::get('/assessments', [ConversationController::class, 'index']);
    Route::get('/assessments/{id}', [ConversationController::class, 'show']);
    Route::delete('/assessments/{id}', [ConversationController::class, 'destroy']);
});
