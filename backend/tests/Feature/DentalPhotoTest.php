<?php

namespace Tests\Feature;

use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Http\Client\Request as ClientRequest;
use Illuminate\Support\Facades\Http;
use PHPUnit\Framework\Attributes\DataProvider;
use Tests\TestCase;

class DentalPhotoTest extends TestCase
{
    use RefreshDatabase;

    protected function setUp(): void
    {
        parent::setUp();
        $this->withHeaders(['Origin' => 'http://127.0.0.1:5173']);
        Http::preventStrayRequests();
    }

    private function imageBytes(): string
    {
        return "\xff\xd8\xff".str_repeat('0', 100)."\xff\xd9";
    }

    private function payload(): array
    {
        return ['photo' => ['view' => 'Frontal bite', 'data_url' => 'data:image/jpeg;base64,'.base64_encode($this->imageBytes())], 'consent_local' => true];
    }

    private function detectionFixture(): array
    {
        return ['mode' => 'photo-outline-draft', 'input_sha256' => hash('sha256', $this->imageBytes()), 'clinical_validation' => false,
            'geometry_dimensions' => '2d-visible-crowns', 'image_quality' => 'usable',
            'crowns' => [['jaw' => 'upper', 'points' => [['x' => .2, 'y' => .2], ['x' => .3, 'y' => .2], ['x' => .3, 'y' => .5], ['x' => .2, 'y' => .5]]]],
            'possible_case_ids' => []];
    }

    public function test_returns_401_without_auth_and_422_without_consent_or_a_valid_jpeg(): void
    {
        $this->postJson('/api/dental/detect', $this->payload())->assertUnauthorized();
        $this->actingAs(User::factory()->create());
        $this->postJson('/api/dental/detect', [...$this->payload(), 'consent_local' => false])->assertUnprocessable()->assertJsonValidationErrors('consent_local');
        $this->postJson('/api/dental/detect', ['photo' => ['view' => 'Frontal bite', 'data_url' => 'https://example.com/patient.jpg'], 'consent_local' => true])->assertUnprocessable()->assertJsonValidationErrors('photo.data_url');

        Http::assertNothingSent();
    }

    public function test_valid_draft_is_bound_to_photo_and_excludes_account_data_without_saving_health_content(): void
    {
        $this->actingAs(User::factory()->create());
        Http::fake([config('ai.url').'/v1/dental/detect' => Http::response($this->detectionFixture())]);

        $this->postJson('/api/dental/detect', [...$this->payload(), 'user_id' => 123, 'email' => 'private@example.invalid'])
            ->assertOk()->assertJsonPath('geometry_dimensions', '2d-visible-crowns')->assertJsonPath('clinical_validation', false)
            ->assertHeader('Cache-Control', 'no-store, private');

        Http::assertSent(fn (ClientRequest $request) => $request->url() === config('ai.url').'/v1/dental/detect'
            && ! array_key_exists('user_id', $request->data()) && ! array_key_exists('email', $request->data())
            && $request->hasHeader('X-Service-Key') && $request['consent_local'] === true);
        $this->assertDatabaseCount('health_assessments', 0);
        $this->assertDatabaseCount('eye_assessments', 0);
        $this->assertDatabaseCount('conversation_sessions', 0);
    }

    public static function invalidDrafts(): array
    {
        return [
            'wrong photograph' => [['input_sha256' => str_repeat('a', 64)]],
            'claims a clinical model' => [['clinical_validation' => true]],
            'unusable with findings' => [['image_quality' => 'insufficient']],
            'invented hidden condition' => [['possible_case_ids' => ['impacted-canine']]],
            'arbitrary treatment recommendation' => [['treatment' => 'Unsupported plan']],
            'out of image' => [['crowns' => [['jaw' => 'upper', 'points' => [['x' => -1, 'y' => 0], ['x' => .3, 'y' => .2], ['x' => .3, 'y' => .5], ['x' => .2, 'y' => .5]]]]]],
            'crossing polygon' => [['crowns' => [['jaw' => 'upper', 'points' => [['x' => .2, 'y' => .2], ['x' => .3, 'y' => .5], ['x' => .3, 'y' => .2], ['x' => .2, 'y' => .5]]]]]],
        ];
    }

    #[DataProvider('invalidDrafts')]
    public function test_returns_502_when_the_provider_draft_breaks_photo_or_geometry_constraints(array $change): void
    {
        $this->actingAs(User::factory()->create());
        Http::fake([config('ai.url').'/v1/dental/detect' => Http::response([...$this->detectionFixture(), ...$change])]);

        $this->postJson('/api/dental/detect', $this->payload())->assertStatus(502);

        Http::assertSentCount(1);
    }

