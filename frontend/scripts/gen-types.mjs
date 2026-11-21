// Generate src/api/schema.ts from the backend's Pydantic models (via FastAPI's OpenAPI schema),
// so the frontend never hand-maintains a second copy of the JSON contracts.
import { execFileSync } from 'node:child_process'
import { existsSync } from 'node:fs'
import path from 'node:path'

const root = path.resolve(import.meta.dirname, '..', '..')
const venvPython = process.platform === 'win32'
  ? path.join(root, '.venv', 'Scripts', 'python.exe')
  : path.join(root, '.venv', 'bin', 'python')
const python = existsSync(venvPython) ? venvPython : 'python'

execFileSync(python, [path.join(root, 'scripts', 'export_openapi.py'), 'openapi.json'], { stdio: 'inherit' })
const cli = path.join(import.meta.dirname, '..', 'node_modules', 'openapi-typescript', 'bin', 'cli.js')
execFileSync(process.execPath, [cli, 'openapi.json', '-o', 'src/api/schema.ts'], { stdio: 'inherit' })
