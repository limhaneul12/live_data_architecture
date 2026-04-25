# Event generator

Step 1의 독립 이벤트 생성기입니다.

```text
python -m event_generator
  -> 랜덤 이벤트 생성
  -> stdout JSON Lines 출력
```

이 패키지는 이벤트 생성과 출력 sink 선택까지만 담당합니다. stdout JSON Lines 한 줄은 MQ message body로 그대로 사용할 수 있는 raw event payload이며, `--sink redis`를 선택하면 같은 payload를 Redis Streams에 publish합니다. PostgreSQL 저장과 FastAPI consumer lifecycle은 backend `event_analytics` bounded context가 담당합니다.

## 실행

기본 실행은 계속 이벤트를 생성하는 infinite mode입니다.

```bash
python -m event_generator
```

데모나 테스트에서는 `--max-events`와 `--no-sleep`을 사용합니다. `--seed`를
명시하면 같은 이벤트 순서를 재현하고, 생략하면 producer 재시작 시 같은
`event_id`를 replay하지 않도록 실행마다 seed를 자동 생성합니다.

```bash
python -m event_generator --max-events 10 --seed 20260424 --no-sleep
```

로컬에서 `python`이 3.12 환경을 가리키지 않는 경우에는 기존 backend uv 환경으로 실행할 수 있습니다.

```bash
UV_PROJECT_ENVIRONMENT=../.venv uv run --project backend python -m event_generator --max-events 10 --seed 20260424 --no-sleep
```

stdout에는 이벤트 JSON Lines만 출력합니다. 시작/종료 요약과 signal 메시지는 stderr로 출력합니다.

Redis Streams로 publish할 때는 `--sink redis`를 사용합니다.

```bash
STREAM_REDIS_URL=redis://localhost:6379/0 python -m event_generator --sink redis
```

Redis Stream key와 maxlen은 배포 설정이 아니라 generator 계약 상수로 고정합니다.
Redis Stream entry는 `payload` field에 `web_event.v1` JSON 문자열을 담습니다.
single Redis와 Redis Cluster를 모두 지원하며, cluster 모드에서는 `STREAM_REDIS_URL`에 콤마로 여러 startup node URL을 전달합니다.

## CLI 옵션

| 옵션 | 기본값 | 설명 |
|---|---:|---|
| `--seed` | 자동 생성 | 재현 가능한 이벤트/phase 생성이 필요할 때 명시하는 seed |
| `--max-events` | 없음 | 지정하지 않으면 infinite mode |
| `--producer-id` | `producer_local` | 이벤트에 기록되는 producer 식별자 |
| `--start-time` | `2026-04-24T00:00:00Z` | 이벤트 timestamp의 기준 날짜. 월/일은 고정하고 시간대만 랜덤 분포로 생성 |
| `--slow-rate` | `1` | slow phase events/sec |
| `--normal-rate` | `5` | normal phase events/sec |
| `--burst-rate` | `20` | burst phase events/sec |
| `--min-phase-seconds` | `10` | phase 최소 지속 시간 |
| `--max-phase-seconds` | `30` | phase 최대 지속 시간 |
| `--sink` | `stdout` | `stdout` 또는 `redis` |
| `--no-sleep` | `false` | 테스트용으로 실제 sleep 생략 |

## 이벤트 타입 설계

커머스 웹 서비스에서 사용자가 상품을 발견하고 구매하거나 결제 오류를 만나는 흐름을 표현하기 위해 5개의 이벤트를 사용합니다.

| 이벤트 타입 | 기본 비율 | 설계 이유 |
|---|---:|---|
| `page_view` | 45% | 전체 트래픽 규모와 인기 경로를 분석하기 위함 |
| `product_click` | 25% | 상품 관심도를 분석하기 위함 |
| `add_to_cart` | 15% | 구매 의도와 funnel 중간 전환을 분석하기 위함 |
| `purchase` | 8% | 구매 전환과 매출을 분석하기 위함 |
| `checkout_error` | 7% | 결제 이탈과 장애 원인을 분석하기 위함 |

구매나 오류 이벤트보다 페이지 조회와 클릭이 더 자주 발생하도록 비율을 잡았습니다. 이렇게 하면 이후 funnel 분석에서 `page_view -> product_click -> add_to_cart -> purchase` 흐름이 자연스럽게 보입니다.

## 발생 시각 설계

`occurred_at`은 `--start-time`의 월/일을 기준 날짜로 사용하되, 시/분/초/밀리초는 이벤트마다 랜덤하게 생성합니다. 과제의 핵심 분석은 일자별 장기 추세가 아니라 “시간대별 이벤트 추이”이므로 월/일까지 랜덤하게 넓히지 않고 하루 안의 hour-of-day 분포만 표현합니다.

시간대 분포는 `traffic_phase`와 연결합니다.

- `slow`: 0~6시, 22~23시 같은 저활동 시간대 비중을 높임
- `normal`: 오전~오후 업무/탐색 시간대에 넓게 분포
- `burst`: 점심/퇴근 후/저녁 피크 시간대 비중을 높임

이 방식은 실제 emit 순서와 event time이 반드시 오름차순이라는 뜻은 아닙니다. Stream은 producer가 발생시킨 순서대로 흘러가지만, analytics 관점의 `occurred_at`은 하루 안의 시간대 분포를 더 잘 보여주도록 샘플링됩니다.

## 필드 구조

모든 이벤트는 같은 top-level field set을 가집니다. 이벤트 타입에 필요 없는 값은 `null`로 둡니다.

| 필드 | 설명 |
|---|---|
| `schema_version` | MQ/consumer가 해석할 payload 계약 버전. 현재 `web_event.v1` |
| `event_id` | 이벤트 한 건을 구분하는 unique opaque string. 중복시키지 않음 |
| `event_type` | 이벤트 타입 |
| `occurred_at` | ISO-8601 UTC 발생 시각 |
| `user_id` | 샘플 사용자 ID |
| `traffic_phase` | `slow`, `normal`, `burst` 중 하나 |
| `producer_id` | producer 식별자 |
| `page_path` | page view 또는 상품 상세 경로 |
| `category_id` | 상품/카테고리 분석용 opaque category string. 여러 이벤트에서 반복 가능 |
| `product_id` | 상품 분석용 stable opaque product string. 같은 상품을 여러 번 클릭/담기할 수 있으므로 반복 가능 |
| `amount` | 구매 금액 |
| `currency` | 구매 통화 |
| `error_code` | checkout 오류 코드 |
| `error_message` | checkout 오류 설명 |

공통 field set을 유지하면 다음 단계에서 PostgreSQL 컬럼으로 분리 저장하기 쉽습니다.

## 출력 예시

```json
{"schema_version":"web_event.v1","event_id":"evt_7f3a9c1e2b4098ab76cd","event_type":"product_click","occurred_at":"2026-04-24T19:42:17.318Z","user_id":"user_013","traffic_phase":"burst","producer_id":"producer_local","page_path":"/products/prod_iphone_15","category_id":"cat_smartphone","product_id":"prod_iphone_15","amount":null,"currency":null,"error_code":null,"error_message":null}
```

## 종료

`--max-events`를 지정하면 해당 개수만 생성하고 종료합니다. Infinite mode에서는 Ctrl+C 또는 SIGTERM으로 graceful shutdown 할 수 있습니다.
