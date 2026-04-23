# 05. Type And Schema Rules

## Goal

Use dataclasses for internal domain/application shapes and Pydantic for IO boundaries, with purpose-driven boundary validation and explicit type modeling.

These are preferred defaults for backend design.
They are not meant as blind rules to follow without judgment.
If a case needs a different choice, the reason should be explicit.

## Dataclass Rule

### Adopt now

Prefer Python `dataclass` for internal backend models such as:

- domain entities
- value objects
- internal commands
- internal read models

Preferred options:

- `slots=True` when mutation/attribute growth is not needed
- `frozen=True` when the object should be immutable
- `kw_only=True` when it improves call-site clarity
- `field(default_factory=...)` for mutable defaults such as lists and dicts

Dataclasses are preferred here because they are lightweight Python objects and fit internal typed models without dragging IO validation concerns into the domain.

Additional guidance:

- use `frozen=True` for value objects and invariant-heavy internal shapes
- use `slots=True` for stable lightweight model objects
- use `kw_only=True` when positional construction would make call sites fragile or unclear

## Pydantic Rule

### Adopt now

Prefer Pydantic at IO boundaries:

- request bodies
- response payloads
- external input validation
- settings/config parsing when needed

Do not use Pydantic models as internal domain state by default unless there is a concrete validation/serialization reason.

Choose strictness by schema purpose, not by blanket rule.

Preferred boundary split:

- external write schemas → selective strictness
- internal machine-controlled contracts such as settings, bootstrap data, and internal stream payloads → strict-by-default
- external read schemas → shape clarity first, with selective strictness only where it materially improves the contract

Every Pydantic boundary schema should make intentional configuration choices for its role instead of relying on defaults by accident.

Boundary strictness can be applied at three levels:

- explicit strict field types (`StrictStr`, `StrictInt`, `StrictFloat`, `StrictBool`)
- per-field strict validation (`Field(strict=True)`) when needed
- model-level strict mode (`ConfigDict(strict=True)`) when the whole schema should reject coercion by default

## ConfigDict Intent Rule

### Adopt now

Each Pydantic boundary schema should choose only the `ConfigDict` options that match its role.

Common options to consider intentionally:

- `extra`
- `strict`
- `frozen`
- `from_attributes`
- `validate_assignment`
- `populate_by_name`
- `json_schema_extra`

Do not cargo-cult the same config block into every schema.
Minimal explicit config is acceptable when it clearly matches the contract.

Preferred baseline:

- start by deciding `extra`
- add strictness only where coercion rejection is part of the contract
- add schema examples for externally visible boundaries
- add the remaining options only when they improve correctness or clarity

## Strict Boundary Type Rule

### Adopt now

At Pydantic boundaries, prefer strict types when the contract should reject coercion:

- `StrictStr`
- `StrictInt`
- `StrictFloat`
- `StrictBool`

Use non-strict primitives when coercion is intentionally acceptable or when strictness would not improve the contract.

Prefer field-level strictness first when only a few values are coercion-sensitive.
Use model-level `strict=True` only when the whole schema should fail fast on coercion.

Notes:

- `StrictInt` should be used when boolean values must not slip through integer fields
- `StrictFloat` should be used when implicit `int -> float` acceptance is not desirable

## String Constraint Rule

### Adopt now

When string fields have shape requirements, prefer constrained annotated strings such as:

- `Annotated[StrictStr, StringConstraints(...)]`

Use explicit constraints for:

- `min_length`
- `max_length`
- `pattern`
- normalization or whitespace behavior where appropriate

Prefer this over older constrained-string constructor style when building reusable typed boundary fields.

If strictness is not needed for a specific boundary field, `Annotated[str, StringConstraints(...)]` is still acceptable.

## Specialized Pydantic Type Rule

### Adopt now

Prefer specialized field types over raw strings when they better express the contract:

- `EmailStr`
- `HttpUrl`
- `AnyUrl`
- `UUID4`
- `AwareDatetime`

This should be the default mindset for externally visible schemas.

Use `AwareDatetime` by default for externally visible timestamps unless the contract explicitly requires naive datetimes.

## Nullability Rule

### Adopt now

Do not make fields nullable by default.

Use `| None` only when the domain or API truly allows missing values.

Do not use `| None` as a convenience escape hatch for uncertain contracts or partially understood data.
If the field is nullable, the contract should clearly allow absence.


## Fallback and Absence Rule

### Adopt now

Do not hide missing data with implicit fallback expressions.

Preferred direction:

