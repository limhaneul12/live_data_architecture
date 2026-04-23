# 09. Implementation Boundary Rule

## Goal

Keep backend implementation units traceable by separating side effects, pure transformations, persistence introduction, infrastructure adapter behavior, and responsibility naming.

This rule is backend-wide and intentionally module-neutral. Product- or module-specific rules such as collector/engine LLM boundaries belong in the owning domain docs, not here.

## Side Effect Boundary Rule

### Adopt now

Classes and functions that perform side effects must make that ownership explicit in name, layer, and tests.

Side effects include:

- database reads/writes
- network calls
- stream/message publish
- file writes
- cache mutation
- environment access
- business-significant clock/time ownership

Preferred ownership language:

| Responsibility | Preferred names |
|---|---|
| Network IO | `Fetcher`, `Client` |
| Persistence | `Repository` |
| Stream/message output | `Publisher` |
| Pure structural transformation | `Parser`, `Mapper` |
| Business/use-case orchestration | `Service`, `UseCase` |

Do not hide side effects inside:

- mappers
- DTO constructors
- entity/value-object methods
- parser helpers
- schema conversion helpers

A class that mixes unrelated side effects is a split candidate.

Examples:

- good: `HttpSourceFetchClient` owns network fetch only
- good: `SourceSnapshotRepository` owns DB persistence only
- good: `CollectorEventPublisher` owns stream publish only
- bad: one `CollectorManager` that fetches, parses, writes DB rows, publishes streams, and interprets business meaning

## Pure Transformation Rule

### Adopt now

Parsing, mapping, hashing, validation, and DTO conversion should stay pure unless there is a strong reason.

Pure transformation code must not:

- call network
- query or write DB
- publish streams/messages
- read environment variables
- mutate shared runtime state
- own business-significant clock/time decisions

Good examples:

```python
compute_raw_content_hash(raw_content: str) -> str
build_source_fetch_target(source: SourceRegistryEntryRecord) -> SourceFetchTarget
map_row_to_read_model(row: EventRow) -> EventReadModel
```

Bad examples:

```python
parse_and_save_snapshot(...)
map_and_publish_event(...)
build_dto_from_env(...)
```

If a transformation needs external context, pass that context as an explicit typed input instead of reading it inside the transformation.

## Migration Introduction Rule

### Adopt now

Do not introduce DB tables, repositories, or migrations before the persistence contract is clear.

Add a migration only when all are true:

- write contract is explicit
- read contract is explicit
- owning bounded context is clear
- additive/rollback path is understood
- tests cover the persistence contract

A fetcher, parser, validator, or DTO contract may exist without persistence while the contract is being validated.

Avoid:

- adding tables while still exploring fetch/parsing behavior
- adding columns for fields whose meaning is not yet stable
- creating repositories before the read/write use cases are explicit
- speculative migrations for “maybe later” data

Preferred progression:

1. typed DTO / pure function / adapter contract
2. focused tests with in-memory fakes or mock transports
3. persistence contract
4. migration
5. repository implementation
6. integration tests

## Infrastructure Adapter Test Rule

### Adopt now

Every new infrastructure adapter must have focused tests for success and failure behavior.

Infrastructure adapters include:

- HTTP/API clients
- DB repositories
- Redis/cache adapters
- stream/message publishers
- filesystem adapters
- external SDK wrappers

Required focused tests:

- success path
- upstream/status failure path
- timeout/transport failure when applicable
- payload/contract shape
- retry/backoff behavior when applicable
- permission/access-denied behavior when applicable

Do not rely only on E2E tests for external IO adapters.

Good direction:

- HTTP client tested with mock transport for 200, 403, timeout/connection error
- repository tested for write/read contract and duplicate behavior
- publisher tested for payload shape and publish failure mapping

## Responsibility Naming Rule

### Adopt now

Class and file names should reveal the single responsibility they own.

Avoid vague names unless a framework or external contract requires them:

- `Manager`
- `Processor`
- `Handler`
- `Helper`
- `Util`
- `Common`
- `BaseSomethingTooBroad`

Prefer names that reveal ownership:

- `SourceFetchService`
- `HttpSourceFetchClient`
- `SourceEntryParser`
- `CollectorEventPublisher`
- `SourceSnapshotRepository`
- `ReviewQueueMapper`
- `StreamRuntimeObserver`

Naming checks:

- If the class name needs “and” to describe it, split the responsibility.
- If the class name says “manager,” ask what it actually manages and rename to that responsibility.
- If the file name says “utils,” prefer a feature-specific module name.
- If “base” grows behavior, reconsider whether it is an abstraction or a dumping ground.

Allowed exceptions:

- framework-required names
- small ABC base classes with one clear abstraction
- test-only helpers where the helper name stays local and obvious

## Review Checklist

Before accepting backend implementation changes, verify:

1. Are side effects explicit in class/function names and layer placement?
2. Are pure transformations free of IO, environment access, and shared-state mutation?
3. Is persistence introduced only after write/read contracts are clear?
4. Do new infrastructure adapters have focused success/failure tests?
5. Do class/file names reveal responsibility rather than hide it behind manager/processor/helper naming?
6. Are module-specific policies kept in module docs instead of being generalized into backend-wide rules?
