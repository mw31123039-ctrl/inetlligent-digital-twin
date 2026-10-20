<?php

namespace App\Services;

use Illuminate\Support\Facades\Http;
use Opis\JsonSchema\Validator;
use Throwable;

class AiService
{
    public function status(): array
    {
        try {
            $response = Http::timeout(3)->withHeaders(['X-Service-Key' => config('ai.key')])->get(config('ai.url').'/health');
            if ($response->successful()) {
                return ['available' => true, 'provider_configured' => $response->json('provider_configured') === true, 'clinical_review_required' => true];
            }
        } catch (Throwable) {}
        return ['available' => false, 'provider_configured' => false, 'clinical_review_required' => true];
    }

    public function assess(array $state): array
    {
        try {
            $response = Http::timeout(config('ai.timeout'))->connectTimeout(3)
                ->withHeaders(['X-Service-Key' => config('ai.key')])->acceptJson()
                ->post(config('ai.url').'/v1/assess', [
                    'region' => $state['region'], 'side' => $state['side'], 'messages' => $state['messages'],
                    'prior_urgency' => $state['assessment']['urgency'] ?? null,
                ]);
            if (!$response->successful() || strlen($response->body()) > 200000) {
                abort(503, 'The assessment service is unavailable. No assessment was generated. For severe or sudden symptoms, seek urgent medical help.');
            }
            $data = $response->json();
            $schema = json_decode(file_get_contents(base_path('../contracts/assessment.schema.json')));
            $validation = (new Validator)->validate(json_decode($response->body()), $schema);
            if (!$validation->isValid() || ($data['selected_region'] ?? null) !== $state['region'] || ($data['side'] ?? null) !== $state['side']) {
                abort(502, 'The AI service returned an invalid assessment. No result was accepted.');
            }
            foreach ($data['supporting_sources'] as $source) {
                $parts = parse_url($source['url']);
                if (($parts['scheme'] ?? '') !== 'https' || ($parts['host'] ?? '') !== 'www.nhs.uk') {
                    abort(502, 'The AI service returned an unapproved reference. No result was accepted.');
                }
            }
            return $data;
        } catch (\Symfony\Component\HttpKernel\Exception\HttpException $exception) {
            throw $exception;
        } catch (Throwable) {
            // Do not expose or log SDK errors, upstream response bodies, or symptoms.
            abort(503, 'The assessment service is unavailable. No assessment was generated. For severe or sudden symptoms, seek urgent medical help.');
        }
    }
}
