<?php

namespace App\Services;

use Illuminate\Validation\ValidationException;

/** Independent deterministic educational evaluator. Never calls a model or external service. */
class EyeAssessmentService
{
    private array $content;
    private array $care;
    private PainAssistance $painHelper;

    public function __construct()
    {
        $this->content = json_decode(file_get_contents(base_path('../contracts/eye/interview.v1.json')), true, flags: JSON_THROW_ON_ERROR);
        $this->care = json_decode(file_get_contents(base_path('../contracts/eye/care.v1.json')), true, flags: JSON_THROW_ON_ERROR);
        $this->painHelper = new PainAssistance;
    }

    public function replay(array $input): array
    {
        $state = [
            'id' => $input['id'], 'locale' => $input['locale'], 'use' => 'education',
            'anatomy_explored' => $input['anatomy_explored'], 'model_side' => $input['model_side'],
            'reported' => ['laterality' => 'unknown', 'location' => 'unknown', 'pain_entry_mode' => 'assistant'],
            'symptoms' => array_fill_keys(array_column($this->content['symptoms'], 'id'), 'unknown'),
            'turns' => [], 'messages' => [], 'acknowledgements' => [], 'urgency' => 'unknown',
            'rule_ids' => [], 'red_flags' => [], 'missing' => [], 'unconfirmed_explanations' => [],
            'source_urls' => [], 'rule_version' => $this->content['version'], 'source_version' => $this->content['version'],
            'clinical_review_status' => 'draft', 'created_at' => now()->toIso8601String(),
        ];
        foreach ($input['turns'] as $turn) {
            if (str_starts_with($turn['question_id'], 'pain-estimate:')) {
                $this->painHelper->applyAction($state, $turn);
                $this->evaluate($state);
                continue;
            }
            if ($state['urgency'] === 'emergency' || ($state['urgency'] === 'urgent' && $turn['question_id'] !== 'question.concern')) {
                $this->invalid('Routine questioning must stop after an urgency warning.');
            }
            if (str_starts_with($turn['question_id'], 'learn:')) {
                $knowledge = json_decode(file_get_contents(base_path('../contracts/eye/knowledge.v1.json')), true, flags: JSON_THROW_ON_ERROR);
                $topic = collect($knowledge['topics'])->firstWhere('id', substr($turn['question_id'], 6));
                if (!$topic || $state['urgency'] !== 'unknown') $this->invalid('Unavailable educational topic.');
                $state['turns'][] = $turn;
                $state['messages'][] = ['role' => 'user', 'text' => $turn['value']];
                $state['messages'][] = ['role' => 'assistant', 'text' => $topic['answer'][$state['locale']], 'kind' => 'education', 'source_urls' => $topic['source_urls'], 'topic_id' => $topic['id']];
                continue;
            }
            $question = collect($this->content['questions'])->firstWhere('id', $turn['question_id']);
            if (!$question) {
                $this->invalid('Unknown eye question.');
            }
            $option = collect($question['options'])->firstWhere('value', $turn['value']);
            $numeric = in_array($question['type'], ['pain', 'age', 'days'], true);
            if ($question['options'] && !$option && empty($turn['text'])) {
                $this->invalid('Choose an available answer or provide the original free text.');
            }
            if ($numeric && $turn['value'] !== 'unknown' && empty($turn['text'])) {
                if (!is_numeric($turn['value']) || (float) $turn['value'] !== (float) (int) $turn['value'] || (int) $turn['value'] < 0 || (int) $turn['value'] > ($question['type'] === 'pain' ? 10 : ($question['type'] === 'days' ? 365 : 120))) {
                    $this->invalid('Invalid pain score or age.');
                }
            }
            $field = $question['field'];
            $state['turns'][] = $turn;
            $state['reported'][$field] = $option || ($numeric && $turn['value'] !== 'unknown' && empty($turn['text']))
                ? ($numeric && $turn['value'] !== 'unknown' ? (int) $turn['value'] : $turn['value'])
                : ($question['type'] === 'text' ? $turn['value'] : 'unknown');
            if ($field === 'pain' && is_int($state['reported']['pain'])) {
                $state['symptoms']['symptom.pain'] = $state['reported']['pain'] > 0 ? 'present' : 'absent';
                $state['reported']['pain_source'] = 'self-reported';
                $state['reported']['pain_entry_mode'] = 'manual';
            }
            if ($field === 'pain_descriptor' && in_array($state['reported']['pain_descriptor'], ['mild', 'moderate', 'severe', 'none'], true)) $state['symptoms']['symptom.pain'] = $state['reported']['pain_descriptor'] === 'none' ? 'absent' : 'present';
            if ($field === 'vision') {
                foreach (['loss' => 'vision-loss', 'blurred' => 'blurred-vision', 'double' => 'double-vision'] as $value => $symptom) {
                    if ($state['reported']['vision'] === $value) {
                        $state['symptoms']['symptom.'.$symptom] = 'present';
                    } elseif ($state['reported']['vision'] === 'unchanged') {
                        $state['symptoms']['symptom.'.$symptom] = 'absent';
                    }
                }
            }
            $state['messages'][] = ['role' => 'assistant', 'text' => $question['text'][$state['locale']]];
            $state['messages'][] = ['role' => 'user', 'text' => $option ? $option['label'][$state['locale']] : ($turn['text'] ?? $turn['value'])];
            if (!$option && !$numeric) {
                $this->parse($state, $turn['text'] ?? $turn['value']);
            }
            $this->evaluate($state);
        }
        $this->evaluate($state);
        $state['pain_assessment'] = $this->painAssessment($state);
        $state['pain_estimate'] = $this->painHelper->estimate($state['reported']);
        $state['care_plan'] = $this->carePlan($state);
        $state['doctor_summary'] = $this->doctorSummary($state);

        return $state;
    }

