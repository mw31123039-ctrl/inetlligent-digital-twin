<?php

namespace Tests\Feature;

use App\Models\EyeAssessment;
use App\Models\HealthAssessment;
use App\Models\User;
use App\Services\EyeAssessmentService;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Str;
use Tests\TestCase;

class EyeAssessmentsTest extends TestCase
{
    use RefreshDatabase;

    protected function setUp(): void
    {
        parent::setUp();
        $this->withHeaders(['Origin' => 'http://127.0.0.1:5173']);
        Http::preventStrayRequests();
    }

    private function payload(string $text = 'PRIVATE synthetic itching in both eyes'): array
    {
        return ['id' => (string) Str::uuid(), 'use' => 'education', 'locale' => 'en', 'model_side' => 'left',
            'anatomy_explored' => ['eye.retina'], 'turns' => [['question_id' => 'question.concern', 'value' => $text]],
            'consent' => true, 'consent_version' => 'health-storage-v1'];
    }

    public function test_clinical_use_is_disabled_and_authentication_and_consent_are_required(): void
    {
        $this->getJson('/api/eye/status')->assertOk()->assertJsonPath('clinical_use_available', false);
        $this->postJson('/api/eye/assessments', $this->payload())->assertUnauthorized();
        $this->actingAs(User::factory()->create())->postJson('/api/eye/assessments', [...$this->payload(), 'consent' => false])->assertUnprocessable();
        $this->postJson('/api/eye/assessments', [...$this->payload(), 'use' => 'clinical'])->assertStatus(409);
        $this->assertDatabaseCount('eye_assessments', 0);
    }

    public function test_every_shared_safety_vector_is_evaluated_without_the_ai_service(): void
    {
        $service = app(EyeAssessmentService::class);
        $cases = json_decode(file_get_contents(base_path('../contracts/eye/cases.v1.json')), true)['cases'];
        foreach ($cases as $case) {
            $result = $service->replay($this->payload($case['text']));
            $this->assertSame($case['level'], $result['urgency'], $case['id']);
            if (isset($case['rule'])) {
                $this->assertContains($case['rule'], $result['rule_ids'], $case['id']);
            }
        }
        Http::assertNothingSent();
    }

    public function test_server_recomputes_urgency_and_encrypts_the_consented_payload(): void
    {
        $this->actingAs(User::factory()->create());
        $payload = [...$this->payload('PRIVATE sudden loss of vision with no pain'), 'urgency' => 'unknown', 'reported' => ['pain' => 0]];
        $this->postJson('/api/eye/assessments', $payload)->assertCreated();
        $raw = DB::table('eye_assessments')->value('payload');
        $this->assertStringNotContainsString('PRIVATE', $raw);
        $record = EyeAssessment::first();
        $this->assertSame('emergency', $record->payload['session']['urgency']);
        $this->assertSame('emergency', $record->payload['session']['care_plan']['route']);
        $this->assertFalse($record->payload['session']['care_plan']['comfort_measures_included']);
        $this->assertStringContainsString('NOT A DIAGNOSIS', $record->payload['session']['doctor_summary']);
        $this->assertSame(0, $record->payload['session']['reported']['pain']);
        $this->assertSame(['eye.retina'], $record->payload['session']['anatomy_explored']);
        $this->assertDatabaseCount('health_assessments', 0);
        Http::assertNothingSent();
    }

    public function test_other_users_cannot_list_read_overwrite_or_delete_records(): void
    {
        $alice = User::factory()->create();
        $bob = User::factory()->create();
        $payload = $this->payload();
        $this->actingAs($alice)->postJson('/api/eye/assessments', $payload)->assertCreated();
        $this->actingAs($bob)->getJson('/api/eye/assessments')->assertOk()->assertJsonCount(0);
        $this->getJson('/api/eye/assessments/'.$payload['id'])->assertNotFound();
        $this->deleteJson('/api/eye/assessments/'.$payload['id'])->assertNotFound();
        $this->postJson('/api/eye/assessments', $payload)->assertNotFound();
        $this->actingAs($alice)->deleteJson('/api/eye/assessments/'.$payload['id'])->assertNoContent();
        $this->getJson('/api/eye/assessments/'.$payload['id'])->assertNotFound();
        $this->assertDatabaseCount('eye_assessments', 0);
    }