- Remove `| None` when callers must provide the value.
- Require explicit empty containers at call sites when empty is intended.
- Use `None` only when absence is part of the contract.
- Normalize optional external input only at boundaries, then pass non-null typed values internally.

Good direction:

```python
@dataclass(frozen=True, slots=True)
class HttpRequest:
    url: str
    query_params: dict[str, str]
    headers: dict[str, str]
    timeout_seconds: float | None


HttpRequest(
    url=source.url,
    query_params={},
    headers={},
    timeout_seconds=None,
)
```

In this example:

- `query_params={}` means an empty query string is intentional.
- `headers={}` means no extra headers is intentional.
- `timeout_seconds=None` is allowed only if “no explicit timeout” or “use upstream default” is part of the contract.

Allowed absence examples:

- fetch failed, so `raw_content is None`
- external source did not publish `published_at`
- optional query filter was not provided at an API boundary
- repository lookup found no row

Allowed boundary-normalization pattern:

```python
def normalize_query_params(
    query_params: dict[str, str] | None,
) -> dict[str, str]:
    return {} if query_params is None else query_params
```

Use this only when absence is part of the external/boundary contract. Do not carry `| None` deeper into application/domain objects just to repair it later.

Forbidden patterns:

```python
metadata = dict(row.metadata_json or {})
items = list(row.items_json or [])
headers = headers or {}
query_params = query_params or {}
timeout = timeout or 30
self._repo = repo or DefaultRepository()
```

Preferred alternatives:

```python
metadata = dict(row.metadata_json)
items = list(row.items_json)
timeout = 30 if timeout is None else timeout
```

Even better, make the contract non-nullable at the boundary:

```python
metadata_json: Mapped[dict[str, JSONValue]] = mapped_column(
    JSON,
    nullable=False,
    default=dict,
)
```

Dependency rule:

- dependencies must be explicitly injected
- do not instantiate fallback repositories, clients, clocks, or config objects inside constructors to make tests easier
- tests should pass explicit fakes instead

Allowed defaults:

- function parameter defaults when the value is truly part of the function contract
- dataclass `field(default_factory=...)`
- Pydantic `Field(default_factory=...)`
- ORM defaults that make database nullability explicit

Rule of thumb:

- if absence is meaningful, show it with `is None`
- if empty is meaningful, pass `{}` or `[]` explicitly at the call site
- if absence is not meaningful, make the type/schema non-nullable
- never use falsy fallback to erase the difference between missing, empty, zero, false, and invalid

## Default Value Rule

### Adopt now

Do not use Pydantic default values as convenience fallbacks by default.

Default values are allowed only when:

- the API or domain contract intentionally defines the omitted value
- the default is stable and non-secret
- the default does not hide missing required input
- the value is not something that should come from auth/session/runtime context

Bad direction:

- actor identity defaults such as `reviewer: str = "admin"`
- domain-significant status defaults that silently change behavior
- defaults added only to make tests or clients easier to satisfy

Good direction:

- explicit required field when caller must provide the value
- upper-layer injection when the runtime/auth context owns the value
- narrow internal machine contract defaults when the omitted value is truly part of the contract

## Type Modeling Rule

### Adopt now

Before using `Any` or broad `object`-based fallback shapes, prefer:

- `TypedDict`
- `ABC`
- `TypeAlias`
- `TypeVar` / `Generic`
- `object` only when a deliberately broad fallback is still the safest precise option

If `Any` or a broad `object`-based fallback is still unavoidable, document why.

Preferred justification format:

```python
# Any justified: <why TypedDict/ABC/TypeAlias/object is not enough here>
# Broad type justified: <why a broad object-based fallback is still necessary here>
```

Current repo guard reference:

- `<shared_root>/guardrails/check_broad_types.py`

Current guard behavior:

- checks `<backend_root>/`
- ignores tests
- fails when `Any` or broad `object`-based fallback types appear without justification

Allowed justification styles:

- inline marker above the specific line

Use `TypedDict` for explicit dictionary payload shapes that should stay typed without becoming Pydantic models.

For dictionary-like payloads, do not default to:

- `dict[str, object]`
- `dict[str, Any]`
- `Mapping[str, object]`
- `Mapping[str, Any]`

Prefer this order instead:

1. `TypedDict`
2. named `TypeAlias`
3. `ABC` when you own the contract and need a real explicit interface
4. broad dictionary typing only as a last resort with explicit justification

Allowed exception:

- genuinely open-ended evidence, telemetry, or operator-factor maps may stay as named `TypeAlias` map shapes when a fixed `TypedDict` would be artificial