    private function invalid(string $message): never
    {
        throw ValidationException::withMessages(['turns' => $message]);
    }

    private function carePlan(array $state): array
    {
        $level = $state['urgency'];
        $reported = $state['reported'];
        $child = ($reported['child'] ?? '') === 'yes' || ($reported['newborn'] ?? '') === 'yes' || (isset($reported['age']) && is_int($reported['age']) && $reported['age'] < 16);
        $childRule = in_array('eye.rule.newborn-red-sticky', $state['rule_ids'], true) || ($child && in_array('eye.rule.white-pupil', $state['rule_ids'], true));
        $route = $level === 'emergency' ? 'emergency' : ($level === 'urgent' ? ($childRule ? 'paediatric' : 'urgent') : 'assessment');
        $steps = [];
        if (in_array('eye.rule.chemical', $state['rule_ids'], true)) {
            $rule = collect($this->content['rules'])->firstWhere('id', 'eye.rule.chemical');
            $steps[] = ['id' => 'chemical-rinse', 'text' => $rule['first_aid']];
        }
        if ($level === 'emergency') {
            $steps[] = $this->care['steps']['travel'];
            $steps[] = $this->care['steps']['protect'];
        }
        if (in_array($reported['exposure'] ?? '', ['penetrating', 'high-speed'], true)) $steps[] = $this->care['steps']['embedded'];
        if (($reported['contact_lenses'] ?? '') === 'yes' && ($reported['exposure'] ?? '') !== 'penetrating') $steps[] = $this->care['steps']['lenses'];
        $surface = false;
        foreach (['dryness', 'grittiness', 'burning'] as $id) $surface = $surface || ($state['symptoms']['symptom.'.$id] ?? '') === 'present';
        $comfort = $level === 'unknown' && ($reported['vision'] ?? '') === 'unchanged' && ($reported['exposure'] ?? '') === 'none'
            && ($reported['contact_lenses'] ?? '') === 'no' && ($reported['recent_procedure'] ?? '') === 'no' && ($reported['onset'] ?? '') === 'gradual'
            && isset($reported['pain']) && is_int($reported['pain']) && $reported['pain'] <= 3 && $surface;
        if ($comfort) {
            $steps[] = $this->care['steps']['screen'];
            $steps[] = $this->care['steps']['environment'];
        }
        if ($level !== 'unknown') $steps[] = $this->care['steps']['prepare'];
        $steps[] = $this->care['steps']['medicine'];
        if ($level === 'unknown') $steps[] = $this->care['steps']['worsening'];
        $sources = [$this->care['sources']['pain'], ...$state['source_urls']];
        if ($comfort) $sources[] = $this->care['sources']['dry'];
        if ($level === 'emergency') $sources[] = $this->care['sources']['injury'];
        if (($reported['contact_lenses'] ?? '') === 'yes') $sources[] = $this->care['sources']['red'];

        return ['version' => $this->care['version'], 'clinical_review_status' => 'draft', 'level' => $level, 'route' => $route,
            'doctor' => $this->care['routes'][$route], 'steps' => $steps, 'comfort_measures_included' => $comfort, 'source_urls' => array_values(array_unique($sources))];
    }

