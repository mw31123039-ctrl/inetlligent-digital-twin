<?php

namespace App\Services;

use Opis\JsonSchema\Validator;

/**
 * Checks a research result from the local AI service before any client sees or stores it.
 *
 * The JSON Schema covers types and bounds; this class re-checks the cross-field rules that
 * a schema cannot express (outcome consistency, score normalisation, heatmap binding).
 */
class CancerResultContract
{
    public const SCHEMA_VERSION = 'humantwin-cancer-result-v2';

    /**
     * @param  array{track: string, modality: string}  $request
     */
    public function violation(string $body, array $request, string $rawImage): ?string
    {
        $schema = json_decode(file_get_contents(base_path('../contracts/cancer-result.schema.json')));
        $decoded = json_decode($body);
        if (is_object($decoded) && isset($decoded->schema_version) && is_string($decoded->schema_version)
            && str_starts_with($decoded->schema_version, 'humantwin-cancer-result-') && $decoded->schema_version !== self::SCHEMA_VERSION) {
            return 'The local AI service is running an older version. Restart it (scripts/start-ai-service.ps1) and analyse again. No result was accepted.';
        }
        if (! is_object($decoded) || ! (new Validator)->validate($decoded, $schema)->isValid()) {
            return 'The model response failed validation. No result was accepted.';
        }
        $result = json_decode($body, true);
        if ($result['track'] !== $request['track'] || $result['modality'] !== $request['modality']
            || $result['input_sha256'] !== hash('sha256', $rawImage)) {
            return 'The result did not match this image or classifier contract. No result was accepted.';
        }

        return $this->outcomeViolation($result);
    }

    /**
     * @param  array<string, mixed>  $result
     */
    public function outcomeViolation(array $result): ?string
    {
        $mismatch = 'The result did not match this image or classifier contract. No result was accepted.';
        $scores = $result['scores'];
        $labels = array_column($scores, 'label');
        $reasons = $result['outcome_reasons'];
        if (count(array_unique($reasons)) !== count($reasons)) {
            return $mismatch;
        }
        if ($result['outcome'] === 'input-rejected') {
            $empty = $scores === [] && ($result['confidence'] ?? null) === null && ($result['heatmap'] ?? null) === null
                && ($result['familiarity'] ?? null) === null && ($result['finding_label'] ?? null) === null;

            return $empty && $reasons === ['input-rejected'] && $result['image_checks']['decision'] === 'rejected' ? null : $mismatch;
        }
        if (count($labels) < 2 || count(array_unique($labels)) !== count($labels)
            || abs(array_sum(array_column($scores, 'value')) - 1) > .001 || ! is_array($result['confidence'] ?? null)
            || $result['image_checks']['decision'] === 'rejected' || in_array('input-rejected', $reasons, true)) {
            return $mismatch;
        }
        $top = array_reduce($scores, fn (?array $best, array $score) => $best === null || $score['value'] > $best['value'] ? $score : $best);
        if ($result['confidence']['top_label'] !== $top['label'] || abs($result['confidence']['probability'] - $top['value']) > 1e-6) {
            return $mismatch;
        }
        $finding = $result['finding_label'] ?? null;
        if (($result['outcome'] === 'finding' && ($reasons !== [] || $finding !== $top['label']))
            || ($result['outcome'] === 'inconclusive' && ($reasons === [] || $finding !== null))) {
            return $mismatch;
        }
        $heatmap = $result['heatmap'] ?? null;
        if (is_array($heatmap) && (count($heatmap['values']) !== $heatmap['grid_width'] * $heatmap['grid_height']
            || ! in_array($heatmap['target_label'], $labels, true))) {
            return 'The explanation did not match this classifier output. No result was accepted.';
        }

        return null;
    }
}
