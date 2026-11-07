<?php

namespace App\Http\Controllers;

use App\Services\DentalOwner;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Http;
use Illuminate\Validation\Rule;
use Opis\JsonSchema\Validator;
use Throwable;

class DentalPhotoController extends Controller
{
    public function status(Request $request): JsonResponse
    {
        try {
            $user = $request->user('sanctum');
            $headers = ['X-Service-Key' => config('ai.key')];
            if ($user) {
                $headers['X-Dental-Owner'] = DentalOwner::token((int) $user->id);
            }
            $response = Http::timeout(3)->withHeaders($headers)->get(config('ai.url').'/v1/dental/detection-status');
            if ($response->successful()) {
                return response()->json([
                    'available' => true,
                    'provider_configured' => $response->json('runtime') === 'local' && $response->json('state') === 'trained-unvalidated' && $response->json('provider_configured') === true,
                    'model_capability_verified' => false, 'draft_only' => true, 'runtime' => 'local', 'external_requests' => false,
                    'state' => $response->json('runtime') === 'local' && in_array($response->json('state'), ['trained-unvalidated', 'training'], true) ? $response->json('state') : 'not-trained',
                    'model_source' => $response->json('model_source') === 'public-dataset' ? 'public-dataset' : 'reviewed-local-examples',
                    'train_images' => max(0, min(100000, (int) $response->json('train_images'))),
                    'validation_images' => max(0, min(100000, (int) $response->json('validation_images'))),
                    'validation_dice' => $response->json('model_source') !== 'public-dataset' && is_numeric($response->json('validation_dice')) ? max(0, min(1, (float) $response->json('validation_dice'))) : null,
                    ...($response->json('state') === 'training' ? [
                        'training_epoch' => max(0, min(500, (int) $response->json('training_epoch'))),
                        'training_epochs' => max(0, min(500, (int) $response->json('training_epochs'))),
                    ] : []),
                ]);
            }
        } catch (Throwable) {
        }

        return response()->json(['available' => false, 'provider_configured' => false, 'model_capability_verified' => false, 'draft_only' => true, 'runtime' => 'local', 'external_requests' => false, 'state' => 'unavailable', 'train_images' => 0, 'validation_images' => 0, 'validation_dice' => null]);
    }

    public function detect(Request $request): JsonResponse
    {
        return $this->outline($request, false);
    }

    public function segment(Request $request): JsonResponse
    {
        return $this->outline($request, true);
    }

    private function outline(Request $request, bool $assisted): JsonResponse
    {
        $rules = [
            'photo' => 'required|array:view,data_url',
            'photo.view' => ['required', Rule::in(['Frontal bite', 'Right bite', 'Left bite', 'Upper arch', 'Lower arch', 'Smile / profile'])],
            'photo.data_url' => ['required', 'string', 'max:350000', 'regex:/\Adata:image\/jpeg;base64,[A-Za-z0-9+\/=]+\z/'],
            'consent_local' => 'required|accepted',
        ];
        if ($assisted) {
            $rules = [...$rules, 'prompt' => 'required|array:jaw,points', 'prompt.jaw' => ['required', Rule::in(['upper', 'lower', 'unknown'])],
                'prompt.points' => 'required|array|min:4|max:12', 'prompt.points.*' => 'required|array:x,y',
                'prompt.points.*.x' => 'required|numeric|between:0,1', 'prompt.points.*.y' => 'required|numeric|between:0,1'];
        }
        $data = $request->validate($rules);
        if ($assisted) {
            abort_unless($this->validPolygons([$data['prompt']]), 422, 'A valid rough crown outline is required.');
        }
        $raw = base64_decode(substr($data['photo']['data_url'], strlen('data:image/jpeg;base64,')), true);
        abort_if($raw === false || strlen($raw) < 100 || ! str_starts_with($raw, "\xff\xd8\xff") || ! str_ends_with($raw, "\xff\xd9"), 422, 'A re-encoded JPEG photograph is required.');
        $data['consent_local'] = true;

        try {
            $response = Http::timeout(62)->connectTimeout(3)->withHeaders(['X-Service-Key' => config('ai.key'), 'X-Dental-Owner' => DentalOwner::token((int) $request->user()->id)])->acceptJson()
                ->post(config('ai.url').($assisted ? '/v1/dental/segment' : '/v1/dental/detect'), $data);
            if (! $response->successful() || strlen($response->body()) > 50000) {
                return response()->json(['message' => 'The local outline tool could not return a draft. Check the local model status or outline crowns manually.'], 503);
            }
            $schema = json_decode(file_get_contents(base_path('../contracts/dental/photo-detection.schema.json')));
            $document = json_decode($response->body());
            if (! (new Validator)->validate($document, $schema)->isValid()) {
                return response()->json(['message' => 'The tooth-outline response failed validation. No draft was applied.'], 502);
            }
            $result = $response->json();
            if ($result['possible_case_ids'] !== [] || ($assisted && count($result['crowns']) > 1)
                || $result['input_sha256'] !== hash('sha256', $raw)
                || ($result['image_quality'] !== 'usable' && ($result['crowns'] !== [] || $result['possible_case_ids'] !== []))
                || ($result['image_quality'] === 'usable' && $result['crowns'] === []) || ! $this->validPolygons($result['crowns'])) {
                return response()->json(['message' => 'The outlines did not match the submitted photo or geometry constraints. No draft was applied.'], 502);
            }

            return response()->json($result);
        } catch (Throwable) {
            return response()->json(['message' => 'The detector could not return a valid draft. Your original photograph is unchanged.'], 503);
        }
    }

    private function validPolygons(array $crowns): bool
    {
        foreach ($crowns as $crown) {
            $points = $crown['points'];
            $count = count($points);
            $area = 0.0;
            for ($i = 0; $i < $count; $i++) {
                $a = $points[$i];
                $b = $points[($i + 1) % $count];
                $area += $a['x'] * $b['y'] - $b['x'] * $a['y'];
            }
            if (abs($area) / 2 < .00001 || abs($area) / 2 > .8) {
                return false;
            }
            for ($i = 0; $i < $count; $i++) {
                for ($j = $i + 1; $j < $count; $j++) {
                    if ($j === $i + 1 || ($i === 0 && $j === $count - 1)) {
                        continue;
                    }
                    $a = $points[$i];
                    $b = $points[($i + 1) % $count];
                    $c = $points[$j];
                    $d = $points[($j + 1) % $count];
                    if ($this->cross($a, $b, $c) * $this->cross($a, $b, $d) < 0 && $this->cross($c, $d, $a) * $this->cross($c, $d, $b) < 0) {
                        return false;
                    }
                }
            }
        }

        return true;
    }

    private function cross(array $a, array $b, array $c): float
    {
        return ($b['x'] - $a['x']) * ($c['y'] - $a['y']) - ($b['y'] - $a['y']) * ($c['x'] - $a['x']);
    }
}