    private function doctorSummary(array $state): string
    {
        $locale = $state['locale'];
        $lines = ['HumanTwin — synthetic educational eye summary / NOT A DIAGNOSIS', 'Created: '.$state['created_at'],
            'Draft warning result: '.$state['urgency'], 'Care service: '.$state['care_plan']['doctor']['title'][$locale],
            'Pain score: '.($state['pain_assessment']['score'] ?? 'unknown').'/10; band: '.$state['pain_assessment']['band']];
        $lines[] = 'Pain-score origin: '.$state['pain_assessment']['numeric_source'].'; assistant suggestion ('.($state['pain_estimate']['confirmed'] ? 'patient-confirmed' : 'unconfirmed').'): '.($state['pain_estimate']['suggested_score'] ?? 'none').'/10 (not an objective measurement).';
        foreach ($state['reported'] as $field => $value) $lines[] = str_replace('_', ' ', $field).': '.$value;
        $lines[] = 'Reported symptoms:';
        foreach ($this->content['symptoms'] as $symptom) if (($state['symptoms'][$symptom['id']] ?? '') === 'present') $lines[] = $symptom['label'][$locale];
        $lines[] = 'Reason for urgency:';
        foreach ($this->content['rules'] as $rule) if (in_array($rule['id'], $state['rule_ids'], true)) $lines[] = $rule['id'].': '.$rule['reason'][$locale];
        $lines[] = 'Information still unknown: '.implode(', ', $state['missing']);
        $lines[] = 'No examination, eye-pressure measurement, imaging or clinical diagnosis has been performed in this chat.';
        $lines[] = 'Original answers (kept in the language entered):';
        foreach ($state['turns'] as $turn) if (!str_starts_with($turn['question_id'], 'learn:')) $lines[] = $turn['question_id'].': '.($turn['text'] ?? $turn['value']);
        $lines[] = 'Questions for the examining clinician:';
        foreach ($this->care['doctor_questions'] as $question) $lines[] = $question[$locale];
        $lines[] = 'Rules: '.$state['rule_version'].'; care: '.$this->care['version'].'; clinical review: pending';
        $lines[] = 'Sources:';

        return implode("\n", [...$lines, ...$state['care_plan']['source_urls']]);
    }

    private function painAssessment(array $state): array
    {
        $scale = json_decode(file_get_contents(base_path('../contracts/eye/pain-scale.v1.json')), true, flags: JSON_THROW_ON_ERROR);
        $score = isset($state['reported']['pain']) && is_int($state['reported']['pain']) ? $state['reported']['pain'] : null;
        $band = null;
        foreach ($scale['bands'] as $item) {
            if (($score !== null && $score >= $item['min'] && $score <= $item['max']) || ($score === null && ($state['reported']['pain_descriptor'] ?? '') === $item['id'])) $band = $item;
        }

        return ['score' => $score, 'band' => $band['id'] ?? 'unknown', 'label' => $band['label'][$state['locale']] ?? 'Not rated',
            'numeric_source' => $score === null ? 'not-reported' : (($state['reported']['pain_source'] ?? '') === 'assisted-confirmed' ? 'assisted-confirmed' : 'patient-reported'), 'functional_impact' => $state['reported']['pain_function'] ?? 'unknown',
            'content_version' => $scale['version'], 'source_urls' => $scale['source_urls']];
    }

    private function negated(string $prefix): bool
    {
        return (bool) preg_match('~'.$this->content['negation_pattern'].'~iu', $prefix)
            || (bool) preg_match('~(?:not|never|no|without|denies|لا|بدون)\s*$~iu', $prefix);
    }

