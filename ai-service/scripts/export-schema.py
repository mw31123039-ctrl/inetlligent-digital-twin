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
