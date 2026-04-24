# Event data format design

작성일: 2026-04-24
범위: Step 1 event generator stdout JSON Lines 계약, 이후 MQ raw event payload 계약

## 1. 목적

이번 데이터 포맷 설계의 목적은 과제 Step 1에서 생성되는 이벤트를 이후 단계의 MQ publish, 저장, 집계, 시각화로 자연스럽게 연결하는 것이다.

Step 1은 아직 DB나 MQ에 저장하지 않는다. 하지만 stdout JSON Lines 한 줄이 이후 MQ message body가 될 수 있어야 하므로, 지금부터 이벤트 한 줄이 어떤 의미를 갖는지 명확하게 잡아둔다.

최종 출력 형태는 아래 방향으로 결정했다.

```text
이벤트 1건 = JSON object 1개
stdout 1줄 = 이벤트 1건 = MQ message body 후보
전체 출력 = JSON Lines stream
```

예시:

```json
{"schema_version":"web_event.v1","event_id":"evt_7f3a9c1e2b4098ab76cd","event_type":"product_click","occurred_at":"2026-04-24T00:00:00.000Z","user_id":"user_013","traffic_phase":"normal","producer_id":"producer_local","page_path":"/products/prod_iphone_15","category_id":"cat_smartphone","product_id":"prod_iphone_15","amount":null,"currency":null,"error_code":null,"error_message":null}
```

## 2. 왜 JSON Lines인가

JSON Lines를 선택한 이유는 stream 처리와 다음 단계 확장이 쉽기 때문이다.

- event generator는 계속 이벤트를 생성하는 producer에 가깝다.
- 한 줄에 이벤트 1건이면 `stdout`, 파일, pipe, MQ payload로 옮기기 쉽다.
- 여러 이벤트를 큰 JSON 배열 하나로 묶으면 infinite mode에서 종료 전까지 완성된 JSON이 나오지 않는다.
- 한 줄씩 parse하면 consumer나 저장 단계에서 실패 이벤트만 분리하기 쉽다.

그래서 stdout은 이벤트 JSON Lines 전용으로 유지하고, 시작/종료/요약 로그는 stderr로 분리했다.

## 3. 왜 모든 이벤트가 같은 top-level field set을 가지는가

이벤트 타입마다 필요한 필드는 다르다.

예를 들어:

- `page_view`는 `page_path`가 중요하다.
- `purchase`는 `product_id`, `amount`, `currency`가 중요하다.
- `checkout_error`는 `error_code`, `error_message`가 중요하다.

하지만 출력 포맷은 모든 이벤트가 같은 top-level field set을 갖도록 설계했다.

```text
schema_version
event_id
event_type
occurred_at
user_id
traffic_phase
producer_id
page_path
category_id
product_id
amount
currency
error_code
error_message
```

이벤트에 해당하지 않는 값은 필드를 생략하지 않고 `null`로 둔다.

이렇게 한 이유:

- 다음 단계에서 PostgreSQL 컬럼으로 분리 저장하기 쉽다.
- JSON 전체를 통째로 저장하지 말라는 과제 요구사항과 잘 맞는다.
- 분석 쿼리에서 컬럼 존재 여부를 매번 걱정하지 않아도 된다.
- stdout sample을 봤을 때 어떤 필드가 전체 계약에 포함되는지 바로 알 수 있다.
- MQ consumer가 이벤트 타입별 parser를 따로 만들지 않아도 v1 payload를 검증할 수 있다.

## 4. schema_version 설계

`schema_version`은 MQ message body만 봐도 어떤 계약으로 해석해야 하는지 알 수 있게 하는 값이다.

예시:

```json
"schema_version": "web_event.v1"
```

이 필드를 넣은 이유:

- MQ에는 여러 producer나 여러 버전의 message가 섞일 수 있다.
- consumer가 payload version을 먼저 확인하고 validation할 수 있다.
- 나중에 `seller_id`, `listing_id`, nested `items` 같은 확장이 필요하면 `web_event.v2`로 분리할 수 있다.

broker topic이나 header에 version을 넣을 수도 있지만, message body만 파일로 저장하거나 샘플로 확인할 때도 계약을 알 수 있도록 payload 안에 포함한다.

