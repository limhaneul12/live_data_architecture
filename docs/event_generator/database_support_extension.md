# Database support extension note

작성일: 2026-04-25  
브랜치: `fect/structured-explore-query`

## 1. 결론

현재 과제 v1은 **PostgreSQL 단일 지원**으로 유지한다. 다만 현재 backend 구조는 “향후 다른 SQL database를 붙일 수 있는 지점”이 비교적 명확하다.

구현 가능성은 있다. 하지만 DB URL만 바꾸는 수준은 아니며, DB별 dialect / runtime guardrail / catalog / test matrix를 adapter로 분리해야 한다.

## 2. 현재 구조

현재 analytics 흐름은 두 종류로 나뉜다.

```text
Chart Builder
  -> /analytics/explore-query
  -> structured request(dataset, columns, order_by, row_limit)
  -> SQLAlchemy Core SELECT 생성
  -> PostgresAnalyticsQueryRepository

SQL Lab
  -> /analytics/query
  -> user raw SQL
  -> sqlglot PostgreSQL dialect parse
  -> AST policy validation
  -> generated view allowlist
  -> PostgreSQL read-only runtime guardrail
  -> SQLAlchemy text() 실행
```

이 중 Chart Builder는 raw SQL을 직접 받지 않기 때문에 DB 확장이 상대적으로 쉽다. SQL Lab은 사용자가 직접 SQL을 입력하므로 DB별 보안 정책과 실행 제약을 별도로 검증해야 한다.

## 3. 확장 가능성이 높은 부분

### 3.1 Chart Builder

Chart Builder는 아래 입력만 받는다.

```text
dataset
columns
order_by
order_direction
row_limit
```

따라서 DB별 구현은 repository/adapter에 가깝다.

예상 구조:

```text
AnalyticsQueryRepository
├── PostgresAnalyticsQueryRepository
├── MySqlAnalyticsQueryRepository       # future
├── DuckDbAnalyticsQueryRepository      # future
└── ClickHouseAnalyticsQueryRepository  # future
```

SQLAlchemy Core가 지원하는 범위에서는 같은 `ExploreQuery` domain contract를 유지할 수 있다. 다만 DB별 identifier quoting, type serialization, limit/order behavior는 테스트가 필요하다.

### 3.2 SQL Lab AST validation

SQL Lab은 `sqlglot` 기반 AST validation을 사용하므로, dialect 자체는 바꿀 수 있다.

예:

```python
sqlglot.parse(sql, read="postgres")
sqlglot.parse(sql, read="mysql")
sqlglot.parse(sql, read="duckdb")
```

하지만 dialect만 바꾸는 것으로는 충분하지 않다. DB별로 허용/차단해야 할 AST node, function surface, catalog 접근 방식이 달라진다.

## 4. DB별로 반드시 분리해야 하는 것

| 항목 | PostgreSQL 현재 방식 | 다른 DB 확장 시 필요 |
|---|---|---|
| SQL dialect | `read="postgres"` | DB별 `sqlglot` dialect |
| identifier policy | lowercase allowlist, schema-qualified relation 거부 | quoting/case-folding 규칙 재검증 |
| runtime read-only | `SET TRANSACTION READ ONLY` | DB별 read-only/permission 방식 |
| timeout | `statement_timeout`, `lock_timeout` | DB별 query timeout 방식 |
| schema scope | `search_path = public, pg_catalog` | DB별 schema/database 선택 정책 |
| health check | `SELECT 1` | 대부분 가능하지만 driver별 확인 필요 |
| generated views | PostgreSQL view/migration | DB별 view/materialized view/table 생성 방식 |
| conflict-ignore insert | `ON CONFLICT DO NOTHING` | MySQL `ON DUPLICATE`, DuckDB/ClickHouse 별도 검토 |
| datetime bucket | `date_trunc` 계열 migration/view | DB별 시간 함수 또는 generated table 전략 |

## 5. 제안 adapter contract

실제로 확장한다면 아래 정도의 adapter가 필요하다.

```python
@dataclass(frozen=True, slots=True)
class AnalyticsDatabaseDialect:
    name: str
    sqlglot_read_dialect: str
    sqlalchemy_driver_url_prefix: str
    allowed_relation_names: frozenset[str]
    runtime_guard_sql: tuple[str, ...]
    health_check_sql: str
```

실행 repository는 이 dialect 정보를 받아 다음 책임을 가진다.

```text
- SQL Lab raw SQL parse dialect 결정
- generated relation allowlist 결정
- DB session 시작 시 runtime guardrail 실행
- structured Explore query 실행
- row value JSON serialization
- health check SQL 실행
```

다만 이 adapter를 지금 바로 코드에 넣지는 않는다. 아직 지원 DB가 1개뿐이라 추상화를 먼저 만들면 실제 요구보다 계층이 앞서가고, 과제 제출 범위도 흐려진다.

## 6. 후보 DB별 현실성

| 후보 | 구현 난이도 | 과제 적합도 | 의견 |
|---|---:|---:|---|
| PostgreSQL | 낮음 | 높음 | 현재 v1 기준. 과제 요구사항에 충분함 |
| DuckDB | 중간 | 중간~높음 | 분석 DB 데모로 좋지만 app+DB compose 요구와는 결이 다름 |
| MySQL | 중간 | 중간 | 웹 서비스 DB 확장 예시로 좋지만 SQL Lab guardrail 재검증 필요 |
| ClickHouse | 높음 | 중간 | 이벤트 분석 DB로는 좋지만 인프라/DDL/driver 범위가 커짐 |
| SQLite | 중간 | 낮음~중간 | 간단하지만 concurrent consumer/analytics 설명력이 약함 |

## 7. v1에서 하지 않는 이유

- 과제 필수 요구사항에는 multi DB가 없다.
- 현재도 generator → Redis Streams → FastAPI consumer → PostgreSQL → SQL aggregation → Next.js visualization까지 범위가 충분히 크다.
- multi DB는 구현보다 검증 비용이 크다.
- SQL Lab raw SQL 지원은 DB별 보안 검증 없이는 “지원한다”고 말하기 어렵다.
- 지금은 Postgres 선택 이유를 명확히 설명하고, 확장 지점만 문서화하는 편이 제출 완성도가 높다.

## 8. 향후 실행 순서

나중에 실제로 구현한다면 아래 순서가 안전하다.

1. `AnalyticsDatabaseDialect` read-only adapter contract 작성
2. 현재 Postgres 구현을 adapter 기반으로 이동하되 behavior는 그대로 유지
3. Postgres regression test로 기존 정책 고정
4. 두 번째 DB 하나만 선택
   - 추천: DuckDB 또는 MySQL
5. DB별 generated view/schema 생성 전략 작성
6. SQL Lab validator를 dialect parameterized test로 확장
7. Docker Compose profile로 선택 DB를 띄우기
8. README에 “지원 DB”와 “실험 DB”를 분리 표기

## 9. 제출 문서에 넣을 문장

```text
현재 구현은 PostgreSQL을 1차 저장소와 분석 DB로 사용한다. SQL Lab의 검증은 sqlglot AST 기반이라 다른 SQL dialect로 확장할 수 있지만, DB별 read-only guardrail, timeout, identifier 정책, generated view catalog, schema migration이 필요하다. 따라서 과제 v1에서는 PostgreSQL 단일 지원으로 범위를 고정하고, 다른 DB 지원은 adapter 기반 향후 확장으로 남긴다.
```
