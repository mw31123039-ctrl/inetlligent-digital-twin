// The mocked Cancer research browser check now lives in tests/e2e/cancer.spec.ts (Playwright test runner).
// This wrapper keeps `node scripts/smoke-cancer.mjs` working: it runs that spec against the dev server.
// Real-model checks: node scripts/smoke-cancer-real.mjs and node scripts/smoke-cancer-care.mjs (all three services running).
import { spawnSync } from 'node:child_process'

const result = spawnSync('npx', ['playwright', 'test', 'tests/e2e/cancer.spec.ts', '--reporter=line'], { stdio: 'inherit', shell: process.platform === 'win32' })
process.exit(result.status ?? 1)
