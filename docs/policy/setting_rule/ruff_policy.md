# Ruff Policy for Agents

Source of truth: `backend/pyproject.toml` and `Makefile`.
Last verified: 2026-04-23.

이 문서는 `AGENTS.md`에 붙여 넣거나 링크할 수 있는 Ruff 정책 설명입니다.
Backend Python 코드는 Ruff를 canonical formatter/linter로 사용합니다.

## Policy Summary

- Ruff는 backend 코드의 포맷팅과 lint를 담당합니다.
- Python target은 `py312`입니다.
- 기본 line length는 `88`입니다.
- Ruff source root는 backend 기준 `app`입니다.
- Ruff 실행 범위는 Makefile 기준 `backend/app backend/tests`입니다.
- 자동 수정이 필요한 경우 `make format`을 사용합니다.
- 검증/CI 모드에서는 `make format_check`를 사용합니다.

## Configuration Snapshot

Current config from `backend/pyproject.toml`:

```toml
[tool.ruff]
target-version = "py312"
line-length = 88
src = ["app"]
extend-exclude = [
  ".venv",
  ".ruff_cache",
  ".pytest_cache",
]
```

## Enabled Rule Families

Ruff currently enables these lint families:

```text
E    pycodestyle errors
F    Pyflakes
I    isort
UP   pyupgrade
B    flake8-bugbear
SIM  flake8-simplify
C4   flake8-comprehensions
PIE  flake8-pie
PERF Perflint
N    pep8-naming
RUF  Ruff-specific rules
ARG  flake8-unused-arguments
RET  flake8-return
PT   flake8-pytest-style
D    pydocstyle
S    flake8-bandit security rules
TRY  tryceratops
```

Agents should satisfy these rules by changing code rather than suppressing warnings.
Use suppressions only when unavoidable and keep them narrow.

## Ignored Rules

The repository intentionally ignores:

```text
E501  line length handled by formatter/context
B008  FastAPI-style dependency defaults may require function-call defaults
D100  missing module docstring
D104  missing package docstring
D105  missing magic method docstring
D107  missing __init__ docstring
```

Do not remove or add ignored rules casually. Ruff config changes affect the whole backend policy.

## Per-file Ignores

```toml
[tool.ruff.lint.per-file-ignores]
"migrations/**/*.py" = ["D"]
"tests/**/*.py" = ["D", "S101"]
```

Meaning:

- Migration files do not require docstrings.
- Test files do not require docstrings.
- Test files may use plain `assert`.

## Import, Docstring, and Format Style

```toml
[tool.ruff.lint.isort]
combine-as-imports = true

[tool.ruff.lint.pydocstyle]
convention = "google"

[tool.ruff.format]
quote-style = "double"
indent-style = "space"
```

Agent expectations:

- Use double quotes after formatting.
- Use spaces for indentation.
- Keep imports Ruff/isort-compatible.
- Public backend classes, functions, and methods should use Google-style docstrings with `Args`, `Returns`, and `Raises` where applicable.
- Do not manually fight Ruff formatting.

## Commands

Apply formatting and safe autofixes:

```bash
make format
```

Check formatting and lint without modifying files:

```bash
make format_check
```

Full backend quality gate:

```bash
make ci
```

## Agent Rules

- Before claiming backend work is complete, Ruff must pass through `make ci` or at least `make format_check` for Ruff-only changes.
- Prefer fixing code over adding `# noqa`.
- If `# noqa` is required, make it specific and document why.
- Do not introduce new Ruff configuration changes unless the task explicitly requires changing policy.
