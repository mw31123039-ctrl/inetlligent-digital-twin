<?php

namespace Tests\Feature;

use App\Models\ClinicalAssessment;
use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\Http;
use Tests\TestCase;

class ClinicalReviewTest extends TestCase
{
    use RefreshDatabase;

    protected function setUp(): void
    {
        parent::setUp();
        $this->withHeaders(['Origin' => 'http://127.0.0.1:5173']);
        Http::preventStrayRequests();
        Http::fake(['*/v2/clinical/catalog' => Http::response(['versions' => ['engine' => 'clinical-engine-test', 'knowledge' => 'knowledge-test']])]);
    }

    private function reviewer(): User
    {
        $user = User::factory()->create();
        $this->artisan('humantwin:reviewer', ['email' => $user->email])->assertSuccessful();

        return $user->fresh();
    }

    private function sharedAssessment(User $owner, bool $shared = true): ClinicalAssessment
    {
        $assessment = json_decode(file_get_contents(base_path('tests/Fixtures/clinical-collecting.json')), true);

        return ClinicalAssessment::create([
            'user_id' => $owner->id, 'consent_version' => 'clinical-storage-v1', 'consented_at' => now(), 'review_shared_at' => $shared ? now() : null,
            'payload' => ['messages' => [['id' => 'm1', 'role' => 'assistant', 'text' => 'q', 'question_id' => 'complaint', 'answer_codes' => [], 'superseded_by' => null],
                ['id' => 'm2', 'role' => 'user', 'text' => 'My name is Test Patient and my eye is red', 'question_id' => 'complaint', 'answer_codes' => [], 'superseded_by' => null]],
                'assessment' => $assessment, 'locale' => 'en', 'anatomy' => ['id' => 'body.eyes', 'side' => 'left'], 'previous_id' => null],
        ]);
    }

    public function test_patients_cannot_use_the_review_queue_and_role_is_not_mass_assignable(): void
    {
        $patient = User::factory()->create();
        $this->actingAs($patient)->getJson('/api/clinical/review/items')->assertForbidden();
        $this->getJson('/api/clinical/review/cases')->assertForbidden();
        $this->postJson('/api/register', ['email' => 'new@example.test', 'password' => 'a-long-password-123', 'role' => 'reviewer']);
        $this->assertNotSame('reviewer', User::where('email', 'new@example.test')->value('role'));
    }

    public function test_reviewers_see_only_shared_cases_without_free_text_or_identity(): void
    {
        $owner = User::factory()->create();
        $shared = $this->sharedAssessment($owner);
        $this->sharedAssessment($owner, false);
        $response = $this->actingAs($this->reviewer())->getJson('/api/clinical/review/cases')->assertOk();
        $this->assertCount(1, $response->json('cases'));
        $this->assertSame($shared->id, $response->json('cases.0.assessment_id'));
        $body = $response->getContent();
        $this->assertStringNotContainsString('Test Patient', $body);
        $this->assertStringNotContainsString($owner->email, $body);
        $this->assertStringNotContainsString('since yesterday', $body, 'patient quotes are not exposed');
        $this->assertDatabaseHas('audit_events', ['action' => 'review.case_viewed', 'owner_id' => $owner->id]);
    }

    public function test_corrections_need_a_second_reviewer_and_record_provenance(): void
    {
        $author = $this->reviewer();
        $item = $this->actingAs($author)->postJson('/api/clinical/review/items', [
            'target_type' => 'citation', 'target_ref' => 'conjunctivitis:sym:itch', 'proposed' => 'Bind itch to the NEI page instead.',
            'rationale' => 'The NHS list item lacks context for itching in allergic conjunctivitis.', 'evidence_url' => 'https://www.nei.nih.gov/',
        ])->assertCreated()->json();
        $this->assertSame('knowledge-test', $item['knowledge_version']);
        $this->assertSame('clinical-engine-test', $item['engine_version']);
        $this->postJson('/api/clinical/review/items/'.$item['id'].'/decision', ['decision' => 'accepted'])->assertForbidden();
        $second = $this->reviewer();
        $this->actingAs($second)->postJson('/api/clinical/review/items/'.$item['id'].'/decision', ['decision' => 'accepted'])->assertOk()->assertJsonPath('status', 'accepted');
        $this->postJson('/api/clinical/review/items/'.$item['id'].'/decision', ['decision' => 'rejected'])->assertStatus(409);
    }

    public function test_patients_control_review_sharing(): void
    {
        $owner = User::factory()->create();
        $record = $this->sharedAssessment($owner, false);
        $this->actingAs($owner)->postJson('/api/clinical/assessments/'.$record->id.'/review-share', [])->assertUnprocessable();
        $this->postJson('/api/clinical/assessments/'.$record->id.'/review-share', ['consent' => true, 'consent_version' => 'clinical-review-share-v1'])->assertOk();
        $this->assertNotNull($record->fresh()->review_shared_at);
        $this->deleteJson('/api/clinical/assessments/'.$record->id.'/review-share')->assertOk();
        $this->assertNull($record->fresh()->review_shared_at);
        $this->actingAs(User::factory()->create())->postJson('/api/clinical/assessments/'.$record->id.'/review-share', ['consent' => true, 'consent_version' => 'clinical-review-share-v1'])->assertNotFound();
    }
}
