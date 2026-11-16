"""Write real engine outputs used as Laravel/Vue test fixtures (synthetic inputs only)."""
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'ai-service'))
from app.clinical.engine import Engine  # noqa: E402
from app.clinical.simulate import run  # noqa: E402


async def main():
    engine = Engine()
    collecting, _ = await run(engine, 'body.eyes', ['My left eye is red, itchy and sticky since yesterday', {'codes': ['none']}, {'codes': ['onset:gradual']}], side='left')
    urgent, _ = await run(engine, 'body.chest', ['Crushing chest pain spreading to my left arm and I am sweating'])
    out = ROOT / 'backend/tests/Fixtures'
    for name, assessment in (('clinical-collecting.json', collecting[-1]), ('clinical-urgent.json', urgent[-1]), ('clinical-start.json', collecting[0])):
        (out / name).write_text(json.dumps(json.loads(assessment.model_dump_json()), ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    frontend = ROOT / 'frontend/tests/fixtures'
    frontend.mkdir(parents=True, exist_ok=True)
    (frontend / 'clinical-collecting.json').write_text((out / 'clinical-collecting.json').read_text(encoding='utf-8'), encoding='utf-8')
    print('fixtures written')


asyncio.run(main())
