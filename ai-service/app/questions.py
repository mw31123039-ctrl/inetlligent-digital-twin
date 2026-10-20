from .schemas import Question

SAFETY = {
    'eyes': 'Are you having sudden loss of sight, sudden severe eye pain, a painful red eye, or a change in vision?',
    'head': 'Are you having a sudden worst-ever headache, new weakness, trouble speaking, or a fever with a stiff neck?',
    'chest': 'Are you having severe chest pressure, trouble breathing, fainting, or pain spreading to your arm or jaw?',
    'abdomen': 'Are you having sudden severe abdominal pain, vomiting blood, black stools, or fainting?',
    'arms': 'Are you having sudden arm weakness, a cold or pale hand, a major injury, or chest pain?',
    'legs': 'Are you having new swelling in one leg, a cold or pale foot, a major injury, or trouble breathing?',
}
TEXT = {
    'symptoms': 'In your own words, what is bothering you about your {region}?',
    'location': 'Where exactly do you feel it, and which side is affected?',
    'onset': 'When did this first start, and did it start suddenly or gradually?',
    'duration': 'How long does each episode last, or has it been continuous?',
    'severity': 'How severe is it, and how is it affecting your usual activities?',
    'related_symptoms': 'What other symptoms have you noticed at the same time?',
    'medical_history': 'What past conditions, injuries, or recent procedures seem relevant to this problem?',
    'medications': 'Are you taking any medicines or supplements, particularly anything new or recently changed?',
    'allergies': 'Do you have any known allergies that might relate to this problem?',
}
CORE = ['symptoms', 'warning_signs', 'location', 'onset', 'duration', 'severity', 'related_symptoms']
UNKNOWN = {"i don't know", 'unknown', 'not sure', 'prefer not to say', 'unsure'}

def question(field, region):
    text = SAFETY[region] if field == 'warning_signs' else TEXT[field].format(region=region)
    options = ['No', 'Yes — I will describe', 'Not sure'] if field == 'warning_signs' else ['None', 'Not sure', 'Prefer not to say'] if field in ['related_symptoms', 'medical_history', 'medications', 'allergies'] else []
    return Question(field=field, text=text, options=options)

def relevant_fields(region, facts):
    text = ' '.join(f.value for f in facts if f.field == 'symptoms').lower()
    extra = []
    if any(word in text for word in ['pain', 'hurt', 'injur', 'surg', 'chronic', 'diabet', 'repeat', 'again']):
        extra.append('medical_history')
    if any(word in text for word in ['pain', 'hurt', 'dry', 'itch', 'rash', 'dizz', 'bleed', 'swell', 'nause']):
        extra.append('medications')
    if any(word in text for word in ['itch', 'red', 'rash', 'swell', 'allerg', 'medicine', 'medication']):
        extra.append('allergies')
    return CORE + extra