## 5. event_id 설계

### 5.1 결정

`event_id`는 이벤트 한 건을 구분하는 **unique opaque string**으로 설계했다.

예시:

```json
"event_id": "evt_7f3a9c1e2b4098ab76cd"
```

### 5.2 왜 중복시키지 않는가

처음에는 같은 카테고리 클릭이나 같은 상품 클릭이 반복될 수 있으므로 `event_id`도 중복 가능하게 둘지 고민했다.

하지만 최종적으로는 `event_id`를 중복시키지 않기로 했다.

이유:

- `event_id`는 “무슨 행동인가”가 아니라 “이벤트 로그 한 건 자체”를 구분하는 값이다.
- 같은 사용자가 같은 상품을 두 번 클릭해도 이벤트는 두 번 발생한 것이다.
- 같은 상품/카테고리 반복은 `product_id`, `category_id`, `event_type` 반복으로 표현하는 것이 더 명확하다.
- 나중에 retry, 중복 전송, idempotency를 다룰 때 unique event id가 있으면 처리하기 쉽다.

즉, 반복 행동은 아래처럼 표현한다.

```json
{"event_id":"evt_a111","event_type":"product_click","product_id":"prod_iphone_15"}
{"event_id":"evt_b222","event_type":"product_click","product_id":"prod_iphone_15"}
```

두 이벤트는 같은 상품 클릭이지만, 서로 다른 이벤트 인스턴스다.

### 5.3 왜 number가 아니라 opaque string인가

number ID는 보기 쉽지만 순서나 규모를 추측하기 쉽다.

```json
"event_id": 4137
```

이보다 아래 형태가 이벤트 식별자로 더 적합하다고 판단했다.

```json
"event_id": "evt_7f3a9c1e2b4098ab76cd"
```

이 방식은 사람이 봤을 때 이벤트 ID임을 알 수 있고, 동시에 내부 순서나 개수를 강하게 노출하지 않는다.

## 6. product_id 설계

### 6.1 결정

`product_id`는 상품 분석용 **stable opaque product string**으로 설계했다.

예시:

```json
"product_id": "prod_iphone_15"
```

### 6.2 왜 중복 가능해야 하는가

`product_id`는 이벤트 한 건의 ID가 아니라 “어떤 상품에 대한 이벤트인가”를 나타내는 차원 값이다.

그래서 여러 이벤트에서 반복되는 것이 맞다.

```json
{"event_type":"product_click","product_id":"prod_iphone_15"}
{"event_type":"add_to_cart","product_id":"prod_iphone_15"}
{"event_type":"purchase","product_id":"prod_iphone_15"}
```

이렇게 반복되어야 상품별 클릭 수, 장바구니 수, 구매 수를 집계할 수 있다.

### 6.3 A사 iPhone과 B사 iPhone 문제

같은 iPhone을 A사와 B사가 모두 판매하는 상황은 `product_id` 하나만으로는 충분하지 않을 수 있다.

이때는 개념을 나눠야 한다.

```text
product_id = 제품 모델 또는 카탈로그 상품
seller_id  = 판매자
listing_id = 판매자가 올린 실제 판매 상품/오퍼
sku        = 재고/옵션 단위
```

예시:

```json
{
  "product_id": "prod_iphone_15",
  "seller_id": "seller_a",
  "listing_id": "listing_a_iphone_15_128_black",
  "sku": "A-IP15-128-BLK"
}
```

Step 1에서는 과제 범위를 단단하게 유지하기 위해 `seller_id`, `listing_id`, `sku`는 넣지 않았다. 대신 `product_id`는 같은 상품을 반복 집계할 수 있는 안정적인 상품 코드로 둔다.

향후 저장/분석 단계에서 marketplace 구조까지 확장하기로 하면 `seller_id`, `listing_id`, `sku`를 추가한다.

## 7. category_id 설계

`category_id`는 상품/카테고리 분석용 반복 가능한 차원 값으로 추가했다.

예시:

```json
"category_id": "cat_smartphone"
```

추가한 이유:

