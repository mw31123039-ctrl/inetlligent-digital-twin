<?php

namespace App\Http\Controllers;

use App\Services\CancerResultContract;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\Crypt;
use Illuminate\Support\Facades\Http;
use Illuminate\Validation\Rule;
use Opis\JsonSchema\Validator;
use Throwable;

class CancerResearchController extends Controller
{
    private const MODALITIES = [
        'skin' => ['skin_photo', 'dermoscopy'],
        'oral' => ['oral_photo'],
        'lung' => ['lung_ct_slice'],
        'breast' => ['mammogram', 'breast_ultrasound', 'breast_mri_slice'],
    ];

    public function status(): JsonResponse
    {
        $pathways = [];
        $upstream = null;
        try {
            $response = Http::timeout(8)->connectTimeout(3)->withHeaders(['X-Service-Key' => config('ai.key')])
                ->acceptJson()->get(config('ai.url').'/v1/cancer/status');
            if ($response->successful() && strlen($response->body()) <= 40000 && $response->json('available') === true
                && $response->json('clinical_validation') === false && $response->json('external_requests') === false
                && $response->json('scope') === 'single-2d-image' && is_array($response->json('pathways'))) {
                $upstream = $response->json('pathways');
            }
        } catch (Throwable) {
        }

        foreach (self::MODALITIES as $track => $modalities) {
            $models = [];
            foreach ($modalities as $modality) {
                $candidate = collect($upstream ?? [])->firstWhere('track', $track);
                $model = is_array($candidate['models'] ?? null) ? collect($candidate['models'])->firstWhere('modality', $modality) : null;
                $configured = ($model['configured'] ?? false) === true && ($model['state'] ?? null) === 'configured-unvalidated'
                    && is_string($model['model_version'] ?? null) && preg_match('/\A[A-Za-z0-9][A-Za-z0-9._-]{0,79}\z/', $model['model_version'])
                    && is_string($model['weights_sha256'] ?? null) && preg_match('/\A[a-f0-9]{64}\z/', $model['weights_sha256'])
                    && is_string($model['target'] ?? null) && strlen($model['target']) >= 1 && strlen($model['target']) <= 640;
                $item = ['modality' => $modality, 'configured' => (bool) $configured,
                    'state' => $configured ? 'configured-unvalidated' : ($upstream === null ? 'service-unavailable' : (($model['state'] ?? null) === 'invalid-artifacts' ? 'invalid-artifacts' : 'not-configured'))];
                if ($configured) {
                    $item = [...$item, 'model_version' => $model['model_version'], 'target' => $model['target'], 'weights_sha256' => $model['weights_sha256']];
                    $labels = $model['labels'] ?? null;
                    if (is_array($labels) && count($labels) >= 2 && count($labels) <= 20
                        && collect($labels)->every(fn ($label) => is_string($label) && strlen($label) >= 1 && strlen($label) <= 80)) {
                        $item['labels'] = array_values($labels);
                    }
                    if (in_array($model['heatmap_method'] ?? null, ['grad-cam', 'attention-rollout', 'occlusion-sensitivity'], true)) {
                        $item['heatmap_method'] = $model['heatmap_method'];
                    }
                    $item['calibration'] = ($model['calibration'] ?? null) === 'temperature-scaled' ? 'temperature-scaled' : 'none';
                }
                $models[] = $item;
            }
            $pathways[] = ['track' => $track, 'models' => $models];
        }

        return response()->json(['available' => $upstream !== null, 'clinical_validation' => false,
            'external_requests' => false, 'scope' => 'single-2d-image', 'pathways' => $pathways]);
    }

