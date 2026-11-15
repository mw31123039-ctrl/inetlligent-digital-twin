<?php

namespace App\Http\Controllers;

use App\Models\CancerReport;
use App\Services\CancerResultContract;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Http\Response;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\Crypt;
use Illuminate\Validation\Rule;

/**
 * Saved cancer research reports ("History"). Only a result that this server received from the
 * local model for the signed-in user within the last 30 minutes can be saved; the client cannot
 * submit or alter model output.
 */
class CancerReportController extends Controller
{
    public const CONSENT_VERSION = 'cancer-report-storage-v1';

    public const MAX_REPORTS = 50;

    public function store(Request $request, CancerResultContract $contract): JsonResponse
    {
        $data = $request->validate([
            'input_sha256' => ['required', 'string', 'regex:/\A[a-f0-9]{64}\z/'],
            'thumbnail_data_url' => ['required', 'string', 'max:300000', 'regex:/\Adata:image\/jpeg;base64,[A-Za-z0-9+\/=]+\z/'],
            'note' => ['nullable', 'string', 'max:500'],
            'consent' => 'required|accepted',
            'consent_version' => ['required', Rule::in([self::CONSENT_VERSION])],
        ]);
        $thumbnail = base64_decode(substr($data['thumbnail_data_url'], strlen('data:image/jpeg;base64,')), true);
        abort_if($thumbnail === false || strlen($thumbnail) < 100 || ! str_starts_with($thumbnail, "\xff\xd8\xff") || ! str_ends_with($thumbnail, "\xff\xd9"), 422, 'A JPEG preview image is required.');

        $userId = $request->user()->id;
        $cached = Cache::get(CancerResearchController::resultCacheKey($userId, $data['input_sha256']));
        abort_if(! is_string($cached), 409, 'This result is no longer available to save. Run the analysis again, then save it.');
        $result = json_decode(Crypt::decryptString($cached), true, flags: JSON_THROW_ON_ERROR);
        abort_if($contract->outcomeViolation($result) !== null, 409, 'This result cannot be saved.');
        abort_if(CancerReport::where('user_id', $userId)->count() >= self::MAX_REPORTS, 409, 'History holds up to 50 reports. Delete an older report first.');

        $report = CancerReport::create([
            'user_id' => $userId,
            'payload' => ['result' => $result, 'thumbnail_data_url' => $data['thumbnail_data_url'], 'note' => $data['note'] ?? null],
            'consent_version' => $data['consent_version'],
            'consented_at' => now(),
        ]);

        return response()->json(['id' => $report->id, 'saved' => true, 'created_at' => $report->created_at->toIso8601String()], 201);
    }

    public function index(Request $request): JsonResponse
    {
        $reports = CancerReport::where('user_id', $request->user()->id)->latest()->limit(self::MAX_REPORTS)->get();

        return response()->json(['reports' => $reports->map(fn (CancerReport $report) => $this->summary($report))->values()]);
    }

    public function show(Request $request, string $id): JsonResponse
    {
        $report = CancerReport::where('user_id', $request->user()->id)->findOrFail($id);

        return response()->json([...$this->summary($report), 'result' => $report->payload['result'],
            'thumbnail_data_url' => $report->payload['thumbnail_data_url'], 'note' => $report->payload['note'] ?? null]);
    }

    public function destroy(Request $request, string $id): Response
    {
        CancerReport::where('user_id', $request->user()->id)->findOrFail($id)->delete();

        return response()->noContent();
    }

    /**
     * @return array{id: string, created_at: string, track: string, modality: string, outcome: string, finding_label: string|null, top_label: string|null, probability: float|null, model_version: string}
     */
    private function summary(CancerReport $report): array
    {
        $result = $report->payload['result'];

        return ['id' => $report->id, 'created_at' => $report->created_at->toIso8601String(), 'track' => $result['track'],
            'modality' => $result['modality'], 'outcome' => $result['outcome'], 'finding_label' => $result['finding_label'] ?? null,
            'top_label' => $result['confidence']['top_label'] ?? null, 'probability' => $result['confidence']['probability'] ?? null,
            'model_version' => $result['model_version']];
    }
}
