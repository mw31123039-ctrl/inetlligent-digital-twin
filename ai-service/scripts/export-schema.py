import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
from app.schemas import Assessment

schema = Assessment.model_json_schema()
schema['$schema'] = 'https://json-schema.org/draft/2020-12/schema'
(root.parent / 'contracts' / 'assessment.schema.json').write_text(json.dumps(schema, indent=2), encoding='utf-8')
print('Exported assessment JSON Schema.')
from app.dental_photo import PhotoDetectionResult
photo_schema = PhotoDetectionResult.model_json_schema()
photo_schema['$schema'] = 'https://json-schema.org/draft/2020-12/schema'
(root.parent / 'contracts/dental/photo-detection.schema.json').write_text(json.dumps(photo_schema, indent=2) + '\n', encoding='utf-8')
print('Exported dental photo-detection JSON Schema.')
from app.dental_screening import ScreeningRecord
screening_schema = ScreeningRecord.model_json_schema()
screening_schema['$schema'] = 'https://json-schema.org/draft/2020-12/schema'
(root.parent / 'contracts/dental/screening-case.schema.json').write_text(json.dumps(screening_schema, indent=2) + '\n', encoding='utf-8')
print('Exported orthodontic screening-case JSON Schema.')
from app.cancer import CancerResult
cancer_schema = CancerResult.model_json_schema()
cancer_schema['$schema'] = 'https://json-schema.org/draft/2020-12/schema'
(root.parent / 'contracts/cancer-result.schema.json').write_text(json.dumps(cancer_schema, indent=2) + '\n', encoding='utf-8')
print('Exported cancer research result JSON Schema.')
from app.cancer_knowledge import KnowledgeAnswer
knowledge_schema = KnowledgeAnswer.model_json_schema()
knowledge_schema['$schema'] = 'https://json-schema.org/draft/2020-12/schema'
(root.parent / 'contracts/cancer-knowledge-result.schema.json').write_text(json.dumps(knowledge_schema, indent=2) + '\n', encoding='utf-8')
print('Exported local cancer evidence search JSON Schema.')