    public function test_disabled_detection_returns_503_without_leaking_provider_content(): void
    {
        $this->actingAs(User::factory()->create());
        Http::fake([config('ai.url').'/v1/dental/detect' => Http::response(['detail' => 'PRIVATE provider message'], 503)]);

        $this->postJson('/api/dental/detect', $this->payload())->assertServiceUnavailable()->assertDontSee('PRIVATE');

        Http::assertSentCount(1);
    }

    public function test_public_status_only_reports_configuration_and_not_provider_secrets(): void
    {
        Http::fake([config('ai.url').'/v1/dental/detection-status' => Http::response(['provider_configured' => true, 'runtime' => 'local', 'state' => 'trained-unvalidated', 'train_images' => 5, 'validation_images' => 2, 'validation_dice' => .7, 'key' => 'PRIVATE', 'model_capability_verified' => true])]);

        $this->getJson('/api/dental/detector-status')->assertOk()->assertExactJson(['available' => true, 'provider_configured' => true, 'model_capability_verified' => false, 'draft_only' => true, 'runtime' => 'local', 'external_requests' => false, 'state' => 'trained-unvalidated', 'model_source' => 'reviewed-local-examples', 'train_images' => 5, 'validation_images' => 2, 'validation_dice' => .7]);

        Http::assertSentCount(1);
    }

    public function test_public_training_counts_are_preserved_without_claiming_mask_validation(): void
    {
        Http::fake([config('ai.url').'/v1/dental/detection-status' => Http::response(['provider_configured' => true, 'runtime' => 'local', 'state' => 'trained-unvalidated', 'model_source' => 'public-dataset', 'train_images' => 2541, 'validation_images' => 246, 'validation_dice' => .99, 'model_capability_verified' => true, 'private_path' => 'PRIVATE'])]);

        $this->getJson('/api/dental/detector-status')->assertOk()->assertJsonPath('train_images', 2541)
            ->assertJsonPath('validation_images', 246)->assertJsonPath('model_source', 'public-dataset')
            ->assertJsonPath('validation_dice', null)->assertJsonPath('model_capability_verified', false)->assertDontSee('PRIVATE');
    }

    public function test_recent_epoch_progress_does_not_enable_unfinished_detection(): void
    {
        Http::fake([config('ai.url').'/v1/dental/detection-status' => Http::response(['provider_configured' => true, 'runtime' => 'local', 'state' => 'training', 'model_source' => 'public-dataset', 'training_epoch' => 4, 'training_epochs' => 30, 'train_images' => 2541, 'validation_images' => 246])]);

        $this->getJson('/api/dental/detector-status')->assertOk()->assertJsonPath('state', 'training')
            ->assertJsonPath('provider_configured', false)->assertJsonPath('training_epoch', 4)->assertJsonPath('training_epochs', 30);
    }

    public function test_assisted_outline_requires_a_valid_prompt_and_forwards_only_local_consent(): void
    {
        $this->actingAs(User::factory()->create());
        $this->postJson('/api/dental/segment', $this->payload())->assertUnprocessable()->assertJsonValidationErrors('prompt');
        Http::assertNothingSent();
        Http::fake([config('ai.url').'/v1/dental/segment' => Http::response($this->detectionFixture())]);
        $prompt = $this->detectionFixture()['crowns'][0];
        $this->postJson('/api/dental/segment', [...$this->payload(), 'prompt' => $prompt, 'consent_external' => true, 'email' => 'private@example.invalid'])
            ->assertOk()->assertJsonCount(1, 'crowns')->assertJsonPath('possible_case_ids', []);
        Http::assertSent(fn (ClientRequest $request) => $request->url() === config('ai.url').'/v1/dental/segment'
            && $request['prompt'] === $prompt && $request['consent_local'] === true
            && ! array_key_exists('consent_external', $request->data()) && ! array_key_exists('email', $request->data()));
    }

    public function test_local_detector_cannot_return_condition_predictions_it_has_not_learned(): void
    {
        $this->actingAs(User::factory()->create());
        Http::fake([config('ai.url').'/v1/dental/detect' => Http::response([...$this->detectionFixture(), 'possible_case_ids' => ['crowding']])]);
        $this->postJson('/api/dental/detect', $this->payload())->assertStatus(502);
        Http::assertSentCount(1);
    }
}