    public function analyze(Request $request, CancerResultContract $contract): JsonResponse
    {
        $data = $request->validate([
            'track' => ['required', Rule::in(array_keys(self::MODALITIES))],
            'modality' => ['required', Rule::in(array_merge(...array_values(self::MODALITIES)))],
            'image_data_url' => ['required', 'string', 'max:1500000', 'regex:/\Adata:image\/jpeg;base64,[A-Za-z0-9+\/=]+\z/'],
            'consent_local' => 'required|accepted',
            'modality_confirmed' => 'required|accepted',
            'research_only_acknowledged' => 'required|accepted',
            'explain' => 'sometimes|boolean',
        ]);
        abort_unless(in_array($data['modality'], self::MODALITIES[$data['track']], true), 422, 'The modality does not match this pathway.');
        $raw = base64_decode(substr($data['image_data_url'], strlen('data:image/jpeg;base64,')), true);
        abort_if($raw === false || strlen($raw) < 100 || ! str_starts_with($raw, "\xff\xd8\xff") || ! str_ends_with($raw, "\xff\xd9"), 422, 'A re-encoded JPEG image is required.');
        $data['consent_local'] = true;
        $data['modality_confirmed'] = true;
        $data['research_only_acknowledged'] = true;

        try {
            $response = Http::timeout(45)->connectTimeout(3)->withHeaders(['X-Service-Key' => config('ai.key')])
                ->acceptJson()->post(config('ai.url').'/v1/cancer/analyze', $data);
            if (! $response->successful() || strlen($response->body()) > 60000) {
                return response()->json(['message' => 'No research result was generated. Check that a compatible local model is installed.'], 503);
            }
            $violation = $contract->violation($response->body(), $data, $raw);
            if ($violation !== null) {
                return response()->json(['message' => $violation], 502);
            }
            $result = $response->json();
            // Kept briefly, encrypted, so the user can save exactly this output to their history.
            Cache::put($this->resultCacheKey($request->user()->id, $result['input_sha256']), Crypt::encryptString(json_encode($result, JSON_THROW_ON_ERROR)), now()->addMinutes(30));

            return response()->json($result);
        } catch (Throwable) {
            return response()->json(['message' => 'The local research model is unavailable. No result was generated.'], 503);
        }
    }

    public static function resultCacheKey(int $userId, string $inputSha256): string
    {
        return 'cancer-result:'.$userId.':'.$inputSha256;
    }

    public function knowledgeStatus(): JsonResponse
    {
        $configured = false;
        try {
            $response = Http::timeout(8)->connectTimeout(3)->withHeaders(['X-Service-Key' => config('ai.key')])
                ->acceptJson()->get(config('ai.url').'/v1/cancer/knowledge-status');
            $configured = $response->successful() && strlen($response->body()) <= 12000
                && $response->json('configured') === true && $response->json('available') === true
                && $response->json('clinical_validation') === false && $response->json('external_requests') === false
                && $response->json('method') === 'local-semantic-retrieval'
                && $response->json('corpus_version') === 'oncology-reference-2026-11-13';
        } catch (Throwable) {
        }

        return response()->json(['available' => (bool) $configured, 'configured' => (bool) $configured,
            'method' => 'local-semantic-retrieval', 'clinical_validation' => false, 'external_requests' => false]);
    }

    public function knowledge(Request $request): JsonResponse
    {
        $data = $request->validate(['question' => 'required|string|min:3|max:600', 'consent_local' => 'required|accepted']);
        $data['question'] = trim($data['question']);
        abort_if(mb_strlen($data['question']) < 3, 422, 'Enter a question of at least three characters.');
        $data['consent_local'] = true;
        try {
            $response = Http::timeout(25)->connectTimeout(3)->withHeaders(['X-Service-Key' => config('ai.key')])
                ->acceptJson()->post(config('ai.url').'/v1/cancer/knowledge', $data);
            if (! $response->successful() || strlen($response->body()) > 20000) {
                return response()->json(['message' => 'Local evidence search is unavailable. The source library remains available to browse.'], 503);
            }
            $schema = json_decode(file_get_contents(base_path('../contracts/cancer-knowledge-result.schema.json')));
            if (! (new Validator)->validate(json_decode($response->body()), $schema)->isValid()) {
                return response()->json(['message' => 'The evidence response failed validation. No answer was accepted.'], 502);
            }
            $result = $response->json();
            if ($result['question_sha256'] !== hash('sha256', $data['question'])
                || count(array_unique(array_column($result['matches'], 'record_id'))) !== count($result['matches'])) {
                return response()->json(['message' => 'The evidence response did not match this question. No answer was accepted.'], 502);
            }

            return response()->json($result);
        } catch (Throwable) {
            return response()->json(['message' => 'The local evidence model could not complete this request. Browse the source library instead.'], 503);
        }
    }
}
