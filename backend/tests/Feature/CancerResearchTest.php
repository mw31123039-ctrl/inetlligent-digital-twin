<?php

namespace Tests\Feature;

use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Http\Client\Request as ClientRequest;
use Illuminate\Support\Facades\Http;
use PHPUnit\Framework\Attributes\DataProvider;
use Tests\TestCase;

class CancerResearchTest extends TestCase
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
        return ['track' => 'skin', 'modality' => 'skin_photo',
            'image_data_url' => 'data:image/jpeg;base64,'.base64_encode("\xff\xd8\xff".str_repeat('0', 100)."\xff\xd9"),
            'consent_local' => true, 'modality_confirmed' => true, 'research_only_acknowledged' => true];
    }

    private function resultFixture(): array
    {
        return ['schema_version' => 'humantwin-cancer-result-v1', 'track' => 'skin', 'modality' => 'skin_photo',
            'model_version' => 'software-fixture-v1', 'target' => 'Synthetic software test only',
            'weights_sha256' => str_repeat('b', 64), 'input_sha256' => hash('sha256', base64_decode(explode(',', $this->payload()['image_data_url'])[1])),
            'scores' => [['label' => 'test_a', 'value' => .7], ['label' => 'test_b', 'value' => .3]],
            'clinical_validation' => false, 'calibrated_cancer_probability' => false, 'external_requests' => false, 'scope' => 'single-2d-image'];
    }

    public function test_inference_requires_auth_consent_and_matching_input_before_contacting_python(): void
    {
        $this->postJson('/api/cancer/analyze', $this->payload())->assertUnauthorized();
        $this->actingAs(User::factory()->create());
        $this->postJson('/api/cancer/analyze', [...$this->payload(), 'consent_local' => false])->assertUnprocessable();
        $this->postJson('/api/cancer/analyze', [...$this->payload(), 'modality_confirmed' => false])->assertUnprocessable();
        $this->postJson('/api/cancer/analyze', [...$this->payload(), 'research_only_acknowledged' => false])->assertUnprocessable();
        $this->postJson('/api/cancer/analyze', [...$this->payload(), 'track' => 'lung'])->assertUnprocessable();
        $this->postJson('/api/cancer/analyze', [...$this->payload(), 'image_data_url' => 'https://example.invalid/patient.jpg'])->assertUnprocessable();
        Http::assertNothingSent();
    }

    public function test_valid_output_is_image_bound_without_forwarding_identity_history_or_saving_health_data(): void
    {
        $this->actingAs(User::factory()->create());
        Http::fake([config('ai.url').'/v1/cancer/analyze' => Http::response($this->resultFixture())]);
        $this->postJson('/api/cancer/analyze', [...$this->payload(), 'email' => 'private@example.invalid', 'subject_id' => 'PRIVATE', 'history' => ['symptoms' => 'private']])
            ->assertOk()->assertJsonPath('clinical_validation', false)->assertJsonPath('scope', 'single-2d-image')
            ->assertHeader('Cache-Control', 'no-store, private');
        Http::assertSent(fn (ClientRequest $request) => $request->hasHeader('X-Service-Key')
            && count($request->data()) === 6 && ! array_key_exists('email', $request->data())
            && ! array_key_exists('history', $request->data()) && ! array_key_exists('subject_id', $request->data()));
        $this->assertDatabaseCount('health_assessments', 0);
        $this->assertDatabaseCount('conversation_sessions', 0);
    }

    public static function invalidOutputs(): array
    {
        return [
            'other image' => [['input_sha256' => str_repeat('c', 64)]],
            'other pathway' => [['track' => 'lung']],
            'other modality' => [['modality' => 'dermoscopy']],
            'clinical claim' => [['clinical_validation' => true]],
            'calibrated risk claim' => [['calibrated_cancer_probability' => true]],
            'volume claim' => [['scope' => 'full-ct-volume']],
            'invented diagnosis' => [['diagnosis' => 'cancer']],
            'duplicate labels' => [['scores' => [['label' => 'a', 'value' => .5], ['label' => 'a', 'value' => .5]]]],
            'inconsistent scores' => [['scores' => [['label' => 'a', 'value' => .9], ['label' => 'b', 'value' => .9]]]],
        ];
    }

    #[DataProvider('invalidOutputs')]
    public function test_invalid_or_unbound_outputs_are_rejected(array $changes): void
    {
        $this->actingAs(User::factory()->create());
        Http::fake([config('ai.url').'/v1/cancer/analyze' => Http::response([...$this->resultFixture(), ...$changes])]);
        $this->postJson('/api/cancer/analyze', $this->payload())->assertStatus(502)->assertJsonMissingPath('scores');
    }

    public function test_status_is_public_and_fails_closed_when_the_service_is_unavailable(): void
    {
        Http::fake([config('ai.url').'/v1/cancer/status' => Http::response([], 503)]);
        $response = $this->getJson('/api/cancer/status')->assertOk()->assertJsonPath('available', false)
            ->assertJsonPath('clinical_validation', false)->assertHeader('Cache-Control', 'no-store, private');
        $this->assertCount(4, $response->json('pathways'));
        foreach ($response->json('pathways') as $pathway) {
            foreach ($pathway['models'] as $model) {
                $this->assertFalse($model['configured']);
                $this->assertSame('service-unavailable', $model['state']);
            }
        }
    }

    public function test_status_accepts_only_explicit_readiness_and_sanitizes_operator_metadata(): void
    {
        $upstream = ['available' => true, 'clinical_validation' => false, 'external_requests' => false, 'scope' => 'single-2d-image',
            'pathways' => [['track' => 'skin', 'models' => [['modality' => 'skin_photo', 'configured' => true,
                'state' => 'configured-unvalidated', 'model_version' => 'software-v1', 'target' => 'Synthetic software test',
                'weights_sha256' => str_repeat('b', 64), 'private_path' => 'operator-only']]]]];
        Http::fake([config('ai.url').'/v1/cancer/status' => Http::sequence()->push($upstream)->push([...$upstream, 'available' => false])]);
        $response = $this->getJson('/api/cancer/status')->assertOk()->assertJsonPath('available', true)
            ->assertJsonPath('pathways.0.models.0.configured', true)->assertJsonMissingPath('pathways.0.models.0.private_path');
        $this->assertCount(4, $response->json('pathways'));
        $this->getJson('/api/cancer/status')->assertOk()->assertJsonPath('available', false)
            ->assertJsonPath('pathways.0.models.0.configured', false);
    }

    public function test_missing_clinical_scope_flags_are_rejected(): void
    {
        $this->actingAs(User::factory()->create());
        $incomplete = $this->resultFixture();
        unset($incomplete['clinical_validation']);
        Http::fake([config('ai.url').'/v1/cancer/analyze' => Http::response($incomplete)]);
        $this->postJson('/api/cancer/analyze', $this->payload())->assertStatus(502)->assertJsonMissingPath('scores');
    }

    public function test_optional_explanation_is_forwarded_and_bound_to_a_returned_class(): void
    {
        $this->actingAs(User::factory()->create());
        $explanation = ['method' => 'occlusion-sensitivity', 'target_label' => 'test_a', 'grid_size' => 4,
            'values' => array_fill(0, 16, .5), 'meaning' => 'score-drop-under-occlusion',
            'localization' => false, 'max_score_drop' => .1];
        $valid = [...$this->resultFixture(), 'explanation' => $explanation, 'runtime' => 'onnxruntime-cpu', 'inference_ms' => 100.0];
        Http::fake([config('ai.url').'/v1/cancer/analyze' => Http::sequence()->push($valid)
            ->push([...$valid, 'explanation' => [...$explanation, 'target_label' => 'unreturned_class']])
            ->push([...$valid, 'explanation' => [...$explanation, 'values' => array_fill(0, 17, .5)]])
            ->push([...$valid, 'explanation' => [...$explanation, 'values' => array_fill(0, 16, -5)]])
            ->push([...$valid, 'explanation' => ['target_label' => 'test_a', 'grid_size' => 4, 'values' => array_fill(0, 16, .5), 'max_score_drop' => .1]])]);
        $this->postJson('/api/cancer/analyze', [...$this->payload(), 'explain' => true])
            ->assertOk()->assertJsonPath('explanation.localization', false);
        Http::assertSent(fn (ClientRequest $request) => $request['explain'] === true);
        $this->postJson('/api/cancer/analyze', [...$this->payload(), 'explain' => true])->assertStatus(502);
        $this->postJson('/api/cancer/analyze', [...$this->payload(), 'explain' => true])->assertStatus(502);
        $this->postJson('/api/cancer/analyze', [...$this->payload(), 'explain' => true])->assertStatus(502);
        $this->postJson('/api/cancer/analyze', [...$this->payload(), 'explain' => true])->assertStatus(502);
    }

    public function test_service_failure_never_returns_a_placeholder_score(): void
    {
        $this->actingAs(User::factory()->create());
        Http::fake([config('ai.url').'/v1/cancer/analyze' => Http::response([], 503)]);
        $this->postJson('/api/cancer/analyze', $this->payload())->assertServiceUnavailable()->assertJsonMissingPath('scores');
    }

    public function test_cancer_images_have_a_bounded_request_limit_independent_of_other_routes(): void
    {
        $this->actingAs(User::factory()->create());
        Http::fake([config('ai.url').'/v1/cancer/analyze' => Http::response($this->resultFixture())]);
        $this->postJson('/api/cancer/analyze', [...$this->payload(), 'ignored_padding' => str_repeat('x', 600000)])->assertOk();
        $this->postJson('/api/cancer/analyze', [...$this->payload(), 'ignored_padding' => str_repeat('x', 1600001)])->assertStatus(413);
        $this->postJson('/api/conversations', ['ignored_padding' => str_repeat('x', 600000)])->assertStatus(413);
        Http::assertSentCount(1);
    }
}
