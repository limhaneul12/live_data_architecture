# 02. Shared Runtime, Container, Bootstrap

## Goal

Keep runtime composition stable and explicit without forcing every domain into one container model too early.

Current target naming:

- prefer `shared/infrastructure/` over vague root names like `shared/db/`

## Current Reality

The repo currently uses mixed composition styles:

- `classic_feed` uses the root DI container
- `collector` mixes local container composition, local bootstrap, and bounded-context workers/maintenance paths

This means a single giant shared container is not the right immediate target.

The target is a small shared infrastructure container plus domain-local composition where needed.

## Container Rule

### Adopt now

Use a shared root container only for dependencies that multiple domains truly share.

Preferred path:

- keep a small shared root runtime composition layer for app startup concerns
- place genuinely cross-domain DI in root `<backend_root>/container.py`
- place shared DB/session infra resources in `<shared_root>/infrastructure/container.py`
- allow bounded contexts to own their own local `containers.py` when they need local composition
- move dependencies into the shared container only when multiple domains really use them

Do not turn the shared container into a global dump of every repository and every use case.

Dependency-injector direction:

- shared infra resources should use dedicated providers/resources
- root app container may compose the shared infra container instead of duplicating its providers
- lifecycle-heavy resources such as database engine and cache connections belong in resource providers
- repositories and use cases should not own engine/cache lifecycle directly

Current ownership note:

- DB/session lifecycle is shared infrastructure
- cache lifecycle should remain root-owned when a future runtime needs it

## Session / Engine Rule

This is one of the best first shared extractions.

Good candidates for `shared/`:

- database engine resource creation
- async session factory creation
- cache connection resource creation
- ORM base and shared persistence primitives

Reason:

- this is already leaking across domains
- it is infrastructure/runtime code, not business logic

## Environment Rule

- root shared config stays in `<backend_root>/settings.py`
- context-specific config stays in `{context}/config.py`
- environment parsing happens only at config boundaries
- non-local required settings should fail fast
- prefer constants over env vars unless the value is truly deployment-dependent
- do not introduce environment variables for stable business/domain constants

## Bootstrap Rule

### Adopt now

Runtime bootstrap should use one stable module entrypoint.

Current preferred pattern:

- `cd backend && uv run --group local --python 3.12.10 python -m app.collector.bootstrap`

Do not spread runtime bootstrap across many standalone scripts.

## Bootstrap Data Format Rule

### Adopt now as target direction

Bootstrap orchestration should stay in Python, but seed data itself should move toward YAML-backed static artifacts.

Preferred target split:

- loader/orchestration in Python
- static bootstrap data in YAML
- explicit schema validation at load time

Why:

- separates configuration artifacts from execution code
- makes large static seed sets easier to review and maintain
- reduces pressure to keep giant constant blobs in runtime modules

Guardrail:

- YAML is only acceptable with strict validation and fail-fast loading

## Runtime Entry Rule

- prefer one stable module entrypoint or Makefile target
- do not grow a new layer of wrappers unless it removes real complexity
- runtime-critical commands should be obvious from Docker/compose startup definitions
