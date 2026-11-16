<?php

namespace Tests\Feature;

use App\Models\ClinicalAssessment;
use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Http\Client\Request as ClientRequest;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Http;
use Tests\TestCase;

class ClinicalSessionsTest extends TestCase
{
    use RefreshDatabase;

    /** @var array<int, array<string, mixed>> */
    private array $sent = [];

    /** @var (callable(array<string, mixed>, ClientRequest): array<string, mixed>)|null */
    private $mutate = null;

    protected function setUp(): void
    {
        parent::setUp();
        $this->withHeaders(['Origin' => 'http://127.0.0.1:5173']);
        Http::preventStrayRequests();
        $this->fakeEngine();
    }

    /**
     * @return array<string, mixed>
     */
    private function fixture(string $name = 'clinical-collecting'): array
    {
        return json_decode(file_get_contents(base_path("tests/Fixtures/{$name}.json")), true);
    }

    private function fakeEngine(?callable $mutate = null): void
    {
        $this->mutate = $mutate;
        if ($mutate !== null) {
            return; // the single registered fake reads the current mutation
        }
        Http::fake(function (ClientRequest $request) {
            $mutate = $this->mutate;
            $this->sent[] = ['url' => $request->url(), 'data' => $request->data()];
            $result = $this->fixture(count($request['messages'] ?? []) === 0 ? 'clinical-start' : 'clinical-collecting');
            $result['locale'] = $request['locale'] ?? 'en';
            $result['anatomy']['id'] = $request['anatomy']['id'] ?? 'body.eyes';
            $result = $mutate ? $mutate($result, $request) : $result;
            if (str_ends_with($request->url(), '/stream')) {
                $lines = json_encode(['type' => 'stage', 'stage' => 'extracting'])."\n".json_encode(['type' => 'stage', 'stage' => 'screening'])."\n"
                    .json_encode(['type' => 'result', 'assessment' => $result])."\n";

                return Http::response($lines, 200, ['Content-Type' => 'application/x-ndjson']);
            }

            return Http::response($result);
        });
    }

    /**
     * @return array<string, mixed>
     */
    private function begin(User $user, array $overrides = []): array
    {
        return $this->actingAs($user)->postJson('/api/clinical/sessions', [
            'anatomy_id' => 'body.eyes', 'side' => 'left', 'locale' => 'en', 'processing_acknowledged' => true, ...$overrides,
        ])->assertCreated()->json();
    }

    /**
     * @return array<string, mixed>
     */
    private function answer(array $session, string $text, array $codes = [], ?string $correct = null): array
    {
        return $this->postJson('/api/clinical/sessions/'.$session['id'].'/turns', [
            'token' => $session['token'], 'text' => $text, 'answer_codes' => $codes, 'correct_message_id' => $correct,
        ])->assertOk()->json();
    }

    public function test_authentication_acknowledgement_and_known_anatomy_are_required(): void
    {
        $this->postJson('/api/clinical/sessions', [])->assertUnauthorized();
        $user = User::factory()->create();
        $this->actingAs($user)->postJson('/api/clinical/sessions', ['anatomy_id' => 'body.eyes', 'side' => 'left', 'locale' => 'en'])->assertUnprocessable();
        $this->postJson('/api/clinical/sessions', ['anatomy_id' => 'body.spleen-of-doom', 'side' => 'left', 'locale' => 'en', 'processing_acknowledged' => true])->assertUnprocessable();
        $this->postJson('/api/clinical/sessions', ['anatomy_id' => 'body.eyes', 'side' => 'left', 'locale' => 'fr', 'processing_acknowledged' => true])->assertUnprocessable();
        Http::assertNothingSent();
    }

    public function test_conversation_flow_keeps_drafts_out_of_the_database(): void
    {
        $session = $this->begin(User::factory()->create());
        $this->assertSame('assistant', $session['messages'][0]['role']);
        $this->assertSame('complaint', $session['messages'][0]['question_id']);
        $turn = $this->answer($session, 'My left eye is red and itchy');
        $this->assertSame(1, $turn['revision']);
        $user = collect($turn['messages'])->firstWhere('role', 'user');
        $this->assertSame('complaint', $user['question_id'], 'answers are bound to the question they answer');
        $this->assertSame('sym:contact_lens', collect($turn['messages'])->last()['question_id']);
        $row = (array) DB::table('clinical_sessions')->first();
        $this->assertSame(['id', 'user_id', 'revision', 'expires_at'], array_keys($row));
        $this->assertStringNotContainsString('itchy', json_encode(DB::table('audit_events')->get()));
        $sent = end($this->sent)['data'];
        $this->assertSame([], $sent['patient_context']);
        $this->assertSame(['id', 'role', 'text', 'question_id', 'answer_codes', 'superseded_by'], array_keys($sent['messages'][0]));
    }

    public function test_corrections_supersede_in_place_and_stale_tokens_conflict(): void
    {
        $session = $this->begin(User::factory()->create());
        $first = $this->answer($session, 'My eye is red');
        $second = $this->answer($first, 'No', ['no']);
        $original = collect($second['messages'])->firstWhere('text', 'My eye is red');
        $corrected = $this->answer($second, 'My right eye is red and painful', [], $original['id']);
        $messages = collect($corrected['messages']);
        $this->assertNotNull($messages->firstWhere('id', $original['id'])['superseded_by']);
        $replacement = $messages->firstWhere('text', 'My right eye is red and painful');
        $this->assertSame($original['question_id'], $replacement['question_id']);
        $this->assertSame($messages->search(fn ($m) => $m['id'] === $original['id']) + 1, $messages->search(fn ($m) => $m['id'] === $replacement['id']));
        $this->postJson('/api/clinical/sessions/'.$session['id'].'/turns', ['token' => $first['token'], 'text' => 'again'])->assertStatus(409);
    }

