# 2026-04-25 — SQL Lab table-first UI follow-up

브랜치: `fect/structured-explore-query`

## 1. 진행 배경

사용자 리뷰에서 SQL Lab 사용자가 실제 table name을 바로 알아야 하며, 사용하지 않는 `Saved queries`가 화면을 복잡하게 만든다는 피드백이 있었다. Chart Builder에서도 Sort by row의 칸 폭이 서로 달라 보이고, Chart preview의 긴 이름이 카드 밖으로 넘치는 문제가 있었다.

## 2. 반영 내용

- `Saved queries` sidebar 제거
- frontend 초기 metadata 로딩에서 preset query fetch 제거
- Chart Builder의 table select와 chart title에서 human label 대신 실제 table name 표시
- SQL Lab `Available tables` 카드의 대표 이름을 실제 table name으로 표시
- Chart Builder `Sort by / Direction / Row limit` control을 같은 폭 grid로 정렬
- Chart preview header, legend, metric card, caption에서 긴 이름이 박스 밖으로 나가지 않도록 wrapping/overflow 방어 추가
- SQL Lab manual SQL의 allowlisted relation 매칭이 대소문자를 구분하지 않는 현재 동작을 regression test로 고정

## 3. SQL AST / 다른 DB 연결 검토

현재 manual SQL은 `sqlglot`으로 PostgreSQL dialect 기준 AST를 만들고, root SELECT / 단일 statement / allowlisted generated table / function, join, subquery 차단 등을 검사한다. 따라서 “AST 기반 정책” 자체는 다른 DB에도 재사용할 수 있지만, 그대로 완전 이식된다고 보면 안 된다.

다른 DB를 붙일 때 필요한 변경점은 아래와 같다.

- `sqlglot.parse(..., read="postgres")`의 dialect를 DB별로 분기
- DB별 identifier quoting / case folding 차이 검증
- DB별 LIMIT, datetime, numeric type serialization 검증
- repository runtime guardrail 교체
  - 현재는 PostgreSQL의 `SET TRANSACTION READ ONLY`, `statement_timeout`, `lock_timeout`, `search_path`에 의존
- generated table/view catalog를 DB별 schema와 맞춤
- SQLAlchemy Core 기반 Chart Builder는 DB adapter를 바꾸면 비교적 이식 가능하지만, manual raw SQL 실행부는 DB별 정책 테스트가 반드시 필요

## 4. 검증 계획

- frontend lint/typecheck/build
- query policy case-insensitive relation test
- 전체 backend/event_generator CI
- diff whitespace check
- docker compose config check

## 5. 검증 결과

- `rg -n "Saved queries|saved-query|fetchPresets|activePreset|preset SQL|sidebar|dataset\.label|<code>\{dataset\.name\}" frontend/app/components/analytics-workspace.tsx frontend/app/globals.css frontend/README.md` → 제거 대상 문구/코드 없음
- `UV_PROJECT_ENVIRONMENT=../.venv uv run --project backend python -m pytest backend/tests/event_analytics/test_query_policy.py` → 35 passed
- `make frontend-ci` → lint, typecheck, Next.js production build 통과
- `make ci` → backend/event_generator format check, lint, pyrefly, guardrails, pytest 147개 통과
- `git diff --check` → 통과
- `docker compose config -q` → 통과