    private function parse(array &$state, string $text): void
    {
        foreach (preg_split('~[;.!?\n]|\bbut\b~iu', $text) as $clause) {
            foreach ($this->content['lexical'] as $item) {
                preg_match_all('~'.$item['pattern'].'~iu', $clause, $matches, PREG_OFFSET_CAPTURE);
                foreach ($matches[0] as [$match, $offset]) {
                    if (!$this->negated(substr($clause, 0, $offset))) {
                        $state['reported'][$item['field']] = $item['value'];
                    }
                }
            }
            foreach ($this->content['symptom_patterns'] as $id => $pattern) {
                preg_match_all('~'.$pattern.'~iu', $clause, $matches, PREG_OFFSET_CAPTURE);
                foreach ($matches[0] as [$match, $offset]) {
                    $state['symptoms']['symptom.'.$id] = $this->negated(substr($clause, 0, $offset)) ? 'absent' : 'present';
                }
            }
        }
        if (preg_match('~\b(?:no pain|painless|without pain)\b|بدون ألم|بێ ئازار~iu', $text)) {
            $state['reported']['pain'] = 0;
            $state['reported']['pain_source'] = 'self-reported';
            $state['reported']['pain_entry_mode'] = 'manual';
            $state['symptoms']['symptom.pain'] = 'absent';
        }
        if (preg_match('~(?:severe|terrible|excruciating) (?:eye )?pain|ألم شديد|ئازاری توند~iu', $text) && !preg_match('~(?:no|not) severe~iu', $text)) {
            $state['reported']['pain_descriptor'] = 'severe';
            $state['symptoms']['symptom.pain'] = 'present';
        } elseif (preg_match('~\bmild (?:eye )?pain\b|ألم خفيف|ئازاری سووک~iu', $text)) {
            $state['reported']['pain_descriptor'] = 'mild';
            $state['symptoms']['symptom.pain'] = 'present';
        } elseif (preg_match('~\bmoderate (?:eye )?pain\b|ألم متوسط|ئازاری مامناوەند~iu', $text)) {
            $state['reported']['pain_descriptor'] = 'moderate';
            $state['symptoms']['symptom.pain'] = 'present';
        }
        if (preg_match('~\b(10|[0-9])\s*(?:/\s*10|out of 10)\b~i', $text, $matches)) {
            $state['reported']['pain'] = (int) $matches[1];
            $state['reported']['pain_source'] = 'self-reported';
            $state['reported']['pain_entry_mode'] = 'manual';
            $state['symptoms']['symptom.pain'] = (int) $matches[1] > 0 ? 'present' : 'absent';
        }
        foreach ($this->painHelper->activityPatterns() as $pattern) {
            if (preg_match('~'.$pattern['pattern'].'~iu', $text, $activityMatch, PREG_OFFSET_CAPTURE) && !$this->negated(substr($text, 0, $activityMatch[0][1]))) {
                $state['reported']['pain_function'] = $pattern['value'];
                break;
            }
        }
        if (preg_match('~\b(?:newborn|neonate)\b|مولود جديد|تازەلەدایکبوو~iu', $text)) {
            $state['reported']['age'] = 0;
            $state['reported']['newborn'] = 'yes';
        } elseif (preg_match('~\b(?:my child|my baby|my son|my daughter|toddler)\b|طفلي|طفلتي|منداڵەکەم~iu', $text)) {
            $state['reported']['child'] = 'yes';
        }
        if (preg_match('~\b(\d{1,3})\s*(?:years? old|year.old|y/o)\b~i', $text, $matches) && (int) $matches[1] <= 120) {
            $state['reported']['age'] = (int) $matches[1];
        }
        preg_match_all('~\b(both eyes|left eye|right eye|bilateral)\b|العينين|العين اليسرى|العين اليمنى|هەردوو چاو|چاوی چەپ|چاوی ڕاست~iu', $text, $matches, PREG_OFFSET_CAPTURE);
        $sides = [];
        foreach ($matches[0] as [$match, $offset]) {
            if ($this->negated(substr($text, 0, $offset))) {
                continue;
            }
            $sides[] = preg_match('~both|bilateral|العينين|هەردوو~iu', $match) ? 'both' : (preg_match('~left|اليسرى|چەپ~iu', $match) ? 'left' : 'right');
        }
        $sides = array_values(array_unique($sides));
        if (count($sides) === 1 && $state['reported']['laterality'] !== $sides[0]) {
            $state['reported']['laterality'] = $sides[0];
            $state['acknowledgements'][] = 'Reported laterality updated to '.$sides[0].'. Anatomy selection remains separate.';
        } elseif (count($sides) > 1) {
            $state['reported']['laterality'] = 'unknown';
            $state['acknowledgements'][] = 'Ambiguous laterality: clarify left, right, both or not sure.';
        }
    }