The intent is not “never use `Any` or `object` under any circumstance.”
The intent is “avoid broad fallback types by default, and require a clear reason when they are necessary.”

## Type Organization Rule

### Adopt now

If a type grows long or repeats across files, extract it.

Suggested path:

- small case: `types.py`
- larger case: `types/{feature}_types.py`

Use `TypeAlias` for named reusable type shapes.

## Contract Rule

### Adopt now

Do not use `Protocol` in this backend.

Preferred rule:

- dictionary shapes → `TypedDict`
- owned explicit interfaces/ports → `ABC`
- reusable union/container shapes → `TypeAlias`

Why:

- `Protocol` is too lightweight for the level of explicitness we want
- owned contracts should be obvious and intentional
- dictionary payloads should be modeled as dictionary shapes, not pseudo-object contracts

`Protocol` should be treated as disallowed in this codebase.

## Attribute Access Rule

### Adopt now — hard ban

Do not use `getattr(...)` or `hasattr(...)` in backend application/domain/infrastructure/interface code.

`getattr(...)` and `hasattr(...)` hide attribute usage from search, weaken static analysis, and make refactors/debugging unsafe. If a shape is dynamic, model it explicitly instead of reading/checking it dynamically.

Use one of these alternatives:

- explicit attributes on dataclasses / ORM models / read models
- `TypedDict` key access for dictionary payloads
- `ABC` contracts with explicit methods or properties
- a small adapter/wrapper that exposes explicit methods for optional SDK behavior
- `hasattr(...)` is also banned for the same reason; prefer explicit contracts

If an upstream SDK exposes optional version-dependent methods, do **not** call them via `getattr(...)` or check them via `hasattr(...)` at the call site. Create a narrow compatibility adapter with explicit methods and tests around the version behavior.

Reason:

- `getattr(...)` / `hasattr(...)` hurt refactor safety
- they weaken static analysis
- they break reliable grep/reference tracing
- they make debugging and usage ownership harder
- they allow dynamic contracts to leak into core backend code

## Variable Annotation Rule

### Adopt now as preferred clarity rule

Prefer explicit variable annotations when they materially improve clarity, type safety, or maintenance.

Good cases:

- long-lived local state
- cached/shared module state
- complex dictionaries/lists/sets
- values produced through multi-step transformation
- values crossing boundary-like handoff points inside a function
- constants and thresholds (`Final[...]` when appropriate)

Examples:

- `payload: EventPayload = {...}`
- `event_map: dict[str, list[str]] = {...}`
- `_repo_instance: EventEngineRepository | None = None`
- `AI_RELEVANCE_THRESHOLD: Final[float] = 20.0`

For payload-like dictionaries, prefer this order:

1. `TypedDict`
2. named `TypeAlias`
3. `ABC` when you own an explicit object contract
4. broad `dict[str, object]` only as a last resort with justification

Do not force variable annotations mechanically for trivial one-line obvious locals such as:

- `count = len(items)`
- `slug = "openai"`
- `is_ready = status == "ready"`

The rule is:

- annotate when it adds clarity
- skip when the inferred type is already obvious and the annotation would be noise

## `json_schema_extra` Rule

### Adopt now

Externally visible boundary schemas must include at least one representative example payload through `json_schema_extra`.

This applies to public, admin, system, and other operator-visible request/response schemas.
Purely internal schemas may omit examples unless they are treated as externally consumed contracts.

## Google-style Docstring Rule

### Adopt now

공개 함수·클래스에는 반드시 Google-style docstring을 작성한다.

필수 포함 항목:

- 한 줄 요약 (함수가 **무엇**을 하는지)
- `Args:` — 각 파라미터의 의미, 단위, 제약 조건
- `Returns:` — 반환 타입과 의미
- `Raises:` — 발생 가능한 예외 (해당 시)

형식:

```python
def compute_triage(
    *,
    publish_eligibility_status: str,
    ai_relevance_score: float,
    source_quality_score: float,
    duplicate_risk_score: float,
    source_count: int,
    text_cleanliness_flags: Sequence[str],
) -> tuple[str, str]:
    """Triage 상태와 사유를 결정한다.

    Args:
        publish_eligibility_status: 발행 적격 상태 ("eligible" | "needs_review" | "blocked").
        ai_relevance_score: AI 관련성 점수 (0.0–100.0).
        source_quality_score: 소스 품질 점수 (0.0–100.0).
        duplicate_risk_score: 중복 위험 점수 (0.0–100.0).
        source_count: 독립 근거 소스 수.
        text_cleanliness_flags: 텍스트 품질 플래그 목록.

    Returns:
        (triage_status, triage_reason) 튜플.
    """
```

