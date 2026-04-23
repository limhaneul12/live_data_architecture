# 03. Testing And Quality Gates

## Goal

Keep tests centralized under one backend test root, while preserving domain ownership through `tests/<domain>/` boundaries.

## Test Placement Rule

### Adopt now

Current layout:

- `<test_root>/classic_feed/`
- `<test_root>/collector/`
- `<test_root>/<domain>/`

## Root Test Rule

### Adopt now

All backend tests live under `<test_root>/`.

Reason:

- one canonical test root is easier to discover and enforce
- `tests/<domain>/` still preserves domain ownership
- shared test helpers, builders, and root fixtures become easier to manage intentionally

Current structure:

- backend tests live under `<test_root>/<domain>`
- new test structure work should continue following `<test_root>/<domain>`

## Pytest Discovery Rule

When a new domain is scaffolded, test discovery must not silently miss it.

Current expectation:

- `make generate <domain>` creates `<test_root>/<domain>/`
- pytest config and Makefile test paths already target the root `<test_root>` tree

## Builder / Factory Rule

### Adopt now as preferred test style

Builders and factories are good when object setup is dense or repetitive.
Use them as the default preference for domain test data setup.

Preferred shape:

- `<test_root>/<domain>/factories/`
- `<test_root>/<domain>/builders/`
- domain-focused fake objects where needed

Use root-level shared builders/factories only when multiple domains truly share the same helper.

Explicit inline setup is still acceptable when it is materially clearer than a builder.

## Test Structure Rule

### Adopt now as preferred writing style

Tests should be written with an explicit structured flow.

Preferred mental model:

- what is being tested
- why this case matters
- which input/setup is prepared
- which action is executed
- what output/state is expected
- how failure should be interpreted

This does not require literal prose in every test, but the test body should read in that order.

In practice, this usually maps to:

- setup/build phase
- action/execution phase
- grouped verification phase

## Assertion Rule

### Adopt now as preferred response-check style

Prefer grouped assertions or expected-dict comparisons over long repetitive one-field-per-line assertions when verifying large payloads.

Preferred use:

- response DTOs
- schema serialization
- API payload comparisons
- factory/builder-backed result comparisons

Preferred pattern for shape-heavy checks:

- assemble inputs with factory/builder helpers
- build one expected dictionary or expected fragment
- compare in one grouped assertion or a small number of grouped assertions

Example direction:

```python
expected = {
    "canonical_title": "Canonical title",
    "canonical_summary": "Canonical summary",
    "source_count": 2,
}
assert item | {key: item[key] for key in expected} == item | expected
```

Preferred example for shape-heavy tests:

```python
event = EventBuilder().with_source_count(2).build()
payload = serialize_event(event)

expected = {
    "canonical_title": "Canonical title",
    "canonical_summary": "Canonical summary",
    "source_count": 2,
}

assert {key: payload[key] for key in expected} == expected
```

Still acceptable for short behavior tests:

```python
result = normalize_slug(" OpenAI ")

assert result == "openai"
```

Single focused assertions are still correct when behavior/failure localization matters more than payload bulk.

Avoid turning every test into a long field-by-field assert chain when the test is really about one payload shape.

## `conftest.py` Rule

### Root-first only for truly shared fixtures

Preferred rule:

- use `<test_root>/conftest.py` for fixtures genuinely shared across domains
- use `<test_root>/<domain>/conftest.py` when the fixture is domain-specific

Do not put domain-specific fixtures in the root conftest.

## Quality Gate Rule

Current backend gate is:

- lint/type scope: `<backend_root>` whole tree
- test scope: `<test_root>` whole tree

Routine commands should reuse the existing environment through `uv run`.
`install-*` targets are only for explicit environment sync.
