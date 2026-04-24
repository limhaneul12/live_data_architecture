# MQ event payload contract

작성일: 2026-04-24
범위: event generator가 MQ에 publish할 raw event JSON body

## 1. 지금 먼저 볼 대상

DB 스키마보다 먼저 고정해야 할 대상은 MQ에 들어갈 **message body JSON**이다.

현재 event generator의 stdout JSON Lines 한 줄은 그대로 MQ message body가 될 수 있게 설계한다.

```text
event_generator stdout 1 line
  = raw event JSON object 1개
  = MQ message body 1개
```

즉 Step 1의 출력 계약이 Step 2 이후 MQ publish 계약의 출발점이다.

## 2. Payload 형태

MQ message body는 transport-neutral JSON object로 둔다.

예시:

```json
{
  "schema_version": "web_event.v1",
  "event_id": "evt_7f3a9c1e2b4098ab76cd",
  "event_type": "product_click",
  "occurred_at": "2026-04-24T00:00:00.000Z",
  "user_id": "user_013",
  "traffic_phase": "normal",
  "producer_id": "producer_local",
  "page_path": "/products/prod_iphone_15",
  "category_id": "cat_smartphone",
  "product_id": "prod_iphone_15",
  "amount": null,
  "currency": null,
  "error_code": null,
  "error_message": null
}
```

JSON Lines 파일/stdout에서는 위 object가 공백 없는 한 줄로 출력된다.

## 3. 왜 MQ envelope를 JSON 안에 넣지 않는가

MQ에는 broker마다 별도 metadata가 있다.

예를 들어 Kafka라면 topic, partition, offset, key가 있고 RabbitMQ라면 exchange, routing key, delivery tag가 있다.

그래서 payload JSON 안에는 broker metadata를 넣지 않는다.

```text
payload JSON에 포함하는 것:
- 서비스에서 발생한 event 자체
- event schema version
- 분석에 필요한 domain field

payload JSON에 포함하지 않는 것:
- topic
- partition
- offset
- delivery tag
- broker message id
- consumer retry count
```

이렇게 하면 나중에 Kafka, RabbitMQ, Redis Streams 중 무엇을 쓰더라도 payload contract를 유지할 수 있다.

## 4. MQ publish 시점의 권장 metadata

아직 MQ 종류를 고정하지 않았으므로 아래는 transport-neutral 권장값이다.

| 구분 | 권장값 | 이유 |
|---|---|---|
| message body | 이 문서의 JSON payload | MQ와 DB 사이에서 가장 중요한 계약 |
| content type | `application/json` | consumer가 parser를 명확히 선택 |
| schema version | body의 `schema_version` | message만 봐도 버전 확인 가능 |
| message id | 가능하면 `event_id` | retry/idempotency 추적에 유리 |
| routing key / topic 후보 | `web.events.raw.v1` | raw event stream임을 명확히 표현 |
| partition key 후보 | `user_id` | 사용자 단위 순서 보존이 필요할 때 사용 |

초기 구현에서는 broker-specific metadata보다 message body JSON을 먼저 단단히 고정한다.

## 5. Field 계약

| 필드 | 타입 | 필수 | 중복 여부 | 설명 |
|---|---|---:|---:|---|
| `schema_version` | string | O | O | payload 계약 버전. 현재 `web_event.v1` |
| `event_id` | string | O | X | 이벤트 한 건의 unique opaque id |
| `event_type` | string | O | O | `page_view`, `product_click`, `add_to_cart`, `purchase`, `checkout_error` |
| `occurred_at` | string | O | 가능 | ISO-8601 UTC 발생 시각 |
| `user_id` | string | O | O | 사용자 분석 차원 |
| `traffic_phase` | string | O | O | `slow`, `normal`, `burst` |
| `producer_id` | string | O | O | 이벤트 생성 주체 |
| `page_path` | string/null | O | O | 페이지 경로 |
| `category_id` | string/null | O | O | 카테고리 분석 차원 |
| `product_id` | string/null | O | O | 상품 분석 차원 |
| `amount` | number/null | O | 가능 | 구매 금액 |
| `currency` | string/null | O | O | 구매 통화 |
| `error_code` | string/null | O | O | 결제 오류 코드 |
| `error_message` | string/null | O | O | 결제 오류 설명 |

모든 필드는 항상 존재한다. 이벤트 타입에 해당하지 않는 값만 `null`로 둔다.

## 6. event_id와 MQ message id의 관계

`event_id`는 application-level id다.

MQ broker가 자체 message id를 만든다 하더라도, consumer와 DB 저장 단계에서는 `event_id`를 기준으로 idempotency를 잡는 것이 좋다.

```text
event_id
  -> 이 이벤트가 실제로 한 번 발생했다는 application id

broker message id / offset / delivery tag
  -> MQ 내부 전달/저장 위치를 나타내는 transport metadata
```

따라서 같은 MQ message가 retry로 두 번 소비되어도 DB에서는 `event_id` unique constraint로 중복 저장을 막을 수 있다.

## 7. product_id와 category_id는 반복 가능해야 한다

`product_id`, `category_id`는 message id가 아니라 분석 차원이다.

같은 상품이나 카테고리에 대해 여러 사용자가 여러 번 행동할 수 있으므로 반복되는 것이 맞다.

```json
{"schema_version":"web_event.v1","event_id":"evt_a111","event_type":"product_click","product_id":"prod_iphone_15","category_id":"cat_smartphone"}
{"schema_version":"web_event.v1","event_id":"evt_b222","event_type":"add_to_cart","product_id":"prod_iphone_15","category_id":"cat_smartphone"}
```

반복 행동은 `event_id` 중복이 아니라 dimension field 반복으로 표현한다.

## 8. 현재 의도적으로 제외한 것

MQ payload v1에서는 아래를 넣지 않는다.

- `seller_id`
- `listing_id`
- `sku`
- `session_id`
- `transaction_id`
- nested `items` array
- broker offset/partition/delivery metadata
- DB 저장 시각 `ingested_at`

이유는 Step 1의 목적이 단일 상품 중심의 event stream을 명확하게 만드는 것이기 때문이다.

`session_id`는 실제 세션 journey를 보장하는 generator로 확장할 때 의미가 커진다. 현재 v1은 단순 랜덤 producer이므로 user 단위 분석만 유지한다.

나중에 marketplace 구조, 세션 path 분석, 다중 상품 purchase를 다룰 때 v2에서 확장한다.

## 9. DB 스키마와의 관계

DB 스키마는 이 MQ payload를 받아서 컬럼으로 분리 저장하는 다음 단계다.

```text
MQ payload JSON field
  -> consumer validation
  -> PostgreSQL events table column
```

따라서 지금은 DB table부터 설계하지 않고, MQ에 들어갈 raw event JSON contract를 먼저 고정한다.