    public function test_streaming_emits_progress_then_one_validated_envelope(): void
    {
        $session = $this->begin(User::factory()->create());
        $response = $this->withHeaders(['Accept' => 'application/x-ndjson'])->post('/api/clinical/sessions/'.$session['id'].'/turns', ['token' => $session['token'], 'text' => 'My eye is red']);
        $response->assertOk();
        $events = array_map(fn ($line) => json_decode($line, true), array_filter(explode("\n", $response->streamedContent())));
        $this->assertSame(['received', 'extracting', 'screening', 'validated'], array_column(array_filter($events, fn ($e) => $e['type'] === 'stage'), 'stage'));
        $final = end($events);
        $this->assertSame('final', $final['type']);
        $this->assertSame('humantwin-clinical-assessment-v2', $final['envelope']['assessment']['schema_version']);
    }

    public function test_invalid_or_unapproved_engine_output_is_never_accepted(): void
    {
        $session = $this->begin(User::factory()->create());
        $this->fakeEngine(function (array $result) {
            $result['citations'][0]['url'] = 'https://evil.example/page';

            return $result;
        });
        $this->postJson('/api/clinical/sessions/'.$session['id'].'/turns', ['token' => $session['token'], 'text' => 'My eye is red'])->assertStatus(502)->assertJsonMissingPath('assessment');
        $this->fakeEngine(function (array $result) {
            unset($result['urgency']);

            return $result;
        });
        $response = $this->withHeaders(['Accept' => 'application/x-ndjson'])->post('/api/clinical/sessions/'.$session['id'].'/turns', ['token' => $session['token'], 'text' => 'My eye is red']);
        $events = array_map(fn ($line) => json_decode($line, true), array_filter(explode("\n", $response->streamedContent())));
        $this->assertSame('error', end($events)['type']);
        $this->assertSame(502, end($events)['status']);
        $this->assertSame(0, DB::table('clinical_sessions')->value('revision'), 'a rejected result does not advance the conversation');
    }

    public function test_saving_requires_consent_recomputes_on_the_server_and_is_owner_scoped(): void
    {
        $owner = User::factory()->create();
        $session = $this->answer($this->begin($owner), 'My eye is red');
        $this->postJson('/api/clinical/sessions/'.$session['id'].'/save', ['token' => $session['token']])->assertUnprocessable();
        $calls = count($this->sent);
        $this->postJson('/api/clinical/sessions/'.$session['id'].'/save', ['token' => $session['token'], 'consent' => true, 'consent_version' => 'clinical-storage-v1'])->assertOk();
        $this->assertSame($calls + 1, count($this->sent), 'the saved assessment is recomputed, not taken from the client');
        $record = ClinicalAssessment::firstOrFail();
        $this->assertStringNotContainsString('My eye is red', DB::table('clinical_assessments')->value('payload'), 'payload is encrypted at rest');
        $this->getJson('/api/clinical/assessments')->assertOk()->assertJsonPath('assessments.0.id', $record->id)->assertJsonPath('assessments.0.urgency', 'routine');
        $this->getJson('/api/clinical/assessments/'.$record->id)->assertOk()->assertJsonPath('messages.1.text', 'My eye is red');

        $intruder = User::factory()->create();
        $this->actingAs($intruder)->getJson('/api/clinical/assessments/'.$record->id)->assertNotFound();
        $this->deleteJson('/api/clinical/assessments/'.$record->id)->assertNotFound();
        $this->postJson('/api/clinical/sessions/'.$session['id'].'/turns', ['token' => $session['token'], 'text' => 'hi'])->assertNotFound();
        $this->assertSame(0, $this->actingAs($intruder)->getJson('/api/clinical/assessments')->json('assessments') ? 1 : 0);

        $this->actingAs($owner)->deleteJson('/api/clinical/assessments/'.$record->id)->assertNoContent();
        $this->assertDatabaseCount('clinical_assessments', 0);
        $this->assertDatabaseHas('audit_events', ['action' => 'clinical.assessment_deleted', 'owner_id' => $owner->id]);
    }

    public function test_patient_memory_is_shared_only_with_consent_and_opt_in(): void
    {
        $user = User::factory()->create();
        $this->actingAs($user)->postJson('/api/clinical/memory/consent', ['consent' => true, 'consent_version' => 'patient-memory-v1', 'retention_days' => 365])->assertOk();
        $this->postJson('/api/clinical/memory/facts', ['kind' => 'allergy', 'label' => 'Penicillin'])->assertCreated();
        $this->begin($user);
        $this->assertSame([], end($this->sent)['data']['patient_context']);
        $session = $this->begin($user, ['use_memory' => true]);
        $this->assertTrue($session['memory_shared']);
        $context = end($this->sent)['data']['patient_context'];
        $this->assertSame('Penicillin', $context[0]['label']);
        $this->assertSame('patient_memory', $context[0]['provenance']);
    }
}
