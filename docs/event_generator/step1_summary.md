# Step 1 summary — event generator

작성일: 2026-04-25
범위: 과제 Step 1 — 웹 서비스 이벤트 랜덤 생성기

## 1. 과제 요구사항 대응

과제 Step 1 요구사항은 아래와 같다.

```text
Python, Go, Java 중 편한 언어를 선택하여 웹 서비스에서 발생할 수 있는
이벤트를 랜덤하게 생성하는 스크립트를 작성하세요.

- 이벤트 타입은 2가지 이상 포함
- 구현 방식, 필드 구성, 생성 건수는 자유
- README에 어떤 이벤트를 왜 그렇게 설계했는지 설명
```

현재 구현은 Python 기반 독립 producer package로 정리했다.

```text
event_generator/
  __main__.py
  cli.py
  constants.py
  generator.py
  models.py
  serialization.py
  sinks.py
  traffic_profile.py
  README.md
```

## 2. 실행 방법

기본 실행은 계속 이벤트를 생성하는 infinite mode다.

```bash
python -m event_generator
```

데모/테스트용으로 생성 건수를 제한할 수 있다.

```bash
python -m event_generator --max-events 10 --seed 20260424 --no-sleep
```

backend uv 환경으로도 실행 가능하다.

```bash
UV_PROJECT_ENVIRONMENT=../.venv uv run --project backend \
  python -m event_generator --max-events 10 --seed 20260424 --no-sleep
```

## 3. 이벤트 타입

커머스 웹 서비스에서 사용자의 탐색부터 구매/결제 실패까지 이어지는 funnel을
표현하기 위해 5개 이벤트를 사용한다.

| 이벤트 타입 | 기본 비율 | 설계 이유 |
|---|---:|---|
| `page_view` | 45% | 전체 트래픽 규모와 인기 페이지를 보기 위함 |
| `product_click` | 25% | 상품 관심도를 보기 위함 |
| `add_to_cart` | 15% | 구매 의도와 funnel 중간 전환을 보기 위함 |
| `purchase` | 8% | 구매 전환과 매출을 보기 위함 |
| `checkout_error` | 7% | 결제 이탈과 오류 원인을 보기 위함 |

이 비율은 실제 서비스에서 조회/클릭이 구매보다 더 자주 발생한다는 점을 단순화한
것이다. 이후 분석 단계에서 이벤트 타입별 count, funnel 전환율, 오류 비율 같은
질문으로 바로 이어진다.

## 4. 출력 형식

stdout은 이벤트 JSON Lines 전용이다.

```text
stdout 1줄 = 이벤트 1건 = 이후 MQ message body 후보 1건
```

시작/종료/summary 로그는 stderr로 분리한다. 이렇게 하면 stdout을 파일, pipe,
Redis Streams publish, 다른 MQ publish로 연결하기 쉽다.

예시:

```json
{"schema_version":"web_event.v1","event_id":"evt_7f3a9c1e2b4098ab76cd","event_type":"product_click","occurred_at":"2026-04-24T00:00:00.000Z","user_id":"user_013","traffic_phase":"normal","producer_id":"producer_local","page_path":"/products/prod_iphone_15","category_id":"cat_smartphone","product_id":"prod_iphone_15","amount":null,"currency":null,"error_code":null,"error_message":null}
```

## 5. 필드 구성

모든 이벤트는 같은 top-level field set을 가진다. 이벤트 타입에 해당하지 않는 값은
필드를 생략하지 않고 `null`로 둔다.

| 필드 | 타입 | 설명 |
|---|---|---|
| `schema_version` | string | payload 계약 버전. 현재 `web_event.v1` |
| `event_id` | string | 이벤트 한 건의 unique opaque id |
| `event_type` | string | 이벤트 타입 |
| `occurred_at` | string | ISO-8601 UTC 발생 시각 |
| `user_id` | string | 사용자 분석 차원 |
| `traffic_phase` | string | `slow`, `normal`, `burst` |
| `producer_id` | string | 이벤트 생성 주체 |
| `page_path` | string/null | 페이지 경로 |
| `category_id` | string/null | 카테고리 분석 차원 |
| `product_id` | string/null | 상품 분석 차원 |
| `amount` | number/null | 구매 금액 |
| `currency` | string/null | 구매 통화 |
| `error_code` | string/null | 결제 오류 코드 |
| `error_message` | string/null | 결제 오류 설명 |

## 6. ID 정책

- `event_id`: 이벤트 인스턴스 식별자이므로 중복시키지 않는다.
- `product_id`: 상품 분석 차원이므로 여러 이벤트에서 반복 가능하다.
- `category_id`: 카테고리 분석 차원이므로 여러 이벤트에서 반복 가능하다.
- `user_id`: 사용자 분석 차원이므로 여러 이벤트에서 반복 가능하다.

반복 행동은 `event_id` 중복이 아니라 `event_type`, `product_id`,
`category_id`, `user_id`의 반복으로 표현한다.

## 7. v1에서 제외한 필드

아래 필드는 Step 1 v1에서 제외했다.

| 제외 필드 | 제외 이유 |
|---|---|
| `session_id` | 현재 generator는 실제 세션 journey 순서를 보장하지 않는 랜덤 producer이기 때문 |
| `seller_id` | marketplace seller 분석은 Step 1 범위를 넘기 때문 |
| `listing_id` | 같은 상품의 판매자별 listing 모델링이 아직 필요하지 않기 때문 |
| `sku` | 옵션/재고 단위 분석은 v1 단일 상품 흐름보다 복잡하기 때문 |
| `transaction_id` | 결제 transaction 모델을 아직 도입하지 않았기 때문 |
| nested `items` | v1은 단일 이벤트/단일 상품 중심이라 top-level field로 충분하기 때문 |

## 8. 검증 기준

Step 1은 아래 테스트와 quality gate로 보호한다.

```text
event_generator/tests/test_cli.py
event_generator/tests/test_generator.py
event_generator/tests/test_serialization.py
event_generator/tests/test_sinks.py
event_generator/tests/test_traffic_profile.py
```

검증하는 것:

- `--max-events` 지정 시 정확한 줄 수 출력
- 같은 seed 조합의 재현성
- stdout/stderr 분리
- JSON Lines serialization field set 유지
- 이벤트 타입별 필수/null 필드 규칙
- 기본 infinite mode와 graceful shutdown

전체 검증은 아래 명령으로 수행한다.

```bash
make ci
```

## 9. 관련 문서

- `event_generator/README.md`
- `docs/event_generator/event_generator_implementation_plan.md`
- `docs/event_generator/event_data_format_design.md`
- `docs/event_generator/mq_event_payload_contract.md`
- `docs/event_generator/event_generator_design.md`