    public function test_invalid_ids_and_turns_are_rejected_and_missing_answers_stay_unknown(): void
    {
        $this->actingAs(User::factory()->create());
        $this->postJson('/api/eye/assessments', [...$this->payload(), 'anatomy_explored' => ['eye.invented']])->assertUnprocessable();
        $this->postJson('/api/eye/assessments', [...$this->payload(), 'turns' => [['question_id' => 'question.fake', 'value' => 'yes']]])->assertUnprocessable();
        $this->postJson('/api/eye/assessments', [...$this->payload(), 'turns' => [['question_id' => 'question.pain', 'value' => '100']]])->assertUnprocessable();
        $state = app(EyeAssessmentService::class)->replay($this->payload());
        $this->assertSame('unknown', $state['red_flags']['eye.rule.postoperative']);
        $this->assertContains('pain', $state['missing']);
        $this->assertSame('unknown', $state['urgency']);
        $this->assertSame([], $state['unconfirmed_explanations']);
    }

    public function test_laterality_changes_without_turning_anatomy_selection_into_a_symptom(): void
    {
        $input = $this->payload();
        $input['turns'] = [['question_id' => 'question.side', 'value' => 'left'], ['question_id' => 'question.concern', 'value' => 'Itching in both eyes']];
        $state = app(EyeAssessmentService::class)->replay($input);
        $this->assertSame('both', $state['reported']['laterality']);
        $this->assertSame('left', $state['model_side']);
        $this->assertSame('unknown', $state['reported']['location']);
    }

    public function test_routine_turns_after_emergency_are_rejected(): void
    {
        $this->actingAs(User::factory()->create());
        $payload = $this->payload('Chemical splash');
        $payload['turns'][] = ['question_id' => 'question.pain', 'value' => '0'];
        $this->postJson('/api/eye/assessments', $payload)->assertUnprocessable();
    }

    public function test_learning_content_does_not_become_a_reported_symptom_and_pain_is_not_invented(): void
    {
        $payload = $this->payload();
        $payload['turns'] = [['question_id' => 'learn:condition.diabetic-retinopathy', 'value' => 'What is diabetic retinopathy?'], ['question_id' => 'question.concern', 'value' => 'Severe eye pain']];
        $state = app(EyeAssessmentService::class)->replay($payload);
        $this->assertArrayNotHasKey('diabetes', $state['reported']);
        $this->assertSame('education', $state['messages'][1]['kind']);
        $this->assertNull($state['pain_assessment']['score']);
        $this->assertSame('severe', $state['pain_assessment']['band']);
        $payload['turns'][] = ['question_id' => 'question.concern', 'value' => 'Pain is 6/10'];
        $state = app(EyeAssessmentService::class)->replay($payload);
        $this->assertSame(6, $state['pain_assessment']['score']);
        $this->assertSame('moderate', $state['pain_assessment']['band']);
        Http::assertNothingSent();
    }

    public function test_assistant_pain_estimates_require_confirmation_and_are_recomputed_on_the_server(): void
    {
        $payload = $this->payload('Moderate eye pain distracts me');
        $state = app(EyeAssessmentService::class)->replay($payload);
        $this->assertSame(5, $state['pain_estimate']['suggested_score']);
        $this->assertNull($state['pain_assessment']['score']);
        $payload['turns'][] = ['question_id' => 'pain-estimate:accept', 'value' => '5'];
        $state = app(EyeAssessmentService::class)->replay($payload);
        $this->assertSame(5, $state['pain_assessment']['score']);
        $this->assertSame('assisted-confirmed', $state['pain_assessment']['numeric_source']);
        $this->assertTrue($state['pain_estimate']['confirmed']);
        $payload['turns'][1]['value'] = '9';
        $this->actingAs(User::factory()->create())->postJson('/api/eye/assessments', $payload)->assertUnprocessable();
    }
}
