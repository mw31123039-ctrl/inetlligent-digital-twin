<?php

namespace App\Http\Controllers;

use Illuminate\Http\JsonResponse;

class DentalCoachController extends Controller
{
    public function review(): JsonResponse
    {
        return response()->json(['message' => 'External dental AI is disabled. Use the local sourced learning library and local outline tools.'], 503);
    }
}
