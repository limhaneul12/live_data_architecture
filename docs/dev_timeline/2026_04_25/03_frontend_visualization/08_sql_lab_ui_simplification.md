# 2026-04-25 — SQL Lab UI simplification

브랜치: `fect/structured-explore-query`

## 1. 진행 배경

사용자 리뷰에서 UI가 어렵고, 실제로 이동할 수 없는 상단 메뉴와 설명 카드가 혼란을 만든다는 지적이 있었다. 특히 SQL Lab에서 쿼리를 작성하려면 조회 가능한 table 이름과 column을 알아야 하는데, 기존 화면만으로는 그 정보를 파악하기 어려웠다.

## 2. 반영 내용

- 상단의 비동작 메뉴 `Dashboards / Charts / SQL Lab / Datasets` 제거
- 왼쪽 `Explore workflow` 설명 카드 제거
- 왼쪽 `Guardrails` 안내 카드 제거
- Chart Builder tab 명칭을 실제 기능에 맞게 `Chart Builder`로 변경
- Chart Builder control의 `Datasource` 표현을 `Table`로 변경
- SQL Lab 오른쪽 패널을 `Available tables`로 명확히 변경
- 각 table card에 column 이름과 column kind 표시
- 각 table card에 `Insert sample SELECT` 버튼 추가
- SQL Lab은 차트 생성 대신 raw query 결과 table을 확인하는 흐름 유지

## 3. 설계 의도

보안/구조 설명은 문서와 코드 guardrail에 남기고, 화면은 실제 사용자가 당장 수행해야 하는 흐름만 남긴다. SQL 사용자는 `Available tables`에서 조회 가능한 generated table과 column을 확인하고, `Insert sample SELECT`로 시작 쿼리를 넣은 뒤 필요에 맞게 수정할 수 있다. Chart Builder는 시각화 전용 흐름으로 남기되, 설명성 카드가 아니라 실제 실행 가능한 tab으로만 노출한다.

## 4. 검증 계획

- 제거 대상 UI 문구가 남아 있는지 검색한다.
- frontend lint/typecheck를 실행한다.
- repo diff whitespace를 검사한다.
- 다른 에이전트로 UI 요구사항 누락 여부를 read-only 검토한다.

## 5. 검증 결과

- `rg -n "Explore workflow|Guardrails|Dashboards|>Datasets<|Datasource|>Explore<|Explore query" frontend/app/components/analytics-workspace.tsx frontend/app/globals.css frontend/README.md` → 제거 대상 UI 문구 없음
- `make frontend-ci` → lint, typecheck, Next.js production build 통과
- `make ci` → backend/event_generator format check, lint, pyrefly, guardrails, pytest 146개 통과
- `git diff --check` → 통과
- `docker compose config -q` → 통과
- designer subagent read-only 검토 → 제거 대상 카드/상단 fake nav 제거 및 SQL Lab table/column 목록 반영 확인
