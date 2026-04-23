# Required Commands Make Policy for Agents

Source of truth: `Makefile`, `backend/pyproject.toml`, and `backend/.agent/AGENTS.md`.
Last verified: 2026-04-23.

이 문서는 `AGENTS.md`에 붙여 넣거나 링크할 수 있는 required command policy입니다.
Backend quality gates must be run through Makefile targets and `uv`.

## Do Not Use pip Directly

Use `uv`; do not call `pip` directly.
The Makefile already wraps backend commands with the correct Python version and dependency group.

Current Python version from Makefile:

```makefile
PYTHON_VERSION := 3.12.10
```

## Makefile Scopes

Current backend scopes:

```makefile
CHECK_PATHS := backend/app backend/tests
TEST_PATHS := backend/tests
TYPECHECK_PATHS := backend/app backend/tests
```

Meaning:

- Ruff format/lint checks `backend/app backend/tests`.
- Pyrefly checks `backend/app backend/tests`.
- Pytest runs `backend/tests`.

## Environment Commands

Install/sync local backend dev dependencies:

```bash
make install-local
```

Other environment sync targets:

```bash
make install
make install-prod
make install-qa
make install-stage
```

Routine verification should use `uv run` through Makefile targets.
`install-*` targets are only for explicit environment sync.

## Formatting Commands

Apply Ruff formatting and Ruff autofixes:

```bash
make format
```

Equivalent Makefile behavior:

```bash
ruff format backend/app backend/tests
ruff check backend/app backend/tests --fix
```

Check formatting and lint without modifying files:

```bash
make format_check
```

Equivalent Makefile behavior:

```bash
ruff format --check backend/app backend/tests
ruff check backend/app backend/tests
```

## Type-check Command

Run Pyrefly:

```bash
make type_checking
```

Equivalent Makefile behavior:

```bash
pyrefly check backend/app backend/tests
```

## Test Command

Run backend tests:

```bash
make test
```

Equivalent Makefile behavior:

```bash
python -m pytest backend/tests
```

## Full Backend CI Gate

After backend changes, run:

```bash
make ci
```

`make ci` runs:

```bash
make format_check
make type_checking
make test
```

Do not claim backend completion until this passes, unless the only changes are documentation-only and no backend behavior/tooling changed.
If `make ci` cannot be run, report the blocker and the narrower verification that was run.

## Frontend-visible Change Gate

If backend work changes frontend-visible behavior, also run from `frontend/`:

```bash
npm run lint
npm run typecheck
npm run build
```

## Development Runtime Commands

Run FastAPI development server on port `8000`:

```bash
make dev
```

Run production-style FastAPI command:

```bash
make run
```

## Database Commands

Initialize PostgreSQL schema and metadata only:

```bash
make db_init
```

Apply migrations:

```bash
make migrate
# or
make db_upgrade
```

Create migration revision:

```bash
MESSAGE="schema change" make makemigration
# or
MESSAGE="schema change" make db_revision
```

## Backend Domain Generator Commands

For any new backend module/bounded context, do not hand-create folders first.
Use the generator:

```bash
make generate <domain>
# or
make generator <domain>
# or
make generate APP_NAME=<domain>
```

Domain names must be snake_case and start with a lowercase letter.

## Docker Compose Commands

Build compose services:

```bash
make compose-build
```

Run API and frontend with Docker Compose:

```bash
make compose-up
```

Stop compose services:

```bash
make compose-down
```

Follow compose logs:

```bash
make compose-logs
```

## Agent Completion Rule

Before final response for backend work, include verification evidence:

- command run
- pass/fail result
- any skipped checks and why

Required default:

```bash
make ci
```
