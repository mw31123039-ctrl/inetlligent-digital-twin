<?php

namespace Tests\Feature;

use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Http\Client\Request as ClientRequest;
use Illuminate\Support\Facades\Http;
use PHPUnit\Framework\Attributes\DataProvider;
use Tests\TestCase;

class CancerKnowledgeTest extends TestCase
{
    use RefreshDatabase;

    protected function setUp(): void
    {
        parent::setUp();
        $this->withHeaders(['Origin' => 'http://127.0.0.1:5173']);
        Http::preventStrayRequests();
    }

    private function payload(): array
    {
        return ['question' => 'Which tests investigate a persistent mouth ulcer?', 'consent_local' => true];
    }

    private function answer(): array
    {
        return ['schema_version' => 'humantwin-cancer-retrieval-v1', 'method' => 'local-semantic-retrieval',
            'corpus_version' => 'oncology-reference-2026-11-13', 'model_version' => 'minilm-software-fixture',
            'weights_sha256' => str_repeat('b', 64), 'question_sha256' => hash('sha256', $this->payload()['question']),
            'matches' => [['record_id' => 'oral', 'similarity' => .6]], 'retrieval_ms' => 8,
            'safety_notice' => 'none', 'question_saved' => false, 'external_requests' => false, 'clinical_validation' => false];
    }

    public function test_evidence_questions_require_auth_and_explicit_local_permission(): void
    {
        $this->postJson('/api/cancer/knowledge', $this->payload())->assertUnauthorized();
        $this->actingAs(User::factory()->create());
        $this->postJson('/api/cancer/knowledge', [...$this->payload(), 'consent_local' => false])->assertUnprocessable();
        $this->postJson('/api/cancer/knowledge', [...$this->payload(), 'question' => '   '])->assertUnprocessable();
        Http::assertNothingSent();
    }

    public function test_valid_source_ids_are_question_bound_without_identity_forwarding_or_health_storage(): void
    {
        $this->actingAs(User::factory()->create());
        Http::fake([config('ai.url').'/v1/cancer/knowledge' => Http::response($this->answer())]);
        $this->postJson('/api/cancer/knowledge', [...$this->payload(), 'patient_name' => 'not-forwarded', 'subject_id' => 'private'])
            ->assertOk()->assertJsonPath('matches.0.record_id', 'oral')->assertJsonPath('clinical_validation', false)
            ->assertHeader('Cache-Control', 'no-store, private');
        Http::assertSent(fn (ClientRequest $request) => count($request->data()) === 2
            && $request->hasHeader('X-Service-Key') && $request['consent_local'] === true
            && ! array_key_exists('patient_name', $request->data()));
        $this->assertDatabaseCount('health_assessments', 0);
        $this->assertDatabaseCount('conversation_sessions', 0);
    }

    public static function invalidResponses(): array
    {
        return [
            'another question' => [['question_sha256' => str_repeat('c', 64)]],
            'unknown record' => [['matches' => [['record_id' => 'invented', 'similarity' => .9]]]],
            'duplicate records' => [['matches' => [['record_id' => 'oral', 'similarity' => .6], ['record_id' => 'oral', 'similarity' => .5]]]],
            'invalid similarity' => [['matches' => [['record_id' => 'oral', 'similarity' => 5]]]],
            'generated diagnosis' => [['diagnosis' => 'cancer']],
            'clinical claim' => [['clinical_validation' => true]],
            'question saved' => [['question_saved' => true]],
            'external processing' => [['external_requests' => true]],
            'unknown corpus' => [['corpus_version' => 'unknown']],
        ];
    }

    #[DataProvider('invalidResponses')]
    public function test_unverified_or_generated_answers_are_rejected(array $changes): void
    {
        $this->actingAs(User::factory()->create());
        Http::fake([config('ai.url').'/v1/cancer/knowledge' => Http::response([...$this->answer(), ...$changes])]);
        $this->postJson('/api/cancer/knowledge', $this->payload())->assertStatus(502)->assertJsonMissingPath('matches');
    }

    public function test_missing_model_has_no_placeholder_answer_and_status_is_public(): void
    {
        Http::fake([config('ai.url').'/v1/cancer/knowledge-status' => Http::response([], 503),
            config('ai.url').'/v1/cancer/knowledge' => Http::response([], 503)]);
        $this->getJson('/api/cancer/knowledge-status')->assertOk()->assertJsonPath('configured', false);
        $this->actingAs(User::factory()->create());
        $this->postJson('/api/cancer/knowledge', $this->payload())->assertServiceUnavailable()->assertJsonMissingPath('matches');
    }
}
