# Backend Test Policy for Agents

Source of truth: root `AGENTS.md`, `backend/.agent/AGENTS.md`, `backend/.agent/rule/backend_dev_rule/03-testing-and-quality-gates.md`, `backend/pyproject.toml`, and `Makefile`.
Last verified: 2026-04-23.

이 문서는 `AGENTS.md`에 붙여 넣거나 링크할 수 있는 backend test policy입니다.
Tests must protect behavior, not implementation.

## Test Location

All backend tests live under:

```text
backend/tests/
```

Domain tests go under:

```text
backend/tests/<domain>/
```

Shared helper tests go under:

```text
backend/tests/shared/
```

Do not scatter backend tests next to production modules unless the repository structure is intentionally changed.

## Pytest Discovery

Current pytest config from `backend/pyproject.toml`:

```toml
[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]
python_files = ["test_*.py"]
addopts = "--strict-markers"
norecursedirs = [".venv", ".pytest_cache", ".ruff_cache", "node_modules"]
```

Policy:

- Test files must match `test_*.py`.
- Backend pytest root is `backend/tests`.
- Strict markers are enabled through `--strict-markers`.
- If adding a new pytest marker, register it properly instead of relying on undeclared markers.

## Core Testing Philosophy

1. Test behavior, not implementation.
2. Mock only at system boundaries.
3. Prefer Classist/Chicago-style tests.
4. Fewer meaningful tests are better than many brittle tests.
5. Refactors should not require test rewrites unless observable behavior changes.

## Mocking Rules

Mock only true boundaries:

- Database / ORM
- Third-party HTTP APIs
- Filesystem boundary when a real temporary filesystem is not suitable
- Clock, randomness, network
- Anything crossing a process boundary

Do not mock repo-owned internals:

- Value objects
- DTOs
- Entities
- Pure functions
- Internal services/modules
- The unit under test

Prefer:

- `httpx.MockTransport` or an HTTP-level fake over mocking internal HTTP client collaborators.
- `tmp_path` / temporary real files over mocked filesystem behavior.
- Real in-memory domain objects over mocks.

## Assertion Rules

Assert observable behavior:

- Return values
- Response payloads
- Persisted state
- Raised domain errors
- External boundary effects, when that is the behavior under test

Avoid using call verification as the primary assertion:

```python
mock.assert_called_once_with(...)
```

Call assertions are acceptable only as secondary evidence for true boundary interactions.

Prefer whole-object or grouped assertions over long repetitive field-by-field checks when verifying payload shape.

Good pattern:

```python
expected = {
    "canonical_title": "Canonical title",
    "canonical_summary": "Canonical summary",
    "source_count": 2,
}

assert {key: payload[key] for key in expected} == expected
```

Single focused assertions are still preferred for simple behavior:

```python
assert normalize_slug(" OpenAI ") == "openai"
```

## Test Naming Rules

Test names should describe observable behavior, not implementation calls.

Use this pattern:

```text
<subject>_<expected_behavior>_when_<condition>
```

Good examples:

```text
returns_cached_result_when_fetched_within_ttl
rejects_login_when_password_is_expired
charges_full_price_for_non_vip_users
```

Bad examples:

```text
test_findUnique_called_once
test_calls_upsert_then_emits_event
test_should_work
```

## Test Structure Rules

Write tests in a clear behavior-first flow:

1. What behavior is being tested
2. Why this case matters
3. Input/setup
4. Action
5. Expected output/state
6. Failure meaning

In code, prefer:

```text
setup/build phase
action/execution phase
grouped verification phase
```

## Builders and Factories

Use builders/factories when setup is dense or repetitive.

Preferred locations:

```text
backend/tests/<domain>/builders/
backend/tests/<domain>/factories/
```

Use root-level shared builders/factories only when multiple domains truly share the helper.
Inline setup is acceptable when it is clearer than adding a builder.

## conftest.py Policy

Use root `backend/tests/conftest.py` only for fixtures genuinely shared across domains.

Use domain-level fixtures for domain-specific setup:

```text
backend/tests/<domain>/conftest.py
```

Do not put domain-specific fixtures in root conftest.

## Test Layer Guidance

Use the smallest test layer that proves the behavior.

| Layer | Use For | Amount |
|---|---|---|
| Unit | Pure domain logic, entities, value objects, utilities | Many |
| Integration | Module behavior with real DB/queue or realistic boundary | Moderate |
| E2E | Critical user journeys | Few |
| Regression | Past bugs/incidents | As needed |

Do not write unit tests for trivial getters, constants, framework wiring, or plain CRUD with no business logic.

## Domain Entity Testing

If business logic is hidden in services operating on plain DB rows, prefer extracting a domain entity/value object and testing it in memory.

- Service code should orchestrate and persist.
- Domain entities should own pure business behavior.

## Property-based Testing

For logic with clear invariants over many inputs, use property-based tests.

Good candidates:

- Parsers
- Normalizers
- Encoders/decoders
- Sorting/ranking logic
- Validators
- State transitions

If writing the fourth example test for the same pure function, consider a property-based test.

## Flaky Test Policy

Never commit flaky tests.

Do not fix flakiness with:

- retry loops
- arbitrary `sleep()`
- larger timeouts without root cause

Common root causes to fix instead:

- shared global state
- real clock usage
- test ordering dependency
- unseeded randomness
- network dependency

If a flaky test must be quarantined temporarily, it must be skipped with:

- linked issue
- owner
- deadline

No owner means delete or fix immediately.

## TDD / Regression Policy

For new behavior or bug fixes:

1. Write or update a behavior-focused failing test first.
2. Implement the smallest change that satisfies the behavior.
3. Run the relevant test.
4. Run `make ci` before completion.

Do not write tests after implementation merely to mirror current implementation details.

## PR/Test Red Flags

Reject or rework tests with these signs:

- More mock setup than real assertions
- `assert_called_with` / `verify()` as the only assertion
- Imports from private/internal paths
- Snapshots of nondeterministic output
- `pytest.skip` without owner/issue/deadline
- Test names that mirror implementation method names
- Test files longer than the production file for trivial code
- New full internal mock frameworks where boundary fakes would work

## When Not to Write a Test

Do not add tests for:

- Plain CRUD with no logic
- Framework wiring
- Static constants/config only
- Throwaway scripts, unless they touch production data
- Code that is about to be deleted

If the protected behavior cannot be stated in one sentence, do not write the test yet.

## One-line Rule

Hide the implementation from the test.
Hide the test from the implementation.
Only behavior connects them.
