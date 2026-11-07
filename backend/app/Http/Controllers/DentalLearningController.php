<?php

namespace App\Http\Controllers;

use App\Services\DentalOwner;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Http;
use Illuminate\Validation\Rule;
use Throwable;

class DentalLearningController extends Controller
{
    public function index(Request $request): JsonResponse
    {
        return $this->proxy($request, 'GET', '/v1/dental/learning');
    }

    public function store(Request $request): JsonResponse
    {
        $data = $request->validate([
            'schema_version' => ['required', Rule::in(['humantwin-local-crowns-v1'])],
            'subject_code' => ['required', 'string', 'regex:/\A[A-Za-z0-9_-]{1,48}\z/'],
            'reviewer_code' => ['required', 'string', 'regex:/\A[A-Za-z0-9_-]{1,48}\z/'],
            'partition' => ['required', Rule::in(['train', 'validation', 'test'])],
            'permission_training' => 'required|accepted', 'complete_annotation' => 'required|accepted',
            'input_sha256' => ['required', 'string', 'regex:/\A[a-f0-9]{64}\z/'],
            'photo' => 'required|array:view,data_url',
            'photo.view' => ['required', Rule::in(['Frontal bite', 'Right bite', 'Left bite', 'Upper arch', 'Lower arch', 'Smile / profile'])],
            'photo.data_url' => ['required', 'string', 'max:350000', 'regex:/\Adata:image\/jpeg;base64,[A-Za-z0-9+\/=]+\z/'],
            'crowns' => 'required|array|min:1|max:32', 'crowns.*' => 'required|array:jaw,points',
            'crowns.*.jaw' => ['required', Rule::in(['upper', 'lower', 'unknown'])],
            'crowns.*.points' => 'required|array|min:4|max:12', 'crowns.*.points.*' => 'required|array:x,y',
            'crowns.*.points.*.x' => 'required|numeric|between:0,1', 'crowns.*.points.*.y' => 'required|numeric|between:0,1',
        ]);
        $raw = base64_decode(substr($data['photo']['data_url'], strlen('data:image/jpeg;base64,')), true);
        abort_if($raw === false || ! str_starts_with($raw, "\xff\xd8\xff") || ! str_ends_with($raw, "\xff\xd9") || hash('sha256', $raw) !== $data['input_sha256'], 422, 'The photo fingerprint is invalid.');
        $data['permission_training'] = true;
        $data['complete_annotation'] = true;

        return $this->proxy($request, 'POST', '/v1/dental/learning/examples', $data);
    }

    public function destroy(Request $request, string $exampleId): JsonResponse
    {
        return $this->proxy($request, 'DELETE', '/v1/dental/learning/examples/'.$exampleId);
    }

    public function train(Request $request): JsonResponse
    {
        $request->validate(['consent_training' => 'required|accepted']);

        return $this->proxy($request, 'POST', '/v1/dental/learning/train', ['consent_training' => true]);
    }

    private function proxy(Request $request, string $method, string $path, array $data = []): JsonResponse
    {
        try {
            $response = Http::timeout(20)->connectTimeout(3)->withHeaders([
                'X-Service-Key' => config('ai.key'), 'X-Dental-Owner' => DentalOwner::token((int) $request->user()->id),
            ])->acceptJson()->send($method, config('ai.url').$path, $data === [] ? [] : ['json' => $data]);
            if (! $response->successful()) {
                $status = in_array($response->status(), [404, 409, 422], true) ? $response->status() : 503;
                $message = match ($status) {
                    404 => 'Teaching example not found.',
                    409 => 'Check patient partitions and duplicate photos, or wait for the current training job. Training needs two training subjects and a different validation subject.',
                    422 => 'Check the photograph, complete crown outlines and teaching permissions.',
                    default => 'The local teaching service is unavailable. Your current photo is unchanged.',
                };

                return response()->json(['message' => $message], $status);
            }
            $result = $response->json();
            if (strlen($response->body()) > 150000 || ! is_array($result) || ! is_array($result['examples'] ?? null) || count($result['examples']) > 200
                || ($result['runtime'] ?? null) !== 'local' || ($result['external_requests'] ?? null) !== false || ($result['clinical_validation'] ?? null) !== false) {
                return response()->json(['message' => 'The local teaching response was invalid.'], 502);
            }
            $examples = [];
            $subjects = ['train' => [], 'validation' => [], 'test' => []];
            foreach ($result['examples'] as $row) {
                if (! is_array($row) || ! preg_match('/\A[a-f0-9]{64}\z/', (string) ($row['id'] ?? ''))
                    || ! preg_match('/\A[A-Za-z0-9_-]{1,48}\z/', (string) ($row['subject_code'] ?? ''))
                    || ! preg_match('/\A[A-Za-z0-9_-]{1,48}\z/', (string) ($row['reviewer_code'] ?? ''))
                    || ! in_array($row['partition'] ?? null, ['train', 'validation', 'test'], true)
                    || ! in_array($row['view'] ?? null, ['Frontal bite', 'Right bite', 'Left bite', 'Upper arch', 'Lower arch', 'Smile / profile'], true)
                    || ! is_int($row['crowns'] ?? null) || $row['crowns'] < 1 || $row['crowns'] > 32) {
                    return response()->json(['message' => 'The teaching-set metadata was invalid.'], 502);
                }
                $examples[] = array_intersect_key($row, array_flip(['id', 'subject_code', 'reviewer_code', 'partition', 'view', 'crowns']));
                $subjects[$row['partition']][strtolower($row['subject_code'])] = true;
            }
            $counts = array_map('count', $subjects);
            $state = $result['job']['state'] ?? 'idle';
            $phase = $result['job']['phase'] ?? 'idle';
            if (! in_array($state, ['idle', 'running', 'complete', 'failed', 'discarded'], true)
                || ! in_array($phase, ['idle', 'queued', 'checking', 'learning', 'validating', 'saving', 'complete', 'failed', 'discarded'], true)) {
                return response()->json(['message' => 'The training progress response was invalid.'], 502);
            }
            $model = $result['model'] ?? [];

            return response()->json([
                'runtime' => 'local', 'external_requests' => false, 'clinical_validation' => false, 'examples' => $examples,
                'subjects' => $counts, 'can_train' => $counts['train'] >= 2 && $counts['validation'] >= 1 && $state !== 'running',
                'job' => ['state' => $state, 'phase' => $phase],
                'model' => ['provider_configured' => ($model['provider_configured'] ?? false) === true,
                    'train_images' => max(0, min(200, (int) ($model['train_images'] ?? 0))),
                    'validation_images' => max(0, min(200, (int) ($model['validation_images'] ?? 0))),
                    'validation_dice' => is_numeric($model['validation_dice'] ?? null) ? max(0, min(1, (float) $model['validation_dice'])) : null],
            ]);
        } catch (Throwable) {
            return response()->json(['message' => 'The local teaching service is unavailable. Your current photo is unchanged.'], 503);
        }
    }
}
