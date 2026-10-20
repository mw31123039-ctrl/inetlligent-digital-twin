<?php

namespace App\Http\Controllers;

use App\Models\User;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Auth;
use Illuminate\Validation\ValidationException;

class SessionController extends Controller
{
    public function register(Request $request)
    {
        abort_unless($request->hasSession(), 403, 'Use the first-party application with CSRF protection.');
        $data = $request->validate(['email' => 'required|email|max:254|unique:users,email', 'password' => 'required|string|min:12|max:128']);
        // No name, birth date, address, or medical profile is requested.
        $user = User::create(['name' => 'Member', ...$data]);
        Auth::login($user);
        $request->session()->regenerate();
        return response()->json(['user' => ['id' => $user->id, 'email' => $user->email]], 201);
    }

    public function login(Request $request)
    {
        abort_unless($request->hasSession(), 403, 'Use the first-party application with CSRF protection.');
        $data = $request->validate(['email' => 'required|email', 'password' => 'required|string|max:128']);
        if (!Auth::attempt($data)) {
            throw ValidationException::withMessages(['email' => 'The email or password is incorrect.']);
        }
        $request->session()->regenerate();
        return response()->json(['user' => ['id' => $request->user()->id, 'email' => $request->user()->email]]);
    }

    public function logout(Request $request)
    {
        Auth::guard('web')->logout();
        $request->session()->invalidate();
        $request->session()->regenerateToken();
        return response()->noContent();
    }
}
