<?php

namespace Tests\Feature;

use App\Models\User;
use App\Services\DentalOwner;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Http\Client\Request as ClientRequest;
use Illuminate\Support\Facades\Http;
use Tests\TestCase;

class DentalScreeningTest extends TestCase
{
    use RefreshDatabase;

    protected function setUp(): void
    {
        parent::setUp();
        $this->withHeaders(['Origin' => 'http://127.0.0.1:5173']);
        Http::preventStrayRequests();
    }

    private function record(): array
    {
        $taxonomy = json_decode(file_get_contents(base_path('../contracts/dental/screening-taxonomy.v1.json')), true);

        return ['schema_version' => 'humantwin-orthodontic-screening-v1', 'taxonomy_version' => $taxonomy['version'],
            'subject_code' => 'PATIENT_1', 'visit_code' => 'VISIT_1', 'partition' => 'train', 'age_years' => null, 'dentition_stage' => 'unknown',
            'scope' => 'not_reviewed', 'normal_appearance' => 'not_assessable', 'existing_braces' => 'not_assessable', 'photos' => [],
            'findings' => array_map(fn (array $item): array => ['id' => $item['id'], 'state' => 'not_assessable', 'evidence_basis' => 'not_recorded', 'photo_ids' => [], 'record_reference' => '', 'note' => '', 'locations' => []], $taxonomy['conditions']),
            'classifications' => ['overall' => 'not_recorded', 'molar_right' => 'not_recorded', 'molar_left' => 'not_recorded', 'canine_right' => 'not_recorded', 'canine_left' => 'not_recorded', 'incisor' => 'not_recorded', 'entered_by_clinician' => false, 'note' => ''],
            'review' => ['reviewer_code' => '', 'reviewer_role' => 'unknown', 'annotations_reviewed' => false, 'definitions_reviewed' => false],
            'data_rights' => 'consented_clinical_data', 'rights_reference' => 'CONSENT_1', 'consent_storage' => true, 'consent_training' => false,
            'is_demonstration' => false, 'clinical_validation' => false, 'classifier_applied' => false, 'model_training_performed' => false];
    }

    private function listing(): array
    {
        return ['cases' => [['id' => str_repeat('a', 64), 'subject_code' => 'PATIENT_1', 'visit_code' => 'VISIT_1', 'partition' => 'train']], 'classifier_available' => false, 'clinical_validation' => false];
    }

    public function test_screening_records_require_authentication_for_every_operation(): void
    {
        $this->getJson('/api/dental/screening/cases')->assertUnauthorized();
        $this->postJson('/api/dental/screening/cases', $this->record())->assertUnauthorized();
        $this->getJson('/api/dental/screening/cases/'.str_repeat('a', 64))->assertUnauthorized();
        $this->deleteJson('/api/dental/screening/cases/'.str_repeat('a', 64))->assertUnauthorized();
        Http::assertNothingSent();
    }

    public function test_storage_requires_the_full_taxonomy_permission_and_no_clinical_or_ai_claims(): void
    {
        $this->actingAs(User::factory()->create());
        $record = $this->record();
        foreach ([['consent_storage' => false], ['clinical_validation' => true], ['classifier_applied' => true], ['is_demonstration' => true], ['taxonomy_version' => 'wrong'], ['patient_name' => 'PRIVATE']] as $change) {
            $this->postJson('/api/dental/screening/cases', [...$record, ...$change])->assertUnprocessable()->assertDontSee('PRIVATE');
        }
        $record['findings'][1]['id'] = $record['findings'][0]['id'];
        $this->postJson('/api/dental/screening/cases', $record)->assertUnprocessable();
        Http::assertNothingSent();
    }

    public function test_explicit_save_uses_server_derived_owner_and_preserves_four_state_labels(): void
    {
        $user = User::factory()->create();
        $this->actingAs($user)->withHeaders(['X-Dental-Owner' => str_repeat('f', 64)]);
        Http::fake([config('ai.url').'/v1/dental/screening/cases' => Http::response($this->listing())]);
        $this->postJson('/api/dental/screening/cases', $this->record())->assertOk()->assertJsonPath('classifier_available', false)->assertJsonCount(1, 'cases')->assertHeader('Cache-Control', 'no-store, private');
        Http::assertSent(fn (ClientRequest $request) => $request->header('X-Dental-Owner')[0] === DentalOwner::token((int) $user->id)
            && count($request['findings']) === 41 && $request['findings'][0]['state'] === 'not_assessable'
            && $request['model_training_performed'] === false && ! array_key_exists('email', $request->data()));
        $this->assertDatabaseCount('health_assessments', 0);
    }

    public function test_list_redacts_extra_content_and_saved_record_cannot_invent_classifier_results(): void
    {
        $this->actingAs(User::factory()->create());
        $list = $this->listing();
        $list['cases'][0]['photo'] = 'PRIVATE_IMAGE';
        Http::fake([
            config('ai.url').'/v1/dental/screening/cases' => Http::response($list),
            config('ai.url').'/v1/dental/screening/cases/'.str_repeat('a', 64) => Http::response([...$this->record(), 'classifier_applied' => true]),
        ]);
        $this->getJson('/api/dental/screening/cases')->assertOk()->assertDontSee('PRIVATE_IMAGE');
        $this->getJson('/api/dental/screening/cases/'.str_repeat('a', 64))->assertStatus(502);
        Http::assertSentCount(2);
    }

    public function test_owner_scoped_load_and_delete_protect_other_visits_and_hide_provider_errors(): void
    {
        $user = User::factory()->create();
        $this->actingAs($user);
        $path = config('ai.url').'/v1/dental/screening/cases/'.str_repeat('a', 64);
        Http::fake([$path => Http::sequence()->push($this->record())->push(['detail' => 'PRIVATE other owner'], 404)]);
        $this->getJson('/api/dental/screening/cases/'.str_repeat('a', 64))->assertOk()->assertJsonCount(41, 'findings');
        $this->deleteJson('/api/dental/screening/cases/'.str_repeat('a', 64))->assertNotFound()->assertDontSee('PRIVATE');
        Http::assertSent(fn (ClientRequest $request) => $request->method() === 'DELETE' && $request->header('X-Dental-Owner')[0] === DentalOwner::token((int) $user->id));
    }

    public function test_photo_bundle_size_exception_is_scoped_to_screening_saves(): void
    {
        $this->actingAs(User::factory()->create());
        Http::fake([config('ai.url').'/v1/dental/screening/cases' => Http::response($this->listing())]);
        $record = $this->record();
        $raw = "\xff\xd8\xff".str_repeat('0', 225000)."\xff\xd9";
        foreach (['a', 'b'] as $character) {
            $record['photos'][] = ['source_sha256' => str_repeat($character, 64), 'width' => 1024, 'height' => 768, 'standard_view' => 'frontal_bite',
                'view_confirmed' => false, 'quality' => 'not_reviewed', 'quality_reasons' => [], 'biting_together' => 'unknown', 'patient_orientation_confirmed' => false,
                'data_url' => 'data:image/jpeg;base64,'.base64_encode($raw), 'input_sha256' => hash('sha256', $raw)];
        }
        $this->postJson('/api/dental/screening/cases', $record)->assertOk();
        $this->postJson('/api/dental/detect', ['oversized' => str_repeat('x', 600000)])->assertStatus(413);
        $this->postJson('/api/dental/screening/cases', ['oversized' => str_repeat('x', 2300001)])->assertStatus(413);
        Http::assertSentCount(1);
    }
}
