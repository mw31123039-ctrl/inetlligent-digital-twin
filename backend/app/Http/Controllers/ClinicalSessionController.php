<?php

namespace App\Http\Controllers;

use App\Models\ClinicalAssessment;
use App\Services\AuditLog;
use App\Services\ClinicalAiService;
use App\Services\ClinicalSessionTokens;
use App\Services\PatientMemory;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Http\Response;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use Illuminate\Validation\Rule;
use Symfony\Component\HttpFoundation\StreamedResponse;
use Symfony\Component\HttpKernel\Exception\HttpExceptionInterface;

/**
 * Clinical assessment v2 conversations: anatomy-aware adaptive interview with in-place corrections,
 * optional NDJSON progress streaming and consented saving of a server-recomputed assessment.
 */
class ClinicalSessionController extends Controller
{
    public const CONSENT_VERSION = 'clinical-storage-v1';

    private const LOCALES = ['en', 'ar', 'ckb'];

    private const SIDES = ['left', 'right', 'both', 'midline', 'unknown'];

    public function __construct(private ClinicalAiService $ai, private ClinicalSessionTokens $tokens, private PatientMemory $memory, private AuditLog $audit) {}

    public function status(): array
    {
        return [...$this->ai->status(), 'clinical_review_required' => true];
    }

    public function catalog(): array
    {
        return $this->ai->catalog();
    }

    public function coverage(): array
    {
        return $this->ai->coverage();
    }

    public function store(Request $request): JsonResponse
    {
        $data = $request->validate([
            'anatomy_id' => ['required', 'string', Rule::in($this->ai->anatomyIds())],
            'side' => ['required', Rule::in(self::SIDES)],
            'locale' => ['required', Rule::in(self::LOCALES)],
            'processing_acknowledged' => 'required|accepted',
            'use_memory' => 'sometimes|boolean',
        ]);
        $userId = $request->user()->id;
        $state = [
            'kind' => 'clinical-v2', 'id' => (string) Str::uuid(), 'user_id' => $userId, 'revision' => 0, 'locale' => $data['locale'],
            'anatomy' => ['id' => $data['anatomy_id'], 'side' => $data['side']],
            'use_memory' => ($data['use_memory'] ?? false) && $this->memory->consent($userId) !== null,
            'messages' => [], 'prior_urgency' => null,
        ];
        $assessment = $this->ai->assess($this->payload($state));
        $this->appendQuestion($state, $assessment);
        DB::table('clinical_sessions')->insert(['id' => $state['id'], 'user_id' => $userId, 'revision' => 0, 'expires_at' => now()->addMinutes(config('ai.conversation_minutes'))]);
        $this->audit->record('clinical.session_started', $userId, $userId, 'clinical_session', $state['id'], ['memory_shared' => $state['use_memory']]);

        return response()->json($this->envelope($state, $assessment), 201);
    }

    public function turn(Request $request, string $id): JsonResponse|StreamedResponse
    {
        $data = $request->validate([
            'token' => 'required|string|max:450000',
            'text' => 'required|string|min:1|max:2000',
            'answer_codes' => 'sometimes|array|max:20',
            'answer_codes.*' => ['string', 'max:80', 'regex:/\A[a-z_]{2,20}(:[A-Za-z0-9_.\-]{1,60})?\z/'],
            'correct_message_id' => 'nullable|uuid',
            'locale' => ['sometimes', Rule::in(self::LOCALES)],
        ]);
        $state = $this->tokens->decode($data['token'], $request->user()->id, $id);
        if (isset($data['locale'])) {
            $state['locale'] = $data['locale'];
        }
        $this->applyAnswer($state, trim($data['text']), $data['answer_codes'] ?? [], $data['correct_message_id'] ?? null);
        $payload = $this->payload($state);

        if (str_contains((string) $request->header('Accept'), 'application/x-ndjson')) {
            return response()->stream(function () use ($state, $payload) {
                $emit = function (array $event): void {
                    echo json_encode($event, JSON_UNESCAPED_UNICODE)."\n";
                    if (ob_get_level() > 0) {
                        ob_flush();
                    }
                    flush();
                };
                $emit(['type' => 'stage', 'stage' => 'received']);
                try {
                    $assessment = $this->ai->streamAssess($payload, fn (string $stage) => $emit(['type' => 'stage', 'stage' => $stage]));
                    $emit(['type' => 'stage', 'stage' => 'validated']);
                    $emit(['type' => 'final', 'envelope' => $this->complete($state, $assessment)]);
                } catch (HttpExceptionInterface $exception) {
                    $emit(['type' => 'error', 'status' => $exception->getStatusCode(), 'message' => $exception->getMessage()]);
                }
            }, 200, ['Content-Type' => 'application/x-ndjson; charset=utf-8', 'X-Accel-Buffering' => 'no', 'Cache-Control' => 'no-store, private']);
        }

        return response()->json($this->complete($state, $this->ai->assess($payload)));
    }

