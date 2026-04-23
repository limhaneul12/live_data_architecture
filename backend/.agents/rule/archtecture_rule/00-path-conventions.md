# 00. Path Conventions

## Goal

Make backend architecture rules portable by separating logical paths from this repository's concrete filesystem layout.

Rules in this folder should prefer logical path variables in normative sections. Concrete paths are allowed in examples, current-repo alignment notes, and migration notes.

## Logical Path Variables

- `<backend_root>` — backend runtime source root
- `<test_root>` — backend test root
- `<shared_root>` — shared backend code root
- `<docs_rule_root>` — backend rule document root
- `<domain>` — bounded-context directory name under `<backend_root>`

## Project-local Mapping

For this repository:

- `<backend_root>` = `backend/app`
- `<test_root>` = `backend/tests`
- `<shared_root>` = `backend/app/shared`
- `<docs_rule_root>` = `docs/rule/backend_dev_rule`
- current active domains:
  - `classic_feed`
  - `collector`

## Usage Rule

Use logical paths in rules:

```text
<backend_root>/<domain>/domain/repositories/
<backend_root>/<domain>/infrastructure/repositories/
<shared_root>/exceptions/
<test_root>/<domain>/
```

Avoid hardcoding project-local paths in normative rules:

```text
backend/app/collector/domain/repositories/
backend/tests/collector/
backend/app/shared/exceptions/
```

Concrete paths are still useful in examples and alignment sections when they clarify this repository's current state.