- 사용자는 상품뿐 아니라 카테고리도 탐색한다.
- 같은 카테고리를 여러 사람이 클릭하거나 조회할 수 있다.
- 카테고리별 관심도, 상품군별 전환율 같은 분석 질문을 만들 수 있다.
- `product_id`만 있으면 상품 단위 분석은 가능하지만, 상품군 단위 분석은 어렵다.

예를 들어 아래 두 이벤트는 서로 다른 상품이지만 같은 카테고리다.

```json
{"event_type":"product_click","category_id":"cat_smartphone","product_id":"prod_iphone_15"}
{"event_type":"product_click","category_id":"cat_smartphone","product_id":"prod_galaxy_s24"}
```

이렇게 하면 카테고리 단위 집계가 가능하다.

## 8. user_id 설계

`user_id`는 반복 가능한 사용자 분석 차원이다.

```json
"user_id": "user_050"
```

이 값은 unique event id가 아니라 분석 차원이다.

- `user_id`가 반복되어야 유저별 이벤트 수를 볼 수 있다.

Step 1에서는 실제 로그인/회원 DB가 없으므로 샘플 ID pool에서 생성한다.

`session_id`는 v1 payload에서 제외했다.

제외한 이유:

- 현재 generator는 실제 세션 journey를 보장하지 않는 랜덤 producer다.
- 세션 ID를 넣으면 “한 세션 안에서 funnel 순서가 보장되는가?”라는 추가 모델링 질문이 생긴다.
- 과제 코어인 이벤트 생성/MQ payload/저장/집계에는 `user_id`만으로도 충분하다.

나중에 세션 단위 path 분석을 추가할 때 `session_id`를 `web_event.v2` 후보로 다시 검토한다.

## 9. occurred_at 설계

`occurred_at`은 ISO-8601 UTC 문자열로 출력한다.

```json
"occurred_at": "2026-04-24T00:00:00.000Z"
```

결정 이유:

- 시간대별 이벤트 추이 분석에 바로 사용 가능하다.
- UTC 기준이면 저장/집계 단계에서 timezone 혼란을 줄일 수 있다.
- `--seed`, `--start-time`, traffic phase rate를 조합해 재현 가능한 시간 흐름을 만들 수 있다.

실제 현재 시간이 아니라 deterministic simulated clock을 사용한 이유는 테스트 재현성 때문이다.

## 10. traffic_phase 설계

`traffic_phase`는 `slow`, `normal`, `burst` 중 하나다.

```json
"traffic_phase": "normal"
```

이 필드를 넣은 이유:

- 이벤트가 항상 같은 속도로 발생하지 않는다는 것을 표현한다.
- 향후 MQ 도입 필요성을 설명할 수 있다.
- burst 시간대에 error나 checkout 문제가 늘어나는지 같은 분석 질문을 만들 수 있다.

Step 1에서는 MQ를 붙이지 않지만, traffic profile은 다음 단계의 MQ/consumer 설계 근거가 된다.

## 11. amount와 currency 설계

`amount`, `currency`는 `purchase` 이벤트에만 의미가 있다.

```json
"amount": 839.12
"currency": "USD"
```

다른 이벤트에서는 `null`로 둔다.

이렇게 한 이유:

- 구매 전환뿐 아니라 매출 집계도 가능하다.
- currency를 분리해두면 금액 필드의 의미가 명확하다.
- 모든 이벤트에 같은 field set을 유지할 수 있다.

## 12. error_code와 error_message 설계

`checkout_error`는 결제 과정에서 사용자가 실패를 만나는 흐름을 표현한다.

```json
"error_code": "PAYMENT_DECLINED"
"error_message": "Payment was declined by the card issuer."
```

이 필드를 둔 이유:

- 단순 error count뿐 아니라 error reason별 집계가 가능하다.
- 결제 오류율을 purchase와 비교할 수 있다.
- 이후 operational/status 이벤트를 추가할 때도 error schema를 확장하기 쉽다.

## 13. 대안과 기각 이유

### 13.1 event_id 중복 허용

기각했다.

반복 행동은 `event_id` 중복이 아니라 `event_type`, `product_id`, `category_id`, `user_id` 반복으로 표현하는 것이 더 정확하다.

