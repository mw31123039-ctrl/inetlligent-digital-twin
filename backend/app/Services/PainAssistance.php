<?php

namespace App\Services;

use Illuminate\Validation\ValidationException;

/** Original draft suggestion heuristic. A proposal never becomes a reported score without confirmation. */
class PainAssistance
{
    private array $content;

    public function __construct()
    {
        $this->content = json_decode(file_get_contents(base_path('../contracts/eye/pain-assistance.v1.json')), true, flags: JSON_THROW_ON_ERROR);
    }

    public function activityPatterns(): array
    {
        return $this->content['activity_patterns'];
    }

    public function estimate(array $reported): array
    {
        $description = (string) ($reported['pain_descriptor'] ?? 'unknown');
        $impact = (string) ($reported['pain_function'] ?? 'unknown');
        $supported = array_key_exists($description, $this->content['proposals']);
        $score = $supported ? ($this->content['proposals'][$description][$impact] ?? null) : null;
        $status = !$supported ? 'insufficient' : ($score === null ? ($impact === 'unknown' ? 'insufficient' : 'needs_clarification') : 'suggested');
        $active = in_array($reported['pain_entry_mode'] ?? '', ['assistant', 'confirmed'], true) || ($reported['pain_source'] ?? '') === 'assisted-confirmed';

        return ['version' => $this->content['version'], 'clinical_review_status' => 'draft', 'status' => $active ? $status : 'not_requested',
            'suggested_score' => $active ? $score : null, 'range' => $active && $supported ? $this->content['ranges'][$description] : null,
            'band' => $active && $supported ? $description : 'unknown', 'based_on' => ['description' => $description, 'activity_impact' => $impact],
            'numeric_source' => 'assistant-estimate', 'confirmed' => ($reported['pain_source'] ?? '') === 'assisted-confirmed',
            'source_urls' => $this->content['source_urls']];
    }

    public function applyAction(array &$state, array $turn): void
    {
        $action = substr($turn['question_id'], strlen('pain-estimate:'));
        if ($state['urgency'] === 'emergency' || !in_array($action, ['start', 'accept', 'manual', 'skip'], true)) {
            throw ValidationException::withMessages(['turns' => 'Emergency guidance takes priority, or this pain helper action is unavailable.']);
        }
        if ($action === 'accept') {
            $proposal = $this->estimate($state['reported']);
            if ($proposal['status'] !== 'suggested' || $proposal['suggested_score'] === null || $turn['value'] !== (string) $proposal['suggested_score']) {
                throw ValidationException::withMessages(['turns' => 'Confirm the current server-computed pain suggestion.']);
            }
            $state['reported']['pain'] = $proposal['suggested_score'];
            $state['reported']['pain_source'] = 'assisted-confirmed';
            $state['reported']['pain_entry_mode'] = 'confirmed';
            $state['symptoms']['symptom.pain'] = $proposal['suggested_score'] > 0 ? 'present' : 'absent';
            $state['messages'][] = ['role' => 'user', 'text' => 'Confirmed the assistant-suggested pain score.'];
            $state['messages'][] = ['role' => 'assistant', 'text' => 'Patient confirmed the suggested '.$proposal['suggested_score'].'/10 score. It is not an objective measurement.'];
        } else {
            $state['reported']['pain_entry_mode'] = $action === 'start' ? 'assistant' : ($action === 'skip' ? 'skipped' : 'manual');
        }
        $state['turns'][] = $turn;
    }
}
