# Event generator implementation plan

작성일: 2026-04-24
브랜치: `fect/event-generator`
범위: Step 1 — 이벤트 생성 + stdout 출력

상세 planning artifacts:

```text
.omx/plans/prd-event-generator-step1.md
.omx/plans/test-spec-event-generator-step1.md
.omx/plans/implementation-plan-event-generator-step1.md
```

## 1. 이번 구현의 목표

과제 Step 1 요구사항을 만족하는 독립 event generator를 만든다.

```text
python -m event_generator
  -> 랜덤 이벤트 생성
  -> stdout JSON Lines 출력
```

이번 단계는 **이벤트를 생성하고 stdout으로 내보내는 것까지만** 한다. 다만 stdout JSON Lines 한 줄은 이후 MQ message body로 그대로 사용할 수 있는 raw event payload 계약으로 본다. 저장, 실제 MQ publish, FastAPI, Docker, 시각화는 다음 단계다.

## 2. 하지 않는 것

- MQ publish
- FastAPI 전송
- PostgreSQL 저장
- consumer 구현
- Docker Compose 연결
- SQL 집계/시각화
- 고부하 스트레스 테스트

## 3. 확정 이벤트 타입

```text
page_view        45%
product_click    25%
add_to_cart       15%
purchase           8%
checkout_error     7%
```

설계 의도:

- `page_view`: 트래픽 규모와 인기 경로를 본다.
- `product_click`: 상품 관심도를 본다.
- `add_to_cart`: 구매 의도와 funnel 중간 전환을 본다.
- `purchase`: 구매 전환과 매출을 본다.
- `checkout_error`: 결제 이탈과 장애 원인을 본다.

## 4. 출력 필드

모든 이벤트는 같은 top-level field set을 가진다. 필요 없는 값은 `null`로 둔다.

```text
schema_version  # 현재 web_event.v1, MQ/consumer payload 계약 버전
event_id  # unique opaque string, 중복 없음
event_type
occurred_at
user_id
traffic_phase
producer_id
page_path
category_id  # stable opaque category string, 반복 가능
product_id  # stable opaque product string, 반복 가능
amount
currency
error_code
error_message
```

이렇게 맞추면 다음 단계에서 MQ message body로 publish하고, 이후 PostgreSQL column schema로 옮기기 쉽다.

## 5. CLI 계약

기본 실행:

```bash
python -m event_generator
```

데모/테스트 실행:

```bash
python -m event_generator --max-events 100 --seed 20260424 --no-sleep
```

주요 옵션:

| 옵션 | 기본값 | 설명 |
|---|---:|---|
| `--seed` | 자동 생성 | 재현 가능한 이벤트/phase 생성이 필요할 때 명시 |
| `--max-events` | 없음 | 지정하지 않으면 infinite mode |
| `--producer-id` | `producer_local` | producer 식별자 |
| `--start-time` | `2026-04-24T00:00:00Z` | deterministic event clock 시작 시각 |
| `--slow-rate` | `1` | slow phase events/sec |
| `--normal-rate` | `5` | normal phase events/sec |
| `--burst-rate` | `20` | burst phase events/sec |
| `--min-phase-seconds` | `10` | phase 최소 지속 시간 |
| `--max-phase-seconds` | `30` | phase 최대 지속 시간 |
| `--no-sleep` | `false` | 테스트용으로 sleep 생략 |

stdout은 이벤트 JSON Lines 전용이다. phase 변경, progress, 종료 summary는 stderr에만 출력한다.

## 6. 예상 파일 구조

```text
event_generator/
  __init__.py
  __main__.py
  cli.py
  models.py
  generator.py
  traffic_profile.py
  serialization.py
  README.md
  tests/
    test_cli.py
    test_generator.py
    test_serialization.py
    test_traffic_profile.py
```

추가로 root package가 quality gate에서 빠지지 않도록 `Makefile`, root `pyproject.toml`, `backend/pyproject.toml` 조정을 포함한다.

## 7. 구현 순서

1. Package skeleton 생성.
2. Event model과 JSON Lines serialization 구현.
3. Seed 기반 event generator 구현.
4. slow/normal/burst traffic profile 구현.
5. CLI, stdout/stderr, graceful shutdown 구현.
6. Unit/CLI tests 작성.
7. Makefile/pyproject quality gate에 `event_generator/` 포함.
8. `event_generator/README.md` 작성.

## 8. 완료 조건

- `python -m event_generator --max-events 10 --seed 20260424 --no-sleep`가 실행된다.
- stdout에 정확히 10개의 JSON line이 출력된다.
- 각 JSON line은 `schema_version=web_event.v1`을 포함하며 이후 MQ message body로 사용할 수 있다.
- 같은 seed/start-time/max-events/no-sleep 조합은 같은 stdout을 만든다.
- `event_id`는 unique opaque string이며 중복시키지 않는다.
- `product_id`와 `category_id`는 분석 대상 식별자이므로 여러 이벤트에서 반복 가능하다.
- 이벤트 타입은 확정된 5개 중 하나다.
- 충분한 sample에서는 5개 이벤트 타입이 모두 등장한다.
- `purchase`에는 `category_id`, `product_id`, `amount`, `currency`가 있다.
- `checkout_error`에는 `error_code`, `error_message`가 있다.
- 기본 실행은 infinite mode이고 SIGINT/SIGTERM으로 graceful shutdown 된다.
- README에 이벤트 설계 이유와 실행법이 있다.
- MQ/FastAPI/PostgreSQL 코드는 Step 1에 포함하지 않는다.

## 9. 다음 구현 착수 기준

이 문서와 `.omx/plans/*event-generator-step1.md`를 기준으로 바로 구현을 시작할 수 있다. 다음 단계에서는 먼저 skeleton과 테스트 구조를 잡고, 이후 generator core를 테스트로 고정한다.