### 13.2 product_id를 매 이벤트마다 새로 생성

기각했다.

상품 ID가 매번 새로 생기면 상품별 클릭/구매 집계가 불가능해진다. `product_id`는 반복 가능한 상품 차원이어야 한다.

### 13.3 number ID 사용

기각했다.

number는 간단하지만 의미가 노출되거나 순서가 있는 것처럼 보인다. 이벤트/상품 식별자는 opaque string이 더 안전하고 실제 분석 도구의 product id/sku 스타일에도 맞다.

### 13.4 이벤트 타입별로 서로 다른 JSON shape 사용

기각했다.

타입별 shape를 다르게 하면 출력은 깔끔해 보이지만, 저장 단계에서 컬럼 mapping과 nullability 판단이 복잡해진다.

### 13.5 nested `items` 배열 사용

보류했다.

GA4나 실제 ecommerce purchase 이벤트에서는 `items` 배열을 쓰는 경우가 많다. 하지만 Step 1은 단일 이벤트/단일 상품 흐름을 보여주는 것이 목적이므로 top-level `product_id`, `category_id`, `amount`로 충분하다.

장바구니에 여러 상품을 담는 복합 purchase를 다룰 때 `items` 배열을 검토한다.

## 14. 현재 Step 1 최종 계약

| 필드 | 타입 | 중복 여부 | 설명 |
|---|---|---:|---|
| `schema_version` | string | 중복 O | MQ/consumer가 해석할 payload 계약 버전. 현재 `web_event.v1` |
| `event_id` | string | 중복 X | 이벤트 한 건의 unique opaque id |
| `event_type` | string | 중복 O | 이벤트 종류 |
| `occurred_at` | string | 중복 가능 | ISO-8601 UTC 발생 시각 |
| `user_id` | string | 중복 O | 사용자 분석 차원 |
| `traffic_phase` | string | 중복 O | slow/normal/burst traffic profile |
| `producer_id` | string | 중복 O | 이벤트 생성 주체 |
| `page_path` | string/null | 중복 O | 페이지 경로 |
| `category_id` | string/null | 중복 O | 카테고리 분석 차원 |
| `product_id` | string/null | 중복 O | 상품 분석 차원 |
| `amount` | number/null | 중복 가능 | 구매 금액 |
| `currency` | string/null | 중복 O | 구매 통화 |
| `error_code` | string/null | 중복 O | 결제 오류 코드 |
| `error_message` | string/null | 중복 O | 결제 오류 설명 |

## 15. 참고한 기준

- [CloudEvents spec](https://github.com/cloudevents/spec/blob/main/cloudevents/spec.md)는 event `id`를 같은 source에서 발생한 event instance를 구분하는 값으로 본다.
- [CloudEvents primer](https://github.com/cloudevents/spec/blob/main/cloudevents/primer.md)는 `id`가 event source 기준으로 unique해야 한다는 방향을 설명한다.
- [Snowplow canonical event documentation](https://docs.snowplow.io/docs/fundamentals/canonical-event/)은 공통 event field 모델을 설명한다.
- [Snowplow Java tracker documentation](https://docs.snowplow.io/docs/sources/java-tracker/tracking-events/)은 tracked event payload의 `event_id`를 unique UUID string으로 둔다고 설명한다.
- [Segment ecommerce spec](https://www.twilio.com/docs/segment/connections/spec/ecommerce/v2)는 `product_id`를 상품 database identifier로 보고, `sku`와 분리 가능하다고 설명한다.
- [Google Analytics 4 ecommerce guide](https://developers.google.com/analytics/devguides/collection/ga4/ecommerce)는 `items` 배열 안에 `item_id`, `item_name`, `item_brand`, `item_category`, `item_variant` 같은 상품 차원 필드를 둔다.
- [Shopify marketplace product listing requirements](https://help.shopify.com/en/manual/online-sales-channels/marketplaces/marketplace-connect/products/requirements)는 GTIN/UPC/MPN/EAN 같은 unique product identifier 개념을 언급한다.

이번 과제에서는 위 기준을 단순화해 `event_id`는 unique event instance id, `product_id`/`category_id`는 반복 가능한 분석 차원으로 설계했다.
