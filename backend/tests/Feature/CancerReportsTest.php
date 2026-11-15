<?php

namespace Tests\Feature;

use App\Models\CancerReport;
use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Http;
use Illuminate\Testing\TestResponse;
use Tests\TestCase;

class CancerReportsTest extends TestCase
{
    use RefreshDatabase;

    protected function setUp(): void
    {
        parent::setUp();
        $this->withHeaders(['Origin' => 'http://127.0.0.1:5173']);
        Http::preventStrayRequests();
    }

    private function image(): string
    {
        return 'data:image/jpeg;base64,'.base64_encode("\xff\xd8\xff".str_repeat('1', 120)."\xff\xd9");
    }

    private function analysis(): array
    {
        return ['track' => 'oral', 'modality' => 'oral_photo', 'image_data_url' => $this->image(),
            'consent_local' => true, 'modality_confirmed' => true, 'research_only_acknowledged' => true];
    }

    private function modelResult(): array
    {
        return ['schema_version' => 'humantwin-cancer-result-v2', 'track' => 'oral', 'modality' => 'oral_photo',
            'model_version' => 'software-fixture-v1', 'target' => 'Synthetic software test only', 'weights_sha256' => str_repeat('b', 64),
            'input_sha256' => hash('sha256', base64_decode(explode(',', $this->image())[1])),
            'outcome' => 'inconclusive', 'outcome_reasons' => ['low-confidence'], 'finding_label' => null,
            'scores' => [['label' => 'benign_lesion', 'value' => .55], ['label' => 'malignant_lesion', 'value' => .45]],
            'confidence' => ['top_label' => 'benign_lesion', 'probability' => .55, 'level' => 'low', 'calibration' => 'temperature-scaled', 'temperature' => 1.4,
                'decision_threshold' => .7, 'normalized_entropy' => .99, 'margin' => .1, 'interpretation' => 'model-confidence-not-personal-risk'],
            'image_checks' => ['width' => 640, 'height' => 480, 'brightness' => 120.0, 'contrast' => 40.0, 'sharpness' => 80.0,
                'colored_fraction' => .9, 'overexposed_fraction' => 0.0, 'decision' => 'accepted', 'findings' => []],
            'clinical_validation' => false, 'calibrated_cancer_probability' => false, 'external_requests' => false, 'scope' => 'single-2d-image'];
    }

    private function save(array $changes = []): TestResponse
    {
        return $this->postJson('/api/cancer/reports', [...['input_sha256' => $this->modelResult()['input_sha256'], 'thumbnail_data_url' => $this->image(),
            'note' => 'PRIVATE synthetic note', 'consent' => true, 'consent_version' => 'cancer-report-storage-v1'], ...$changes]);
    }

    public function test_only_a_result_this_server_returned_to_the_same_user_can_be_saved(): void
    {
        $this->save()->assertUnauthorized();
        $owner = User::factory()->create();
        $this->actingAs($owner)->save()->assertStatus(409);
        Http::fake([config('ai.url').'/v1/cancer/analyze' => Http::response($this->modelResult())]);
        $this->postJson('/api/cancer/analyze', $this->analysis())->assertOk();
        $this->actingAs(User::factory()->create())->save()->assertStatus(409);
        $this->assertDatabaseCount('cancer_reports', 0);
        $this->actingAs($owner)->save(['consent' => false])->assertUnprocessable();
        $this->save(['consent_version' => 'other'])->assertUnprocessable();
        $this->save(['thumbnail_data_url' => 'data:image/jpeg;base64,'.base64_encode('not a jpeg image at all, just text that is long enough to pass '.str_repeat('x', 100))])->assertUnprocessable();
        $this->save(['scores' => [['label' => 'invented', 'value' => 1]]])->assertCreated();
        $saved = CancerReport::sole();
        $this->assertSame($this->modelResult()['scores'], $saved->payload['result']['scores']);
    }

    public function test_reports_are_encrypted_owner_scoped_listed_shown_and_deleted(): void
    {
        $owner = User::factory()->create();
        Http::fake([config('ai.url').'/v1/cancer/analyze' => Http::response($this->modelResult())]);
        $this->actingAs($owner)->postJson('/api/cancer/analyze', $this->analysis())->assertOk();
        $id = $this->save()->assertCreated()->json('id');
        $stored = DB::table('cancer_reports')->value('payload');
        $this->assertStringNotContainsString('PRIVATE', $stored);
        $this->assertStringNotContainsString('benign_lesion', $stored);
        $this->getJson('/api/cancer/reports')->assertOk()->assertJsonCount(1, 'reports')
            ->assertJsonPath('reports.0.outcome', 'inconclusive')->assertJsonPath('reports.0.top_label', 'benign_lesion')
            ->assertJsonMissingPath('reports.0.thumbnail_data_url');
        $this->getJson('/api/cancer/reports/'.$id)->assertOk()->assertJsonPath('result.outcome_reasons', ['low-confidence'])
            ->assertJsonPath('note', 'PRIVATE synthetic note')->assertHeader('Cache-Control', 'no-store, private');
        $this->actingAs(User::factory()->create())->getJson('/api/cancer/reports/'.$id)->assertNotFound();
        $this->deleteJson('/api/cancer/reports/'.$id)->assertNotFound();
        $this->actingAs($owner)->deleteJson('/api/cancer/reports/'.$id)->assertNoContent();
        $this->assertDatabaseCount('cancer_reports', 0);
    }

    public function test_history_is_capped_per_user(): void
    {
        $owner = User::factory()->create();
        Http::fake([config('ai.url').'/v1/cancer/analyze' => Http::response($this->modelResult())]);
        $this->actingAs($owner)->postJson('/api/cancer/analyze', $this->analysis())->assertOk();
        for ($index = 0; $index < 50; $index++) {
            CancerReport::create(['user_id' => $owner->id, 'payload' => ['result' => $this->modelResult(), 'thumbnail_data_url' => $this->image(), 'note' => null],
                'consent_version' => 'cancer-report-storage-v1', 'consented_at' => now()]);
        }
        $this->save()->assertStatus(409);
    }
}
