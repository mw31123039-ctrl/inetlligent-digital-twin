<?php

namespace App\Services;

use Illuminate\Http\Client\PendingRequest;
use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\Http;
use Opis\JsonSchema\Validator;
use Symfony\Component\HttpKernel\Exception\HttpException;
use Throwable;

/**
 * Client for the private clinical v2 engine. Every assessment is checked against the shared JSON Schema
 * and an allowlist of source hosts before it can reach a browser or the database.
 */
class ClinicalAiService
{
    public const UNAVAILABLE = 'The assessment service is unavailable. No assessment was generated. For severe or sudden symptoms, seek urgent medical help.';

    private function client(?float $timeout = null): PendingRequest
    {
        return Http::timeout($timeout ?? config('ai.timeout'))->connectTimeout(3)
            ->withHeaders(['X-Service-Key' => config('ai.key')])->acceptJson();
    }

    /**
     * @return array{available: bool, language_model_configured: bool}
     */
    public function status(): array
    {
        try {
            $response = $this->client(3)->get(config('ai.url').'/health');
            if ($response->successful() && $response->json('clinical_v2') === true) {
                return ['available' => true, 'language_model_configured' => $response->json('clinical_language_model_configured') === true];
            }
        } catch (Throwable) {
        }

        return ['available' => false, 'language_model_configured' => false];
    }

    /**
     * @return array<string, mixed>
     */
    public function catalog(): array
    {
        return Cache::remember('clinical-v2-catalog', 600, function () {
            try {
                $response = $this->client(8)->get(config('ai.url').'/v2/clinical/catalog');
            } catch (Throwable) {
                abort(503, 'The clinical catalogue is unavailable.');
            }
            abort_unless($response->successful(), 503, 'The clinical catalogue is unavailable.');

            return $response->json();
        });
    }

    /**
     * @return array<string, mixed>
     */
    public function coverage(): array
    {
        try {
            $response = $this->client(8)->get(config('ai.url').'/v2/clinical/coverage');
        } catch (Throwable) {
            abort(503, 'Coverage information is unavailable.');
        }
        abort_unless($response->successful(), 503, 'Coverage information is unavailable.');

        return $response->json();
    }

    /**
     * @param  array<string, mixed>  $payload
     * @return array<string, mixed>
     */
    public function assess(array $payload): array
    {
        try {
            $response = $this->client()->post(config('ai.url').'/v2/clinical/assess', $payload);
        } catch (Throwable) {
            abort(503, self::UNAVAILABLE);
        }
        abort_if($response->status() === 422, 422, 'The assessment request was rejected. Check the selected anatomy.');
        abort_if(! $response->successful() || strlen($response->body()) > 400000, 503, self::UNAVAILABLE);

        return $this->validated($response->body(), $payload);
    }

    /**
     * Stream progress stages from the engine. Only the final, validated assessment is returned; stages carry
     * no health content.
     *
     * @param  array<string, mixed>  $payload
     * @param  callable(string): void  $onStage
     * @return array<string, mixed>
     */
    public function streamAssess(array $payload, callable $onStage): array
    {
        try {
            $response = $this->client()->withOptions(['stream' => true])->accept('application/x-ndjson')
                ->post(config('ai.url').'/v2/clinical/assess/stream', $payload);
        } catch (Throwable) {
            abort(503, self::UNAVAILABLE);
        }
        abort_unless($response->successful(), 503, self::UNAVAILABLE);
        $body = $response->toPsrResponse()->getBody();
        $buffer = '';
        $size = 0;
        try {
            while (! $body->eof()) {
                $chunk = $body->read(8192);
                $size += strlen($chunk);
                abort_if($size > 500000, 503, self::UNAVAILABLE);
                $buffer .= $chunk;
                while (($position = strpos($buffer, "\n")) !== false) {
                    $line = substr($buffer, 0, $position);
                    $buffer = substr($buffer, $position + 1);
                    $result = $this->handleLine($line, $payload, $onStage);
                    if ($result !== null) {
                        return $result;
                    }
                }
            }
            $result = $this->handleLine($buffer, $payload, $onStage);
        } catch (HttpException $exception) {
            throw $exception;
        } catch (Throwable) {
            abort(503, self::UNAVAILABLE);
        }
        abort_if($result === null, 503, self::UNAVAILABLE);

        return $result;
    }

