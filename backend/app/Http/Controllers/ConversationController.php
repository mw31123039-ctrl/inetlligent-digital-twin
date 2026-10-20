<?php

namespace App\Http\Controllers;

use App\Models\HealthAssessment;
use App\Services\AiService;
use App\Services\ConversationTokens;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use Illuminate\Validation\Rule;

class ConversationController extends Controller
{
    public function __construct(private AiService $ai, private ConversationTokens $tokens) {}

    private function envelope(array $state): array
    {
        return ['id' => $state['id'], 'revision' => $state['revision'], 'token' => $this->tokens->encode($state), 'messages' => $state['messages'], 'assessment' => $state['assessment']];
    }

    private function appendReply(array &$state): void
    {
        $result = $state['assessment'];
        $text = $result['next_question']['text'] ?? ($result['phase'] === 'urgent' ? $result['recommended_next_action'] : 'Your reported information is summarized below. This is not a diagnosis.');
        $state['messages'][] = ['id' => (string) Str::uuid(), 'role' => 'assistant', 'text' => $text, 'field' => $result['next_question']['field'] ?? null];
        abort_if(strlen(json_encode($state, JSON_THROW_ON_ERROR)) > 160000, 422, 'This conversation reached its safe size limit. Download the current summary and start a new assessment.');
    }

    private function reportedSide(array $state): string
    {
        $side = $state['initial_side'] ?? $state['side'];
        $field = 'symptoms';
        foreach ($state['messages'] as $message) {
            if ($message['role'] === 'assistant') { $field = $message['field'] ?? 'symptoms'; continue; }
            // Only an explicit location answer is normalized. Narrative mentions
            // ("not my left eye") must never become an inferred positive finding.
            if ($field === 'location' && preg_match('/^(left|right|both)(?: (?:eye|eyes|arm|arms|leg|legs|side|sides|hand|hands|foot|feet))?[.!]?$/i', $message['text'], $matches)) {
                $side = strtolower($matches[1]);
            }
        }
        return $side;
    }

    public function store(Request $request)
    {
        $data = $request->validate([
            'region' => ['required', Rule::in(['eyes', 'head', 'chest', 'abdomen', 'arms', 'legs'])],
            'side' => ['required', Rule::in(['unknown', 'left', 'right', 'both', 'center', 'not_applicable'])],
            'processing_acknowledged' => 'required|accepted',
        ]);
        $state = ['id' => (string) Str::uuid(), 'user_id' => $request->user()->id, 'revision' => 0,
            'region' => $data['region'], 'side' => $data['side'], 'initial_side' => $data['side'], 'messages' => [], 'assessment' => null];
        $state['assessment'] = $this->ai->assess($state);
        $this->appendReply($state);
        DB::table('conversation_sessions')->insert(['id' => $state['id'], 'user_id' => $state['user_id'], 'revision' => 0, 'expires_at' => now()->addMinutes(config('ai.conversation_minutes'))]);
        return response()->json($this->envelope($state), 201);
    }

    public function turn(Request $request, string $id)
    {
        $data = $request->validate(['token' => 'required|string|max:350000', 'text' => 'required|string|min:1|max:2000', 'correct_message_id' => 'nullable|uuid']);
        $state = $this->tokens->decode($data['token'], $request->user()->id, $id);
        if (!empty($data['correct_message_id'])) {
            $index = null;
            foreach ($state['messages'] as $key => $message) {
                if ($message['id'] === $data['correct_message_id'] && $message['role'] === 'user') { $index = $key; break; }
            }
            abort_if($index === null, 422, 'The answer to correct was not found.');
            // Truncate derived replies and answers so stale facts never survive an edit.
            $state['messages'] = array_slice($state['messages'], 0, $index);
        }
        abort_if(count($state['messages']) >= 58, 422, 'This conversation has reached its limit. Start a new assessment.');
        $state['messages'][] = ['id' => (string) Str::uuid(), 'role' => 'user', 'text' => trim($data['text']), 'field' => null];
        $state['side'] = $this->reportedSide($state);
        $state['assessment'] = $this->ai->assess($state);
        $this->appendReply($state);
        $updated = DB::table('conversation_sessions')->where('id', $id)->where('user_id', $request->user()->id)->where('revision', $state['revision'])->update(['revision' => $state['revision'] + 1]);
        abort_unless($updated === 1, 409, 'Another reply changed this conversation. Start a new assessment.');
        $state['revision']++;
        return response()->json($this->envelope($state));
    }

    public function save(Request $request, string $id)
    {
        $data = $request->validate(['token' => 'required|string|max:350000', 'consent' => 'required|accepted', 'consent_version' => ['required', Rule::in(['health-storage-v1'])]]);
        $state = $this->tokens->decode($data['token'], $request->user()->id, $id);
        $record = HealthAssessment::updateOrCreate(['id' => $id, 'user_id' => $request->user()->id], [
            'payload' => ['messages' => $state['messages'], 'assessment' => $state['assessment']],
            'consent_version' => $data['consent_version'], 'consented_at' => now(),
        ]);
        return response()->json(['id' => $record->id, 'saved' => true]);
    }

    public function index(Request $request)
    {
        return HealthAssessment::where('user_id', $request->user()->id)->latest()->limit(50)->get()->map(fn ($item) => [
            'id' => $item->id, 'created_at' => $item->created_at->toIso8601String(), 'region' => $item->payload['assessment']['selected_region'],
        ]);
    }

    public function show(Request $request, string $id)
    {
        $record = HealthAssessment::where('user_id', $request->user()->id)->findOrFail($id);
        return response()->json(['id' => $record->id, ...$record->payload]);
    }

    public function destroy(Request $request, string $id)
    {
        $userId = $request->user()->id;
        $exists = DB::table('conversation_sessions')->where('id', $id)->where('user_id', $userId)->exists()
            || HealthAssessment::where('id', $id)->where('user_id', $userId)->exists();
        abort_unless($exists, 404);
        DB::transaction(function () use ($id, $userId) {
            HealthAssessment::where('id', $id)->where('user_id', $userId)->delete();
            DB::table('conversation_sessions')->where('id', $id)->where('user_id', $userId)->delete();
        });
        return response()->noContent();
    }
}