적용 범위:

- `application/` 레이어의 모든 공개 함수·클래스 메서드
- `domain/` 레이어의 정책 함수 (예: triage, eligibility)
- `infrastructure/` 레이어의 repository 공개 메서드
- `interface/router/` 의 endpoint 함수 (FastAPI docstring 겸용)

예외:

- `__init__`, `__repr__` 등 trivial dunder 메서드는 생략 가능
- private helper (`_`로 시작)는 복잡도가 높을 때만 작성


## Comment and Justification Rule

### Adopt now

주석은 코드가 이미 말하는 “무엇”을 반복하지 말고, 코드만으로 드러나지 않는 **왜**를 설명할 때만 작성한다.

허용/권장되는 주석:

- `Any`, broad `object`, `type: ignore`, lint noqa 등 예외적 패턴을 쓰는 이유. `getattr(...)`과 `hasattr(...)`은 금지한다.
- 외부 API/SDK/Redis/DB/브라우저 등 upstream 제약 때문에 선택한 우회 방식
- 정책상 의도적으로 보수적이거나 넓게 처리하는 분기
- 삭제하면 안 되는 경계 조건, 보안/권한/데이터 보존 이유
- 복잡한 정규식, parser rule, retry/backoff, idempotency, DLQ/stream 처리의 의도

피해야 할 주석:

- 함수명/변수명/한 줄 코드가 이미 설명하는 내용을 반복하는 주석
- 오래된 구현 배경을 사실처럼 남기는 주석
- TODO만 남기고 issue/context/소유자/조건을 적지 않는 주석
- 타입/계약을 주석으로만 설명하고 `TypedDict`, dataclass, Pydantic schema, ABC로 모델링하지 않는 방식

예외적 패턴의 justification은 해당 라인 바로 위에 둔다.

권장 형식:

```python
# Broad type justified: worker tests pass lightweight config stubs without full runtime config.
def coerce_collector_runtime_config(config: object) -> CollectorRuntimeConfig:
    ...

# Do not use getattr/hasattr for optional SDK behavior.
# Wrap version-dependent SDK calls behind an explicit adapter method instead.
await redis_durability_adapter.wait_for_replicas(replicas=1, timeout_ms=100)
```

TODO 주석은 임시 작업 표시로만 사용하고, 조건과 제거 기준을 함께 적는다.

```python
# TODO(collector-v0.2): replace rule-only parsing after source_entries fixtures exist.
```

Rule of thumb:

- public API/contract 설명은 docstring에 둔다.
- 예외적 구현 선택의 이유는 짧은 inline comment에 둔다.
- 동작 설명이 길어지면 코드/타입/함수 이름을 먼저 개선한다.

## Computation Style Rule

### Adopt now

수치 계산(scoring, analytics, 통계 집계)에는 **NumPy**를 우선 사용한다.

이유:

- 가중합, clip, round 등 반복 패턴을 벡터 연산으로 간결하게 표현
- 향후 배치 계산·대량 데이터 확장 시 성능 이점
- 코드베이스 전체에서 계산 스타일 일관성 유지

적용 대상:

- 가중합 계산 (예: impact scoring)
- 점수 정규화, clip, 구간 매핑
- Counter/ratio 기반 집계를 배열 연산으로 대체 가능한 경우
- analytics repository의 결과 가공

예시:

```python
import numpy as np

# Before (순수 Python)
total = (
    market * w.market_change
    + ecosystem * w.ecosystem_influence
    + technical * w.technical_significance
    + company * w.company_weight
    + trust * w.trust
)
total = min(max(round(total, 2), 0.0), 100.0)

# After (NumPy)
scores = np.array([market, ecosystem, technical, company, trust])
weights = np.array([w.market_change, w.ecosystem_influence,
                    w.technical_significance, w.company_weight, w.trust])
total = float(np.clip(scores @ weights, 0.0, 100.0).round(2))
```

예외:

- 단일 스칼라 비교 (`if score < threshold`)는 NumPy 불필요
- I/O 경계의 단순 변환은 plain Python 허용

## Practical Reference Note

These rules align with:

- Python dataclass guidance for lightweight typed data containers
- Pydantic v2 strict and specialized boundary validation patterns
- Google-style docstring conventions (PEP 257 + Google Python Style Guide)
- NumPy vectorized computation for numerical consistency and performance

In this repo, the architectural intent is:

- dataclass inside
- Pydantic at the edge
