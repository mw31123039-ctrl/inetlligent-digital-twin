<?php

namespace Tests\Feature;

use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\Http;
use Tests\TestCase;

class DentalCoachTest extends TestCase
{
    use RefreshDatabase;

    public function test_external_review_returns_503_without_forwarding_private_content(): void
    {
        $this->withHeaders(['Origin' => 'http://127.0.0.1:5173']);
        Http::preventStrayRequests();
        $this->postJson('/api/dental/coach', [])->assertUnauthorized();
        $this->actingAs(User::factory()->create());
        $this->postJson('/api/dental/coach', ['question' => 'PRIVATE question', 'notes' => 'PRIVATE notes', 'consent_external' => true])
            ->assertServiceUnavailable()->assertSee('disabled')->assertDontSee('PRIVATE')->assertHeader('Cache-Control', 'no-store, private');
        Http::assertNothingSent();
        $this->assertDatabaseCount('health_assessments', 0);
    }
}