    public function save(Request $request, string $id): JsonResponse
    {
        $data = $request->validate([
            'token' => 'required|string|max:450000',
            'consent' => 'required|accepted',
            'consent_version' => ['required', Rule::in([self::CONSENT_VERSION])],
            'previous_id' => 'nullable|uuid',
        ]);
        $userId = $request->user()->id;
        $state = $this->tokens->decode($data['token'], $userId, $id);
        abort_if(! collect($state['messages'])->contains('role', 'user'), 422, 'Answer at least one question before saving.');
        $previous = isset($data['previous_id']) ? ClinicalAssessment::where('user_id', $userId)->find($data['previous_id']) : null;
        abort_if(isset($data['previous_id']) && ! $previous, 404);
        // The stored assessment is recomputed on the server from the transcript; the client cannot alter it.
        $assessment = $this->ai->assess($this->payload($state));
        $record = ClinicalAssessment::updateOrCreate(['id' => $id, 'user_id' => $userId], [
            'payload' => ['messages' => $state['messages'], 'assessment' => $assessment, 'locale' => $state['locale'], 'anatomy' => $state['anatomy'], 'previous_id' => $previous?->id],
            'consent_version' => $data['consent_version'],
            'consented_at' => now(),
        ]);
        $this->audit->record('clinical.assessment_saved', $userId, $userId, 'clinical_assessment', $record->id, ['knowledge' => $assessment['versions']['knowledge']]);

        return response()->json(['id' => $record->id, 'saved' => true, 'created_at' => $record->created_at->toIso8601String()]);
    }

    public function destroy(Request $request, string $id): Response
    {
        $userId = $request->user()->id;
        $deleted = DB::table('clinical_sessions')->where('id', $id)->where('user_id', $userId)->delete();
        abort_unless($deleted === 1, 404);
        $this->audit->record('clinical.session_deleted', $userId, $userId, 'clinical_session', $id);

        return response()->noContent();
    }

    /**
     * @param  array<string, mixed>  $state
     * @param  array<int, string>  $codes
     */
    private function applyAnswer(array &$state, string $text, array $codes, ?string $correctId): void
    {
        $message = ['id' => (string) Str::uuid(), 'role' => 'user', 'text' => $text, 'question_id' => null, 'answer_codes' => array_values(array_unique($codes)), 'superseded_by' => null];
        if ($correctId !== null) {
            $index = collect($state['messages'])->search(fn (array $item) => $item['id'] === $correctId && $item['role'] === 'user' && $item['superseded_by'] === null);
            abort_if($index === false, 422, 'The answer to correct was not found.');
            // The original stays in the transcript (marked superseded) so the change is auditable and comparable.
            $state['messages'][$index]['superseded_by'] = $message['id'];
            $message['question_id'] = $state['messages'][$index]['question_id'];
            array_splice($state['messages'], $index + 1, 0, [$message]);
            $last = end($state['messages']);
            if ($last['role'] === 'assistant') {
                array_pop($state['messages']); // re-ask from the updated case instead of a stale pending question
            }
        } else {
            $last = end($state['messages']);
            $message['question_id'] = $last && $last['role'] === 'assistant' ? $last['question_id'] : null;
            $state['messages'][] = $message;
        }
        abort_if(count($state['messages']) > 86, 422, 'This conversation has reached its limit. Save it or start a new assessment.');
    }

    /**
     * @param  array<string, mixed>  $state
     * @param  array<string, mixed>  $assessment
     * @return array<string, mixed>
     */
    private function complete(array $state, array $assessment): array
    {
        $this->appendQuestion($state, $assessment);
        $state['prior_urgency'] = ['level' => $assessment['urgency']['level'], 'rule_ids' => array_slice(array_column($assessment['urgency']['reasons'], 'rule_id'), 0, 40)];
        abort_unless($this->tokens->advance($state['id'], $state['user_id'], $state['revision']), 409, 'Another reply changed this conversation. Reload or start a new assessment.');
        $state['revision']++;

        return $this->envelope($state, $assessment);
    }

    /**
     * @param  array<string, mixed>  $state
     * @param  array<string, mixed>  $assessment
     */
    private function appendQuestion(array &$state, array $assessment): void
    {
        $question = $assessment['next_question'] ?? null;
        if ($question) {
            $state['messages'][] = ['id' => (string) Str::uuid(), 'role' => 'assistant', 'text' => mb_substr($question['text'], 0, 2000), 'question_id' => $question['id'], 'answer_codes' => [], 'superseded_by' => null];
        }
        abort_if(strlen(json_encode($state, JSON_THROW_ON_ERROR)) > 300000, 422, 'This conversation reached its safe size limit. Save it or start a new assessment.');
    }

    /**
     * @param  array<string, mixed>  $state
     * @return array<string, mixed>
     */
    private function payload(array $state): array
    {
        return [
            'locale' => $state['locale'],
            'anatomy' => $state['anatomy'],
            'messages' => array_map(fn (array $message) => [
                'id' => $message['id'], 'role' => $message['role'], 'text' => $message['text'], 'question_id' => $message['question_id'],
                'answer_codes' => $message['answer_codes'], 'superseded_by' => $message['superseded_by'],
            ], $state['messages']),
            'patient_context' => $state['use_memory'] ? $this->memory->context($state['user_id']) : [],
            'prior_urgency' => $state['prior_urgency'],
            'max_questions' => (int) config('ai.clinical_max_questions'),
        ];
    }

    /**
     * @param  array<string, mixed>  $state
     * @param  array<string, mixed>  $assessment
     * @return array<string, mixed>
     */
    private function envelope(array $state, array $assessment): array
    {
        return ['id' => $state['id'], 'revision' => $state['revision'], 'token' => $this->tokens->encode($state), 'locale' => $state['locale'],
            'memory_shared' => $state['use_memory'], 'messages' => $state['messages'], 'assessment' => $assessment];
    }
}
