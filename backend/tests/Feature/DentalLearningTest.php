<?php

namespace Tests\Feature;

use App\Models\User;
use App\Services\DentalOwner;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Http\Client\Request as ClientRequest;
use Illuminate\Support\Facades\Http;
use Tests\TestCase;

class DentalLearningTest extends TestCase
{
    use RefreshDatabase;

    protected function setUp(): void
    {
        parent::setUp();
        $this->withHeaders(['Origin' => 'http://127.0.0.1:5173']);
        Http::preventStrayRequests();
    }

    private function state(): array
    {
        return ['runtime' => 'local', 'external_requests' => false, 'clinical_validation' => false,
            'examples' => [['id' => str_repeat('a', 64), 'subject_code' => 'SUBJECT_1', 'reviewer_code' => 'DENTIST_1', 'partition' => 'train', 'view' => 'Frontal bite', 'crowns' => 2]],
            'job' => ['state' => 'idle', 'phase' => 'idle'], 'model' => ['provider_configured' => false, 'train_images' => 0, 'validation_images' => 0, 'validation_dice' => null]];
    }

    private function example(): array
    {
        $raw = "\xff\xd8\xff".str_repeat('0', 100)."\xff\xd9";

        return ['schema_version' => 'humantwin-local-crowns-v1', 'subject_code' => 'SUBJECT_1', 'reviewer_code' => 'DENTIST_1', 'partition' => 'train',
            'permission_training' => true, 'complete_annotation' => true, 'input_sha256' => hash('sha256', $raw),
            'photo' => ['view' => 'Frontal bite', 'data_url' => 'data:image/jpeg;base64,'.base64_encode($raw)],
            'crowns' => [['jaw' => 'upper', 'points' => [['x' => .2, 'y' => .2], ['x' => .3, 'y' => .2], ['x' => .3, 'y' => .5], ['x' => .2, 'y' => .5]]]]];
    }

    public function test_all_teaching_actions_require_authentication_without_forwarding_anything(): void
    {
        $this->getJson('/api/dental/learning')->assertUnauthorized();
        $this->postJson('/api/dental/learning/examples', $this->example())->assertUnauthorized();
        $this->postJson('/api/dental/learning/train', ['consent_training' => true])->assertUnauthorized();
        $this->deleteJson('/api/dental/learning/examples/'.str_repeat('a', 64))->assertUnauthorized();
        Http::assertNothingSent();
    }

    public function test_training_and_saving_require_explicit_permission_and_valid_photo_fingerprints(): void
    {
        $this->actingAs(User::factory()->create());
        $this->postJson('/api/dental/learning/train', ['consent_training' => false])->assertUnprocessable()->assertJsonValidationErrors('consent_training');
        $this->postJson('/api/dental/learning/examples', [...$this->example(), 'permission_training' => false])->assertUnprocessable()->assertJsonValidationErrors('permission_training');
        $this->postJson('/api/dental/learning/examples', [...$this->example(), 'complete_annotation' => false])->assertUnprocessable()->assertJsonValidationErrors('complete_annotation');
        $this->postJson('/api/dental/learning/examples', [...$this->example(), 'input_sha256' => str_repeat('a', 64)])->assertUnprocessable();
        Http::assertNothingSent();
    }

    public function test_saving_uses_server_derived_account_scope_and_strips_account_identifiers(): void
    {
        $user = User::factory()->create();
        $this->actingAs($user)->withHeaders(['X-Dental-Owner' => str_repeat('f', 64)]);
        Http::fake([config('ai.url').'/v1/dental/learning/examples' => Http::response($this->state())]);
        $this->postJson('/api/dental/learning/examples', [...$this->example(), 'owner' => 'spoofed', 'email' => $user->email, 'user_id' => 999])
            ->assertOk()->assertJsonCount(1, 'examples')->assertJsonPath('can_train', false)->assertHeader('Cache-Control', 'no-store, private');
        Http::assertSent(fn (ClientRequest $request) => $request->header('X-Dental-Owner')[0] === DentalOwner::token((int) $user->id)
            && $request['permission_training'] === true && ! array_key_exists('owner', $request->data())
            && ! array_key_exists('email', $request->data()) && ! array_key_exists('user_id', $request->data()));
        $this->assertDatabaseCount('health_assessments', 0);
        $this->assertNotSame(DentalOwner::token((int) $user->id), DentalOwner::token((int) $user->id + 1));
    }

    public function test_status_returns_only_safe_metadata_and_progress(): void
    {
        $this->actingAs(User::factory()->create());
        $state = $this->state();
        $state['examples'][0]['photo'] = 'PRIVATE_IMAGE';
        $state['job']['message'] = 'PRIVATE_ERROR';
        $state['api_key'] = 'PRIVATE_KEY';
        Http::fake([config('ai.url').'/v1/dental/learning' => Http::response($state)]);
        $this->getJson('/api/dental/learning')->assertOk()->assertJsonPath('subjects.train', 1)->assertJsonPath('external_requests', false)->assertDontSee('PRIVATE');
        Http::assertSentCount(1);
    }

    public function test_training_queues_only_a_consented_job_and_deletion_preserves_owner_scope(): void
    {
        $user = User::factory()->create();
        $this->actingAs($user);
        $running = [...$this->state(), 'job' => ['state' => 'running', 'phase' => 'checking']];
        Http::fake([
            config('ai.url').'/v1/dental/learning/train' => Http::response($running),
            config('ai.url').'/v1/dental/learning/examples/'.str_repeat('a', 64) => Http::response(['detail' => 'PRIVATE other owner'], 404),
        ]);
        $this->postJson('/api/dental/learning/train', ['consent_training' => true, 'dataset_path' => 'PRIVATE'])->assertOk()->assertJsonPath('job.state', 'running')->assertJsonPath('can_train', false);
        $this->deleteJson('/api/dental/learning/examples/'.str_repeat('a', 64))->assertNotFound()->assertDontSee('PRIVATE');
        Http::assertSent(fn (ClientRequest $request) => $request->method() === 'DELETE' && $request->header('X-Dental-Owner')[0] === DentalOwner::token((int) $user->id));
        Http::assertSent(fn (ClientRequest $request) => $request->method() === 'POST' && $request->data() === ['consent_training' => true]);
    }

    public function test_unavailable_or_unsafe_service_responses_cannot_claim_training_success(): void
    {
        $this->actingAs(User::factory()->create());
        Http::fake([config('ai.url').'/v1/dental/learning' => Http::sequence()
            ->push(['detail' => 'PRIVATE traceback'], 503)
            ->push([...$this->state(), 'external_requests' => true])]);
        $this->getJson('/api/dental/learning')->assertServiceUnavailable()->assertDontSee('PRIVATE');
        $this->getJson('/api/dental/learning')->assertStatus(502);
        Http::assertSentCount(2);
    }
}
