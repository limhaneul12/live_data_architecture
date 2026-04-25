# 2026-04-25 — Multi database extension note

브랜치: `fect/structured-explore-query`

## 1. 진행 배경

SQL Lab이 `sqlglot` AST 기반 검증을 사용하고 Chart Builder가 SQLAlchemy Core structured query를 사용하므로, PostgreSQL 외 다른 DB도 비슷한 방식으로 분석할 수 있는지 검토했다. 구현 자체는 가능하지만, 과제 v1에 넣으면 범위가 커지고 검증 비용이 커진다.

## 2. 반영 내용

- `docs/event_generator/database_support_extension.md` 신규 작성
- README Step3 설명에 PostgreSQL 단일 지원과 향후 adapter 확장 가능성 추가
- Step2/3 backend analytics design에 “다른 DB 지원 가능성” 섹션 추가
- remaining work의 의도적 제외 범위에 multi DB 지원 추가

## 3. 결정

현재 제출 범위에서는 PostgreSQL 단일 지원을 유지한다.

향후 확장하려면 `AnalyticsDatabaseDialect` 또는 유사 adapter가 필요하다.

```text
- sqlglot read dialect
- SQLAlchemy driver URL policy
- generated relation allowlist
- runtime read-only guard SQL
- statement/lock timeout strategy
- health check SQL
- value serialization policy
```

Chart Builder는 structured request 기반이라 repository adapter로 확장하기 쉽다. SQL Lab은 raw SQL을 받기 때문에 dialect별 AST 정책, catalog 접근 차단, function 차단, timeout/read-only guardrail을 다시 테스트해야 한다.

## 4. 검증 계획

- 문서 링크/문구 확인
- diff whitespace 검사
- 필요 시 docs 관련 pytest smoke 확인

## 5. 검증 결과

- `rg -n "database_support_extension|다른 DB 지원 가능성|multi DB|PostgreSQL 외" README.md docs/event_generator/step2_backend_analytics_design.md docs/remaining_work.md docs/dev_timeline/2026_04_25/12_multi_database_extension_note.md` → README/설계/remaining work 링크와 문구 확인
- `git diff --check` → 통과
- `make ci` → backend/event_generator format check, lint, pyrefly, guardrails, pytest 152개 통과
- `docker compose config -q` → 통과
