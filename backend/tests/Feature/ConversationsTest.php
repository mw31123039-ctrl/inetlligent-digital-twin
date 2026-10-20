<?php

namespace Tests\Feature;

use App\Models\User;
use App\Models\HealthAssessment;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Http\Client\Request as ClientRequest;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Http;
use Tests\TestCase;

class ConversationsTest extends TestCase
{
    use RefreshDatabase;

    protected function setUp(): void
    {
        parent::setUp();
        $this->withHeaders(['Origin' => 'http://127.0.0.1:5173']);
        Http::preventStrayRequests();
        $this->fakeAi();
    }

    private function fixture(): array { return json_decode(file_get_contents(base_path('tests/Fixtures/assessment.json')), true); }

    private function fakeAi(): void
    {
        Http::fake(function (ClientRequest $request) {
            $result = $this->fixture();
            $result['selected_region'] = $request['region'] ?? 'eyes';
            $result['side'] = $request['side'] ?? 'unknown';
            $users = array_values(array_filter($request['messages'] ?? [], fn ($item) => $item['role'] === 'user'));
            $result['reported_symptoms'] = array_column($users, 'text');
            $result['facts'] = array_map(fn ($message) => ['field' => 'symptoms', 'value' => $message['text'], 'quote' => $message['text'], 'message_id' => $message['id']], $users);
            $result['next_question'] = ['field' => 'warning_signs', 'text' => 'Are there any urgent warning signs?', 'options' => ['No', 'Yes']];
            return Http::response($result);
        });
    }

    private function begin(User $user, string $region = 'eyes'): array
    {
        return $this->actingAs($user)->postJson('/api/conversations', ['region' => $region, 'side' => 'left', 'processing_acknowledged' => true])->assertCreated()->json();
    }

    private function turn(array $chat, string $text, ?string $correction = null): array
    {
        return $this->postJson('/api/conversations/'.$chat['id'].'/turns', ['token' => $chat['token'], 'text' => $text, 'correct_message_id' => $correction])->assertOk()->json();
    }

    public function test_authentication_and_processing_acknowledgement_are_required(): void
    {
        $this->postJson('/api/conversations', [])->assertUnauthorized();
        $this->get('/api/me')->assertUnauthorized();
        $this->actingAs(User::factory()->create())->postJson('/api/conversations', ['region' => 'eyes', 'side' => 'left'])->assertUnprocessable();
        Http::assertNothingSent();
    }

    public function test_all_body_contexts_are_forwarded_and_drafts_store_no_health_content(): void
    {
        $user = User::factory()->create();
        foreach (['eyes', 'head', 'chest', 'abdomen', 'arms', 'legs'] as $region) {
            $chat = $this->begin($user, $region);
            $this->assertSame($region, $chat['assessment']['selected_region']);
            $this->assertSame('left', $chat['assessment']['side']);
        }
        $this->assertDatabaseCount('health_assessments', 0);
        $this->assertEqualsCanonicalizing(['id','user_id','revision','expires_at'], array_keys((array) DB::table('conversation_sessions')->first()));
    }

    public function test_correction_removes_derived_answers_before_reassessment(): void
    {
        $chat = $this->begin(User::factory()->create());
        $chat = $this->turn($chat, 'OLD dry feeling');
        $first = collect($chat['messages'])->firstWhere('role', 'user')['id'];
        $chat = $this->turn($chat, 'Later answer');
        $chat = $this->turn($chat, 'CORRECTED itchy feeling', $first);
        $users = collect($chat['messages'])->where('role', 'user')->pluck('text')->all();
        $this->assertSame(['CORRECTED itchy feeling'], $users);
        $this->assertStringNotContainsString('CORRECTED', $chat['token']);
        $this->assertDatabaseCount('health_assessments', 0);
    }

    public function test_save_requires_consent_and_encrypts_health_payload(): void
    {
        $chat = $this->turn($this->begin(User::factory()->create()), 'PRIVATE-HEALTH-CONTENT');
        $path = '/api/conversations/'.$chat['id'].'/save';
        $this->postJson($path, ['token' => $chat['token'], 'consent' => false, 'consent_version' => 'health-storage-v1'])->assertUnprocessable();
        $this->assertDatabaseCount('health_assessments', 0);
        $this->postJson($path, ['token' => $chat['token'], 'consent' => true, 'consent_version' => 'health-storage-v1'])->assertOk();
        $raw = DB::table('health_assessments')->value('payload');
        $this->assertStringNotContainsString('PRIVATE-HEALTH', $raw);
        $this->assertStringContainsString('PRIVATE-HEALTH', json_encode(HealthAssessment::first()->payload));
        $this->getJson('/api/assessments')->assertJsonCount(1);
    }

