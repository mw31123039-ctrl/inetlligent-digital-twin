<?php

namespace App\Http\Controllers;

use App\Services\DentalOwner;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Http;
use Opis\JsonSchema\Validator;
use Throwable;

class DentalScreeningController extends Controller
{
    public function index(Request $request): JsonResponse
    {
        return $this->proxy($request, 'GET', '/v1/dental/screening/cases');
    }

    public function store(Request $request): JsonResponse
    {
        $data = json_decode($request->getContent(), true);
        abort_unless($this->validRecord($data) && ($data['consent_storage'] ?? false) === true, 422, 'A valid screening record and explicit local-storage permission are required.');

        return $this->proxy($request, 'POST', '/v1/dental/screening/cases', $data);
    }

    public function show(Request $request, string $caseId): JsonResponse
    {
        return $this->proxy($request, 'GET', '/v1/dental/screening/cases/'.$caseId, [], true);
    }

    public function destroy(Request $request, string $caseId): JsonResponse
    {
        return $this->proxy($request, 'DELETE', '/v1/dental/screening/cases/'.$caseId);
    }

    private function validRecord(mixed $data): bool
    {
        try {
            if (! is_array($data)) {
                return false;
            }
            $schema = json_decode(file_get_contents(base_path('../contracts/dental/screening-case.schema.json')));
            $document = json_decode(json_encode($data, JSON_THROW_ON_ERROR));
            if (! (new Validator)->validate($document, $schema)->isValid()) {
                return false;
            }
            $taxonomy = json_decode(file_get_contents(base_path('../contracts/dental/screening-taxonomy.v1.json')), true, flags: JSON_THROW_ON_ERROR);
            $expected = array_column($taxonomy['conditions'], 'id');
            $actual = array_column($data['findings'], 'id');
            sort($expected);
            sort($actual);

            return $actual === $expected && $data['taxonomy_version'] === $taxonomy['version'];
        } catch (Throwable) {
            return false;
        }
    }

    private function proxy(Request $request, string $method, string $path, array $data = [], bool $recordResponse = false): JsonResponse
    {
        try {
            $response = Http::timeout(62)->connectTimeout(3)->withHeaders([
                'X-Service-Key' => config('ai.key'), 'X-Dental-Owner' => DentalOwner::token((int) $request->user()->id),
            ])->acceptJson()->send($method, config('ai.url').$path, $data === [] ? [] : ['json' => $data]);
            if (! $response->successful()) {
                $status = in_array($response->status(), [404, 409, 422], true) ? $response->status() : 503;

                return response()->json(['message' => match ($status) {
                    404 => 'Screening visit not found.',
                    409 => 'Check local-storage consent, patient/visit codes and patient-level partitions. Every image and visit of one patient must remain in one partition.',
                    422 => 'The screening record was rejected. Check the taxonomy, photo fingerprints, review fields and data rights.',
                    default => 'The local screening store is unavailable. Your current draft is unchanged.',
                }], $status);
            }
            if (strlen($response->body()) > 2300000) {
                return response()->json(['message' => 'The screening response exceeded its size limit.'], 502);
            }
            $result = $response->json();
            if ($recordResponse) {
                return $this->validRecord($result) ? response()->json($result) : response()->json(['message' => 'The saved screening record failed validation.'], 502);
            }
            if (! is_array($result) || ($result['classifier_available'] ?? null) !== false || ($result['clinical_validation'] ?? null) !== false
                || ! is_array($result['cases'] ?? null) || count($result['cases']) > 200) {
                return response()->json(['message' => 'The screening-list response was invalid.'], 502);
            }
            $cases = [];
            foreach ($result['cases'] as $row) {
                if (! is_array($row) || ! preg_match('/\A[a-f0-9]{64}\z/', (string) ($row['id'] ?? ''))
                    || ! preg_match('/\A[A-Za-z0-9_-]{1,48}\z/', (string) ($row['subject_code'] ?? ''))
                    || ! preg_match('/\A[A-Za-z0-9_-]{1,48}\z/', (string) ($row['visit_code'] ?? ''))
                    || ! in_array($row['partition'] ?? null, ['train', 'validation', 'test'], true)) {
                    return response()->json(['message' => 'Screening visit metadata was invalid.'], 502);
                }
                $cases[] = array_intersect_key($row, array_flip(['id', 'subject_code', 'visit_code', 'partition']));
            }

            return response()->json(['cases' => $cases, 'classifier_available' => false, 'clinical_validation' => false]);
        } catch (Throwable) {
            return response()->json(['message' => 'The local screening store is unavailable. Your current draft is unchanged.'], 503);
        }
    }
}
