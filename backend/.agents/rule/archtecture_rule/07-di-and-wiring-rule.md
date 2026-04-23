# DI and Wiring Rule

## Goal

Define the active backend dependency-injection rule for FastAPI + dependency-injector.

This rule exists to keep runtime wiring predictable, bounded-context composition narrow, and async resource resolution safe.

## Core Rule

Dependency injection must follow this ownership order:

- root container owns truly shared runtime resources
- bounded-context containers own only context-local repositories and use cases
- routers depend on use cases or narrow ports, not broad infrastructure composition

## Root Container Rule

The root container is the only place that should own backend-wide async resources such as:

- database engine resources
- cache/redis resources
- shared session factories
- other cross-domain runtime lifecycle objects

Allowed shape:

- `providers.Resource(...)` for shared async lifecycle resources
- `providers.Container(...)` to pass shared dependencies into bounded-context containers

Do not duplicate async runtime resources inside each bounded context.

## Bounded Context Container Rule

Bounded-context containers should receive shared runtime dependencies from the root container and compose only their local objects.

Allowed shape:

- repository providers
- use-case providers
- context-local service providers

Do not let bounded-context containers create their own database engine or redis client when those lifecycles are already shared.

## Router Injection Rule

FastAPI router dependencies must be async-safe when the provider chain touches async `Resource(...)` providers.

### Required

If a router dependency helper uses `Depends(Provide[...])` and the resolved provider path depends on an async resource, the helper itself must be `async def`.

Good direction:

- async dependency helper returning a narrow port or use case
- async route handler directly using `Depends(Provide[...])`

Bad direction:

- sync dependency helper wrapping `Depends(Provide[...])` for a provider chain that reaches async resources

Reason:

FastAPI may execute sync dependencies in a worker thread. If dependency-injector then needs to resolve an async provider from that sync thread path, runtime failures such as missing event loops can occur.

## Repository Folder Naming

For new backend work, use plural repository folders:

- domain contracts / ports: `<backend_root>/<domain>/domain/repositories/`
- infrastructure implementations: `<backend_root>/<domain>/infrastructure/repositories/`

Existing singular `repository/` folders are legacy and should not be used as a template for new collector work.

## Port Injection Rule

Routers and use cases should depend on the narrowest contract that matches their concern.

Good direction:

- public read router → read port
- admin review command/query router → admin review port
- analytics/dashboard router → analytics port

Bad direction:

- one umbrella repository port containing unrelated public read, admin mutation, and analytics methods

If a repository contract grows across unrelated query families, split it before the application/router surface spreads further.

## Use Case Construction Rule

Prefer container-built use cases over router-local manual assembly when the bounded context already has an established DI shape.

Transitional manual assembly is acceptable only when:

- the bounded context is still being normalized
- the construction is small and local
- there is no duplicated runtime ownership

Target direction remains bounded-context container ownership.

## Testing Rule

Tests should override narrow router dependencies or inject narrow ports/use cases, not broad concrete container state.

Prefer:

- FastAPI dependency overrides for router-level tests
- fake ports for use-case tests

Avoid:

- relying on broad concrete repository composition when a narrower port exists

## Review Checklist

Before accepting backend DI changes, verify all of the following:

- async shared resources live in the root/shared container only
- bounded-context containers only compose local objects from injected shared runtime dependencies
- no sync router dependency helper resolves an async provider chain
- routers depend on narrow ports or use cases
- repository contracts do not mix unrelated concern families without strong reason
- tests override narrow dependencies rather than broad concrete composition

## Current Repo Alignment Targets

Use these current repo patterns as the active baseline:

- `<backend_root>/container.py` for shared runtime ownership
- `<shared_root>/infrastructure/container.py` for shared database resource ownership
- `<backend_root>/classic_feed/containers.py` for bounded-context composition
- `<backend_root>/collector/containers.py` for bounded-context composition where the collector owns local wiring
- route dependency helpers should stay in each active bounded context router module

This rule is active for backend work going forward.