    /**
     * @param  array<string, mixed>  $payload
     * @param  callable(string): void  $onStage
     * @return array<string, mixed>|null
     */
    private function handleLine(string $line, array $payload, callable $onStage): ?array
    {
        if (trim($line) === '') {
            return null;
        }
        $event = json_decode($line, true);
        abort_unless(is_array($event) && isset($event['type']), 503, self::UNAVAILABLE);
        if ($event['type'] === 'stage' && is_string($event['stage'] ?? null) && preg_match('/\A[a-z_]{3,20}\z/', $event['stage'])) {
            $onStage($event['stage']);

            return null;
        }
        if ($event['type'] === 'result' && is_array($event['assessment'] ?? null)) {
            return $this->validated(json_encode($event['assessment'], JSON_THROW_ON_ERROR), $payload);
        }
        abort_if($event['type'] === 'error' && ($event['status'] ?? 0) === 422, 422, 'The assessment request was rejected. Check the selected anatomy.');
        abort(503, self::UNAVAILABLE);
    }

    /**
     * @param  array<string, mixed>  $payload
     * @return array<string, mixed>
     */
    private function validated(string $body, array $payload): array
    {
        $schema = json_decode(file_get_contents(base_path('../contracts/clinical/assessment.v2.schema.json')));
        $decoded = json_decode($body);
        if (! is_object($decoded) || ! (new Validator)->setMaxErrors(1)->validate($decoded, $schema)->isValid()) {
            abort(502, 'The assessment failed validation. No result was accepted.');
        }
        $data = json_decode($body, true);
        abort_unless(($data['locale'] ?? null) === $payload['locale'], 502, 'The assessment failed validation. No result was accepted.');
        abort_unless(in_array($data['anatomy']['id'] ?? null, $this->anatomyIds(), true), 502, 'The assessment failed validation. No result was accepted.');
        $hosts = $this->allowedHosts();
        foreach ($data['citations'] as $citation) {
            $parts = parse_url($citation['url']);
            abort_unless(($parts['scheme'] ?? '') === 'https' && in_array($parts['host'] ?? '', $hosts, true), 502, 'The assessment cited an unapproved source. No result was accepted.');
        }

        return $data;
    }

    /**
     * @return array<string, mixed>
     */
    public function extractDocument(string $filename, string $mediaType, string $bytes): array
    {
        try {
            $response = $this->client(30)->post(config('ai.url').'/v2/clinical/documents/extract', [
                'filename' => mb_substr(preg_replace('/[^\w.\- ]+/u', '_', $filename) ?: 'report', 0, 200),
                'media_type' => $mediaType,
                'content_base64' => base64_encode($bytes),
            ]);
        } catch (Throwable) {
            abort(503, 'Report extraction is unavailable.');
        }
        abort_unless($response->successful(), $response->status() === 413 ? 413 : 503, 'Report extraction is unavailable.');
        $schema = json_decode(file_get_contents(base_path('../contracts/clinical/report-extraction.v1.schema.json')));
        abort_unless((new Validator)->validate(json_decode($response->body()), $schema)->isValid(), 502, 'The extraction failed validation.');

        return $response->json();
    }

    /**
     * @return array<int, string>
     */
    public function anatomyIds(): array
    {
        return Cache::rememberForever('clinical-anatomy-ids:'.filemtime(base_path('../contracts/clinical/anatomy.v1.json')), function () {
            $contract = json_decode(file_get_contents(base_path('../contracts/clinical/anatomy.v1.json')), true);

            return array_column($contract['nodes'], 'id');
        });
    }

    /**
     * @return array<int, string>
     */
    private function allowedHosts(): array
    {
        $registry = json_decode(file_get_contents(base_path('../contracts/clinical/sources.v1.json')), true);

        return $registry['policy']['allowed_hosts'];
    }
}