    private function combine(array $values, bool $all): string
    {
        if ($all) {
            return in_array('absent', $values, true) ? 'absent' : (count(array_filter($values, fn ($v) => $v === 'present')) === count($values) ? 'present' : 'unknown');
        }

        return in_array('present', $values, true) ? 'present' : (count(array_filter($values, fn ($v) => $v === 'absent')) === count($values) ? 'absent' : 'unknown');
    }

    private function fact(array $state, string $key, mixed $value): string
    {
        if ($key === 'symptom') {
            return $state['symptoms']['symptom.'.$value] ?? 'unknown';
        }
        if ($key === 'symptoms') {
            return $this->combine(array_map(fn ($id) => $this->fact($state, 'symptom', $id), $value), false);
        }
        if ($key === 'visual') {
            $visual = in_array($state['reported']['vision'] ?? '', ['loss', 'blurred', 'double'], true);
            foreach (['vision-loss', 'blurred-vision', 'double-vision', 'curtain', 'blind-spots', 'distorted-lines', 'colour-change'] as $id) {
                $visual = $visual || ($state['symptoms']['symptom.'.$id] ?? '') === 'present';
            }

            return $visual ? 'present' : (($state['reported']['vision'] ?? '') === 'unchanged' ? 'absent' : 'unknown');
        }
        if ($key === 'pain_gte') {
            if (($state['reported']['pain_descriptor'] ?? '') === 'severe' && $value <= 7) return 'present';
            return isset($state['reported']['pain']) && is_int($state['reported']['pain']) ? ($state['reported']['pain'] >= $value ? 'present' : 'absent') : 'unknown';
        }
        if ($key === 'newborn') {
            if (($state['reported']['newborn'] ?? '') === 'yes') return 'present';
            if (isset($state['reported']['age_days']) && is_int($state['reported']['age_days'])) return $state['reported']['age_days'] < 28 ? 'present' : 'absent';
            return isset($state['reported']['age']) && is_int($state['reported']['age']) && $state['reported']['age'] > 0 ? 'absent' : 'unknown';
        }
        $actual = $state['reported'][$key] ?? 'unknown';
        if ($actual === 'unknown' || $actual === '') {
            return 'unknown';
        }

        return (is_array($value) ? in_array($actual, $value, true) : $actual === $value) ? 'present' : 'absent';
    }

    private function clause(array $state, ?array $clause, bool $all): string
    {
        if (!$clause) {
            return 'present';
        }
        $values = [];
        foreach ($clause as $key => $value) {
            $values[] = $this->fact($state, $key, $value);
        }

        return $this->combine($values, $all);
    }

    private function evaluate(array &$state): void
    {
        $ids = $state['rule_ids'];
        $matches = [];
        foreach ($this->content['rules'] as $rule) {
            $result = $this->combine([$this->clause($state, $rule['all'], true), $this->clause($state, $rule['any'], false)], true);
            $state['red_flags'][$rule['id']] = in_array($rule['id'], $ids, true) ? 'present' : $result;
            if ($result === 'present' || in_array($rule['id'], $ids, true)) {
                $ids[] = $rule['id'];
                $matches[] = $rule;
            }
        }
        $state['rule_ids'] = array_values(array_unique($ids));
        $state['urgency'] = in_array('emergency', array_column($matches, 'level'), true) ? 'emergency' : ($matches ? 'urgent' : 'unknown');
        $state['source_urls'] = array_values(array_unique(array_merge([], ...array_column($matches, 'source_urls'))));
        $state['missing'] = array_values(array_map(fn ($q) => $q['field'], array_filter($this->content['questions'], fn ($q) => ($state['reported'][$q['field']] ?? 'unknown') === 'unknown')));
    }
}
