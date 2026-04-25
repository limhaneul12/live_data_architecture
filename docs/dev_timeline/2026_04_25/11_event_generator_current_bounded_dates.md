# 2026-04-25 — Event generator current-bounded dates

브랜치: `fect/structured-explore-query`

## 1. 진행 배경

사용자 리뷰에서 이벤트 날짜를 특정 고정일로 두기보다는 “현재 시각 기준 과거/현재는 가능하지만 미래는 안 된다”는 정책이 더 맞다는 피드백이 있었다. 이전 변경은 hour-of-day 분포를 만들기 위해 날짜를 `--start-time` 기준으로 고정했지만, 이 방식은 demo 날짜가 코드에 고정되어 보일 수 있다.

## 2. 반영 내용

- `EventGeneratorConfig.start_time` 기본값을 하드코딩 날짜에서 실행 시점 기준 전날 00:00 UTC로 변경
- `--start-time` CLI 기본값을 제거하고, 생략 시 dynamic default를 사용
- `--start-time`이 현재 reference time보다 미래이면 generator 생성 단계에서 거부
- 오늘 날짜를 `--start-time`으로 지정한 경우 `occurred_at`이 현재 시각을 넘지 않도록 hour/min/sec/ms 범위를 제한
- 과거 날짜를 지정한 경우 해당 시작 시각 이후의 hour-of-day 분포를 유지
- 테스트에서는 `reference_time`을 주입해 현재 시간 의존성을 고정

## 3. 설계 의도

기본값을 현재 UTC 기준 “전날 00:00”으로 둔 이유는 다음과 같다.

- 하루 전체 0~23시 시간대 분포를 보여줄 수 있음
- 기본 실행에서 미래 timestamp가 생성되지 않음
- 특정 날짜를 코드에 하드코딩하지 않음
- 사용자가 원하면 `--start-time`으로 과거 날짜를 명시할 수 있음

`occurred_at`은 analytics event time이므로 stream emit 순서와 반드시 오름차순일 필요는 없다. 다만 event time 자체는 현재 reference time을 넘지 않게 제한한다.

## 4. 검증 계획

- event_generator ruff format/check
- event_generator tests
- 미래 `--start-time` CLI 거부 확인
- 기본 CLI sample이 현재 기준 전날 날짜를 쓰는지 확인
- 전체 CI
- diff whitespace / compose config 검증

## 5. 검증 결과

- `UV_PROJECT_ENVIRONMENT=../.venv uv run --project backend ruff format --config backend/pyproject.toml event_generator event_generator/tests` → 통과
- `UV_PROJECT_ENVIRONMENT=../.venv uv run --project backend ruff check --config backend/pyproject.toml event_generator event_generator/tests` → 통과
- `UV_PROJECT_ENVIRONMENT=../.venv uv run --project backend python -m pytest event_generator/tests` → 28 passed
- `PYTHONPATH=. UV_PROJECT_ENVIRONMENT=../.venv uv run --project backend python -m event_generator --max-events 3 --seed 20260424 --no-sleep` → 현재 UTC 기준 전날 날짜(`2026-04-24`)와 다양한 시간대 출력 확인
- `PYTHONPATH=. UV_PROJECT_ENVIRONMENT=../.venv uv run --project backend python -m event_generator --max-events 1 --seed 20260424 --start-time 2999-01-01T00:00:00Z --no-sleep` → `start time must not be in the future`로 거부 확인
- `make ci` → backend/event_generator format check, lint, pyrefly, guardrails, pytest 152개 통과
- `git diff --check` → 통과
- `docker compose config -q` → 통과
