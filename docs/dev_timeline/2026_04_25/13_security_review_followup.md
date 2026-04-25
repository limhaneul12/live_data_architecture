# 13. Security review follow-up

## 배경

SQL Lab이 사용자 입력 SQL을 받기 때문에 SQL Injection, read-only query abuse,
DB 권한 경계가 현재 구조에서 가장 중요한 보안 검토 지점이다.

## SQLAlchemy 공식 문서 기준 정리

SQLAlchemy는 `bindparam()` 또는 SQLAlchemy Core/ORM expression으로 만든 값 조건을
DBAPI bind parameter로 넘길 때 안전한 값 바인딩을 제공한다. 반대로 사용자 입력을
SQL 문자열에 직접 inline rendering 하거나, 검증되지 않은 raw SQL 문자열을
`text()`로 실행하는 것은 SQLAlchemy가 구조적으로 안전하게 만들어 주는 영역이 아니다.

따라서 현재 SQL Lab의 안전성은 아래 계층이 함께 작동해야 확보된다.

1. sqlglot AST validator로 허용 SQL shape 제한
2. generated view allowlist로 조회 relation 제한
3. SQLAlchemy bind parameter로 `row_limit` 같은 값만 바인딩
4. PostgreSQL transaction/runtime guardrail 적용
5. 별도 read-only DB role로 최종 권한 경계 보강

## 1번 조치: DB/Redis host publish 범위 축소

`docker-compose.yml`에서 Postgres와 Redis host port를 loopback에만 bind했다.

```yaml
ports:
  - "127.0.0.1:${POSTGRES_PORT:-15432}:5432"
  - "127.0.0.1:${REDIS_PORT:-16379}:6379"
```

과제 실행 편의성은 유지하되, 같은 네트워크의 외부 host에서 DB/Redis로 직접 접근하는
면적을 줄인다.

## 2번 방향: read-only DB role

아직 구현하지 않았지만 가장 권장되는 방향은 analytics SQL 실행용 DSN을 writer DSN과
분리하는 것이다.

- `DATABASE_DB_ADDRESS`: app writer/consumer용
- `ANALYTICS_DATABASE_DB_ADDRESS`: SQL Lab/Explore read-only용

read-only role은 generated view에만 `SELECT` 권한을 갖고, raw `events` table 직접
조회와 DDL/DML 권한은 갖지 않아야 한다.

## 3번 방향: SQL Lab 운영 경계

SQL Lab은 사람이 SQL을 직접 입력하는 기능이므로 일반 사용자 기능이라기보다
local/admin/debug surface에 가깝다. 과제에서는 노출해도 되지만, 운영형 구조로 간다면
별도 admin surface 또는 feature flag로 분리하는 것이 안전하다.

## 4번 방향: frontend proxy allowlist

Nginx가 없어도 Next.js API route 내부에서 `/analytics/datasets`, `/analytics/query`,
`/analytics/explore-query`만 통과시키는 allowlist를 둘 수 있다. Nginx/API gateway는
운영 단계의 추가 방어선이고, 이 과제 코드에서는 route-level allowlist가 더 가볍다.

## 5번 방향: ORM/Core와 생 SQL 역할 분리

- Chart Builder / Explore: SQLAlchemy Core로 SQL 생성한다.
- SQL Lab: 사용자가 입력한 SQL을 table 결과로 확인하는 별도 기능으로 둔다.

즉, 차트 생성 목적은 structured endpoint로 안전하게 가져가고, 생 SQL은 SQL Lab의
교육/검증용 표면으로 제한한다.

## 6번 제외

Redis password/TLS는 현재 과제 local compose 범위에서는 제외한다. 대신 host publish를
loopback으로 제한해 외부 접근면을 줄인다.
