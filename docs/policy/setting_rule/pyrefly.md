# Pyrefly Policy for Agents

Source of truth: `backend/pyproject.toml` and `Makefile`.
Last verified: 2026-04-23.

이 문서는 `AGENTS.md`에 붙여 넣거나 링크할 수 있는 Pyrefly 정책 설명입니다.
Backend Python 코드는 Pyrefly를 canonical static type checker로 사용합니다.

## Policy Summary

- Pyrefly는 backend static type checking을 담당합니다.
- Python version은 `3.12`입니다.
- Pyrefly 실행 범위는 Makefile 기준 `backend/app backend/tests`입니다.
- `check-unannotated-defs = true`이므로 annotation이 없는 함수 body도 type checking 대상입니다.
- `infer-return-types = "checked"`이므로 추론된 return type도 검증 대상입니다.
- `min-severity = "error"`이므로 error severity는 반드시 해결해야 합니다.

## Configuration Snapshot

Current config from `backend/pyproject.toml`:

```toml
[tool.pyrefly]
python-version = "3.12"
project-includes = ["app", "tests"]
project-excludes = [
  "**/__pycache__",
  "**/.venv/**",
  "**/venv/**",
  "**/.mypy_cache/**",
  "**/.ruff_cache/**",
  "**/build/**",
  "**/dist/**",
  "**/.pytest_cache/**",
  "**/.git/**",
]
search-path = ["app", "."]
check-unannotated-defs = true
infer-return-types = "checked"
min-severity = "error"
```

## Included Paths

Pyrefly checks backend project code and tests:

```text
app
tests
```

From the repository root, Makefile runs Pyrefly against:

```text
backend/app
backend/tests
```

## Excluded Paths

Generated/cache/build paths are excluded:

```text
**/__pycache__
**/.venv/**
**/venv/**
**/.mypy_cache/**
**/.ruff_cache/**
**/build/**
**/dist/**
**/.pytest_cache/**
**/.git/**
```

## Typing Expectations

Agents should write backend code that is easy for Pyrefly to verify.

- Public backend APIs should be explicitly typed.
- Domain/application code should use precise owned types.
- Prefer:
  - dataclasses
  - `TypedDict`
  - `TypeAlias`
  - `StrEnum`
  - `ABC` ports/interfaces
- Do not use Pydantic as domain state. Pydantic belongs at IO/interface boundaries.
- Do not use `Protocol` for owned ports/interfaces; use `ABC`.
- Avoid broad `Any`, broad `object`, broad dictionaries, `getattr(...)`, and `hasattr(...)`.
- If broad dynamic typing is unavoidable, add a short justification comment explaining the boundary or dynamic behavior.

## Nullability and Fallback Expectations

- `None` is allowed only when absence is meaningful in the contract.
- Do not hide fallback behavior with `or {}`, `or []`, or dependency fallback expressions.
- Prefer non-nullable parameters and explicit empty containers at call sites.
- Use explicit `is None` branches only when absence is part of the contract.
- Dependencies must be injected explicitly; do not create fallback dependencies inside constructors or functions.

## Commands

Run Pyrefly only:

```bash
make type_checking
```

Run full backend quality gate:

```bash
make ci
```

## Agent Rules

- Fix Pyrefly errors before claiming completion.
- Do not silence type errors with broad casts or `Any` unless the boundary requires it.
- Do not change Pyrefly configuration casually.
- If changing type policy, document the reason because it affects backend-wide verification.
