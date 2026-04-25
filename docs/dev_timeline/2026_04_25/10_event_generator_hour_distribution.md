# 2026-04-25 — Event generator hour-of-day distribution

브랜치: `fect/structured-explore-query`

## 1. 진행 배경

사용자 리뷰에서 이벤트 생성 시 월/일까지 랜덤하게 넓히기보다는, 하루 안에서 시간대(hour-of-day)만 랜덤 분포로 표현하고 싶다는 요구가 있었다. 과제 분석 항목에도 “시간대별 이벤트 추이”가 있으므로, 장기 날짜 분포보다 하루 안의 시간대 분포가 더 직접적인 설명력을 가진다.

## 2. 반영 내용

- `occurred_at`의 월/일은 `--start-time`의 UTC 기준 날짜로 고정
- 시/분/초/밀리초는 이벤트마다 seed 기반으로 랜덤 샘플링
- `traffic_phase`별 hour weight를 분리
  - `slow`: 야간/새벽/늦은 밤 비중 높음
  - `normal`: 오전~오후 전반에 넓게 분포
  - `burst`: 점심/퇴근 후/저녁 피크 비중 높음
- 기존 deterministic seed 재현성은 유지
- CLI `--start-time`은 “첫 이벤트의 정확한 timestamp”가 아니라 “event time 기준 날짜” 역할로 문서화

## 3. 설계 의도

Stream emit 순서는 producer가 이벤트를 내보낸 순서이고, `occurred_at`은 analytics용 event time이다. 따라서 `occurred_at`이 반드시 오름차순일 필요는 없다고 판단했다. 대신 generated data가 시간대별 집계에서 더 의미 있는 분포를 갖도록 하루 안의 hour-of-day만 샘플링한다.

월/일까지 랜덤화하지 않은 이유는 다음과 같다.

- 과제의 핵심 범위가 작고, 장기 시계열까지 만들면 설명/검증 범위가 커짐
- hourly aggregation을 보여주기에는 하루 기준 분포가 충분함
- Docker demo에서 seed를 고정했을 때 결과를 이해하기 쉬움

## 4. 검증 계획

- event_generator lint
- event_generator tests
- 전체 backend/event_generator CI
- sample CLI 출력 확인
- README 문서 반영 확인

## 5. 검증 결과

- `UV_PROJECT_ENVIRONMENT=../.venv uv run --project backend ruff format --config backend/pyproject.toml event_generator event_generator/tests` → 14 files unchanged
- `UV_PROJECT_ENVIRONMENT=../.venv uv run --project backend ruff check --config backend/pyproject.toml event_generator event_generator/tests` → 통과
- `UV_PROJECT_ENVIRONMENT=../.venv uv run --project backend python -m pytest event_generator/tests` → 25 passed
- `PYTHONPATH=. UV_PROJECT_ENVIRONMENT=../.venv uv run --project backend python -m event_generator --max-events 10 --seed 20260424 --no-sleep` → `2026-04-24` 날짜 고정, 09/10/11/14/16/18/19/23시 등 다양한 시간대 출력 확인
- `make ci` → backend/event_generator format check, lint, pyrefly, guardrails, pytest 149개 통과
- `git diff --check` → 통과
- `docker compose config -q` → 통과
