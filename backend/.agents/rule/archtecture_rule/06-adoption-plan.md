# 06. Adoption Plan

## Goal

Translate the rules into a safe refactor order.

## Phase 1 — Adopt Now

### 1. Keep bounded contexts as the primary backend shape

Do not flatten backend code into one shared layer.

### 2. Narrow shared extraction only

First candidates:

- SQLAlchemy base/model primitives
- session/engine helpers
- neutral infra/runtime helpers
- shared constants
- truly cross-domain DI in the root container

### 3. Use `<test_root>/<domain>` as the test layout

This is the active test architecture.

### 4. Keep domain generation aligned with `<test_root>/<domain>`

This is already part of the scaffold shape and should remain so.

### 5. Add an application-scaling convention before `application/` becomes flat-file sprawl

Use feature-family expansion such as `application/{feature}_usecase/` when the use-case surface grows large.

### 6. Add a class-responsibility review threshold before hotspot classes grow further

Use a practical warning threshold at more than 8 methods (excluding `__init__`) and treat more than 12 methods or mixed-concern classes as split/refactor candidates.

## Phase 2 — Adopt Narrowly

### 1. Domain exceptions only when repeated errors appear

Do not design a global exception tree before the need is real.

### 2. Root/domain split for `conftest.py`

Use `<test_root>/conftest.py` only for truly shared fixtures and keep domain-specific fixtures under `<test_root>/<domain>/conftest.py`.

### 3. Builders/factories selectively

Prefer them as the default test setup style, but keep explicit setup where it is materially clearer.

### 4. Use grouped verification for shape-heavy tests

Prefer expected-dictionary or grouped assertion style when checking large DTO/payload shapes.

## Phase 3 — Defer

### 1. One giant shared container

Defer unless multiple domains converge on the same lifecycle/composition style.

### 2. Broad `shared/` usage

Defer broad shared extraction; keep it narrow.

### 3. Optional environment-variable expansion

Defer adding env vars for values that can stay as constants.

### 4. Unvalidated YAML bootstrap data

Defer unvalidated YAML; target YAML only with strict validation.

## Decision Summary

### Strong now

- bounded-context-first layout
- narrow shared runtime extraction
- shared infrastructure package for cross-domain DB/session/runtime resources
- `<test_root>/<domain>` target test layout
- generate-domain with `<test_root>/<domain>` as target shape
- dataclass-internal / Pydantic-boundary split
- YAML bootstrap as target direction with validation
- class responsibility first, with method-count thresholds as a warning signal
- shared guardrails under `<shared_root>/` for backend-wide architectural checks

### Good with guardrails

- shared exceptions only after repeated cross-domain need is proven
- grouped assertions
- builders/factories
- root/domain split for `conftest.py`
- root shared container only for truly shared DI

### Not the default target yet

- broad `shared/` usage
- one master container for every domain
