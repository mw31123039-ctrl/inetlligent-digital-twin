import json
import re
from pathlib import Path
from .schemas import Escalation

RULESET = json.loads((Path(__file__).parent / 'rules' / 'triage.v1.json').read_text(encoding='utf-8'))
LEVELS = {'not_established': 0, 'routine': 1, 'soon': 2, 'same_day': 3, 'emergency': 4}

def positive_matches(pattern, text):
    # Conservative, transparent English matching. This is deliberately not an
    # assertion of medical/NLP completeness; see CLINICAL_REVIEW.md.
    for clause in re.split(r'[.!?;\n]|\bbut\b|\bhowever\b|\bnow\b|\btoday\b', text.lower()):
        for match in re.finditer(pattern, clause):
            prefix = clause[max(0, match.start() - 45):match.start()]
            if re.search(r"\b(no|not|without|denies|deny|never|don't have|do not have)\b[^,]{0,35}$", prefix):
                continue
            if re.search(r'\b(years? ago|last year|used to|in the past)\b', clause):
                continue
            yield match.group(0)

def screen(messages, previous=None):
    reasons, ids = [], []
    level = 'not_established'
    for rule in RULESET['rules']:
        if 'all_patterns' in rule:
            users = [message for message in messages if message.role == 'user']
            if all(any(list(positive_matches(pattern, message.text)) for message in users) for pattern in rule['all_patterns']):
                reasons.append(rule['reason'])
                ids.append(rule['id'])
                if LEVELS[rule['urgency']] > LEVELS[level]: level = rule['urgency']
            continue
        for message in messages:
            if message.role != 'user':
                continue
            if list(positive_matches(rule['pattern'], message.text)):
                reasons.append(rule['reason'])
                ids.append(rule['id'])
                if LEVELS[rule['urgency']] > LEVELS[level]:
                    level = rule['urgency']
                break
    # An unspecific positive answer to an urgent-warning question needs human
    # assessment; never continue an ordinary questionnaire to obtain details.
    for i, message in enumerate(messages):
        if message.role == 'user' and i and messages[i - 1].field == 'warning_signs':
            if re.match(r'^yes\b', message.text.strip(), re.I):
                reasons.append('You reported a possible warning sign; its nature is not established.')
                ids.append('positive-warning-screen')
                if LEVELS[level] < LEVELS['same_day']:
                    level = 'same_day'
    # Corrections cannot silently downgrade a previously raised urgent warning.
    if previous and LEVELS[previous.level] >= LEVELS['same_day']:
        if LEVELS[previous.level] > LEVELS[level]:
            level = previous.level
        reasons += previous.reasons
        ids += previous.rule_ids
    return Escalation(level=level, reasons=list(dict.fromkeys(reasons)), rule_ids=list(dict.fromkeys(ids)))

def action(level):
    return {
        'emergency': 'Seek emergency medical help now. Contact your local emergency service or go to the nearest emergency department. Do not drive yourself if you are unwell. Do not wait to finish this chat.',
        'same_day': 'Seek urgent medical assessment today. If symptoms are severe, worsening, or include trouble breathing, chest pressure, fainting or sudden loss of sight, seek emergency help now. Do not wait to finish this chat.',
        'soon': 'Arrange an assessment with a clinician soon. Seek urgent help if symptoms worsen or warning signs appear.',
        'routine': 'Discuss persistent or concerning symptoms with a clinician. This chat cannot confirm a cause.',
        'not_established': 'There is not enough information to establish urgency or a cause. Answer the next useful question or contact a clinician. Seek urgent help for severe, sudden or rapidly worsening symptoms.',
    }[level]
