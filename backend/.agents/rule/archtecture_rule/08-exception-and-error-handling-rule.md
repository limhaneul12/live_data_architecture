# 08. Exception And Error Handling Rule

## Goal

Express failure with domain meaning first, keep shared exception surfaces narrow, and reserve broad built-in exceptions for runtime or parsing edges only.

## Domain Exception Rule

### Adopt now

When a bounded context has repeated, semantically distinct failure cases, define named domain exceptions and raise them at the boundary where the failure becomes meaningful.

Active backend domains should use:

- `<shared_root>/exceptions/collector_exceptions.py`
- `<shared_root>/exceptions/classic_feed_exceptions.py`

The current rule is to keep the catalog under `<shared_root>/exceptions/` because the repo explicitly wants one discoverable exception surface. Domain-specific modules may live there, but class names must still stay domain-scoped.

Examples:

- `CollectorSeedValidationError`
- `CollectorConfigurationError`
- `CollectorUpstreamError`
- `EventEngineEventNotFoundError`
- `EventEngineCandidatePayloadError`
- `ClassicFeedEventNotFoundError`
- `ClassicFeedActionCardNotFoundError`

## Shared Exception Rule

### Adopt narrowly

Only truly cross-domain contracts belong in shared exception modules.

Good shared candidates:

- route-to-HTTP mapping exceptions
- shared stream/runtime retry-drop exceptions
- shared decorator contracts

Current shared modules:

- `route_exceptions.py`
- `stream_exceptions.py`
- `common_exceptions.py`
- `exception_decorators.py`

Do not move domain-specific business failures into these neutral files just because multiple routers happen to map them.

Do not create per-domain exception packages such as `<backend_root>/<domain>/exceptions/` unless this backend-wide exception policy is intentionally revised.

## Broad Built-in Raise Rule

### Adopt now

Do not raise broad built-in exceptions such as:

- `RuntimeError`
- `ValueError`
- `TypeError`

from domain/application/runtime boundaries when a stable domain meaning already exists.

Prefer:

- domain exception for domain failures
- shared route/stream exception for shared transport/runtime contracts

Allowed exceptions:

- environment/bootstrap validation where the failure is still infrastructure-global
- guardrail/checker failure where the code intentionally aborts startup
- very local parse helpers where introducing a domain exception would add no semantic value

## Broad Catch Rule

### Adopt narrowly

`except Exception` is allowed only in these cases:

1. worker/runtime loop protection
2. health/readiness probes
3. shared decorator/facade boundaries that intentionally map arbitrary exception families
4. tiny best-effort parse helpers
5. smoke/maintenance code that should keep scanning despite partial failures

When used, the catch block should do one of these clearly:

- log and continue
- map to a domain/shared exception
- apply retry/drop policy
- return a bounded fallback value

Do not use `except Exception` inside normal application decision code when the caller needs to know the difference between not-found, invalid-input, upstream-failure, and configuration-failure cases.

## Router Mapping Rule

### Adopt now

Routers should map domain exceptions directly instead of:

- receiving `None`/`False` sentinels for error cases
- checking `status == "error"` for predictable domain failures
- catching broad built-in exceptions and guessing an HTTP status

Preferred direction:

- use case raises `EventEngineEventNotFoundError`
- router maps that exception to `404`

Bad direction:

- use case returns `StatusData(status="error", message="Event not found")`
- router reinterprets that string into a `404`

## Stream Runtime Rule

### Adopt now

Shared stream runtime should keep:

- `DropMessageError` for non-retryable message failures
- shared exception decorator logic in `exception_decorators.py`
- policy objects in `common_exceptions.py`

Do not introduce domain-specific stream failures into the shared runtime package unless the failure semantics are truly runtime-wide.

## Review Checklist

Before adding or changing exception handling, verify:

1. Is this a domain failure with repeated meaning?
2. Does a domain exception already exist?
3. Is a broad built-in raise still justified?
4. Is `except Exception` truly acting as a runtime/decorator/health boundary?
5. Is the router mapping a real exception instead of interpreting sentinel values?
