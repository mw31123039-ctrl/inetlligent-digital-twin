<?php

namespace App\Http\Controllers;

use App\Models\EyeAssessment;
use App\Services\EyeAssessmentService;
use Illuminate\Http\Request;
use Illuminate\Validation\Rule;

class EyeAssessmentController extends Controller
{
    public function status()
    {
        $content = json_decode(file_get_contents(base_path('../contracts/eye/interview.v1.json')), true, flags: JSON_THROW_ON_ERROR);
        return response()->json(['clinical_use_available' => false, 'clinical_review_status' => 'draft', 'version' => $content['version'], 'question_count' => count($content['questions']), 'ai_required' => false]);
    }

    public function store(Request $request, EyeAssessmentService $service)
    {
        abort_if($request->input('use') === 'clinical', 409, 'Live eye triage is disabled pending clinical and medical translation review.');
        $anatomy = json_decode(file_get_contents(base_path('../contracts/eye/anatomy.v1.json')), true, flags: JSON_THROW_ON_ERROR);
        $data = $request->validate([
            'id' => 'required|uuid', 'use' => ['required', Rule::in(['education'])],
            'locale' => ['required', Rule::in(['en', 'ar-IQ', 'ckb'])],
            'model_side' => ['required', Rule::in(['left', 'right'])],
            'anatomy_explored' => 'present|array|max:100',
            'anatomy_explored.*' => ['string', 'distinct', Rule::in(array_column($anatomy['structures'], 'id'))],
            'turns' => 'required|array|min:1|max:120',
            'turns.*' => 'required|array:question_id,value,text',
            'turns.*.question_id' => 'required|string|max:80',
            'turns.*.value' => 'required|string|min:1|max:2000',
            'turns.*.text' => 'sometimes|string|min:1|max:2000',
            'consent' => 'required|accepted',
            'consent_version' => ['required', Rule::in(['health-storage-v1'])],
        ]);
        // The client sends only original answers and learning context, never trusted urgency or diagnoses.
        $session = $service->replay($data);
        $existing = EyeAssessment::find($data['id']);
        abort_if($existing && $existing->user_id !== $request->user()->id, 404);
        $record = EyeAssessment::updateOrCreate(['id' => $data['id'], 'user_id' => $request->user()->id], [
            'payload' => ['session' => $session], 'content_version' => $session['rule_version'],
            'consent_version' => $data['consent_version'], 'consented_at' => now(),
        ]);

        return response()->json(['id' => $record->id, 'saved' => true, 'clinical_use_available' => false], 201);
    }

    public function index(Request $request)
    {
        return EyeAssessment::where('user_id', $request->user()->id)->latest()->limit(50)->get()
            ->map(fn ($record) => ['id' => $record->id, 'created_at' => $record->created_at->toIso8601String()]);
    }

    public function show(Request $request, string $id)
    {
        $record = EyeAssessment::where('user_id', $request->user()->id)->findOrFail($id);

        return response()->json(['id' => $record->id, ...$record->payload]);
    }

    public function destroy(Request $request, string $id)
    {
        EyeAssessment::where('user_id', $request->user()->id)->findOrFail($id)->delete();

        return response()->noContent();
    }
}