    public function test_other_users_cannot_read_edit_save_or_delete_a_conversation(): void
    {
        $alice = User::factory()->create(); $bob = User::factory()->create();
        $chat = $this->begin($alice);
        $this->postJson('/api/conversations/'.$chat['id'].'/save', ['token' => $chat['token'], 'consent' => true, 'consent_version' => 'health-storage-v1'])->assertOk();
        $this->actingAs($bob);
        $this->getJson('/api/assessments')->assertJsonCount(0);
        $this->getJson('/api/assessments/'.$chat['id'])->assertNotFound();
        $this->deleteJson('/api/conversations/'.$chat['id'])->assertNotFound();
        $this->postJson('/api/conversations/'.$chat['id'].'/turns', ['token' => $chat['token'], 'text' => 'Intrusion'])->assertNotFound();
        $this->postJson('/api/conversations/'.$chat['id'].'/save', ['token' => $chat['token'], 'consent' => true, 'consent_version' => 'health-storage-v1'])->assertNotFound();
        $this->assertDatabaseCount('health_assessments', 1);
    }

    public function test_deletion_removes_saved_payload_and_revokes_draft_tokens(): void
    {
        $chat = $this->begin(User::factory()->create());
        $this->postJson('/api/conversations/'.$chat['id'].'/save', ['token' => $chat['token'], 'consent' => true, 'consent_version' => 'health-storage-v1'])->assertOk();
        $this->deleteJson('/api/conversations/'.$chat['id'])->assertNoContent();
        $this->assertDatabaseCount('health_assessments', 0);
        $this->assertDatabaseCount('conversation_sessions', 0);
        $this->postJson('/api/conversations/'.$chat['id'].'/turns', ['token' => $chat['token'], 'text' => 'Replay'])->assertGone();
    }

    public function test_stale_and_tampered_tokens_are_rejected(): void
    {
        $chat = $this->begin(User::factory()->create());
        $this->turn($chat, 'An answer');
        $this->postJson('/api/conversations/'.$chat['id'].'/turns', ['token' => $chat['token'], 'text' => 'Replay'])->assertConflict();
        $this->postJson('/api/conversations/'.$chat['id'].'/turns', ['token' => 'tampered', 'text' => 'Intrusion'])->assertUnprocessable();
    }

    public function test_expired_draft_cannot_be_saved_or_continued(): void
    {
        $chat = $this->begin(User::factory()->create());
        DB::table('conversation_sessions')->where('id', $chat['id'])->update(['expires_at' => now()->subMinute()]);
        $this->postJson('/api/conversations/'.$chat['id'].'/turns', ['token' => $chat['token'], 'text' => 'Late answer'])->assertGone();
    }

    public function test_malformed_ai_response_is_rejected_at_the_laravel_boundary(): void
    {
        Http::swap(new \Illuminate\Http\Client\Factory);
        Http::fake(['*' => Http::response(['diagnosis' => 'CONFIRMED, SECRET SYMPTOMS'])]);
        $this->actingAs(User::factory()->create())->postJson('/api/conversations', ['region' => 'eyes', 'side' => 'unknown', 'processing_acknowledged' => true])->assertStatus(502)->assertDontSee('SECRET');
        $this->assertDatabaseCount('conversation_sessions', 0);
    }

    public function test_upstream_failures_do_not_reflect_health_content(): void
    {
        Http::swap(new \Illuminate\Http\Client\Factory);
        Http::fake(['*' => Http::response('SECRET HEALTH BODY', 500)]);
        $this->actingAs(User::factory()->create())->postJson('/api/conversations', ['region' => 'eyes', 'side' => 'unknown', 'processing_acknowledged' => true])->assertStatus(503)->assertDontSee('SECRET');
        Http::swap(new \Illuminate\Http\Client\Factory);
        Http::fake(['*' => Http::failedConnection()]);
        $this->postJson('/api/conversations', ['region' => 'eyes', 'side' => 'unknown', 'processing_acknowledged' => true])->assertStatus(503);
    }

    public function test_signup_and_logout_do_not_require_a_medical_profile(): void
    {
        $this->postJson('/api/register', ['email' => 'member@example.test', 'password' => 'a-long-test-password'])->assertCreated();
        $this->assertAuthenticated();
        $this->postJson('/api/logout')->assertNoContent();
        $this->assertGuest('web');
        \Illuminate\Support\Facades\Auth::forgetGuards();
        $this->getJson('/api/me')->assertUnauthorized();
    }
}
