"""Drive the stateless engine through a scripted conversation (tests, evaluation and local demos).

This mirrors what Laravel does: append the assistant's next question, then the patient's reply, and
re-assess with the whole transcript.
"""
import itertools

from .schemas import AssessRequest

_ids = itertools.count(1)


def _id(prefix):
    return f'{prefix}-{next(_ids)}'


async def run(engine, anatomy, turns, side='unknown', locale='en', context=None, max_questions=12, prior_urgency=None):
    """turns: list of str (free text) or dict(text=..., codes=[...], correct=<turn index>)."""
    messages = []
    request = AssessRequest(locale=locale, anatomy={'id': anatomy, 'side': side}, messages=[], patient_context=context or [], max_questions=max_questions)
    assessment = await engine.assess(request)
    history = [assessment]
    user_ids = []
    if assessment.next_question:
        messages.append({'id': _id('a'), 'role': 'assistant', 'text': assessment.next_question.text, 'question_id': assessment.next_question.id})
    for turn in turns:
        spec = {'text': turn} if isinstance(turn, str) else dict(turn)
        codes = spec.get('codes', [])
        text = spec.get('text') or ' '.join(codes) or '-'
        message = {'id': _id('u'), 'role': 'user', 'text': text, 'answer_codes': codes}
        if 'correct' in spec:
            target = user_ids[spec['correct']]
            index = next(i for i, m in enumerate(messages) if m['id'] == target)
            messages[index]['superseded_by'] = message['id']
            message['question_id'] = messages[index].get('question_id') or next((m.get('question_id') for m in reversed(messages[:index]) if m['role'] == 'assistant'), None)
            messages.insert(index + 1, message)
        else:
            messages.append(message)
        user_ids.append(message['id'])
        urgency = history[-1].urgency
        request = AssessRequest(locale=locale, anatomy={'id': anatomy, 'side': side}, messages=messages, patient_context=context or [], max_questions=max_questions,
                                prior_urgency={'level': urgency.level, 'rule_ids': [r.rule_id for r in urgency.reasons]} if prior_urgency is not False else None)
        assessment = await engine.assess(request)
        history.append(assessment)
        if assessment.next_question:
            messages.append({'id': _id('a'), 'role': 'assistant', 'text': assessment.next_question.text, 'question_id': assessment.next_question.id})
    return history, messages
