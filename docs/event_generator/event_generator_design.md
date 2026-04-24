# Event generator design

작성일: 2026-04-24
브랜치: `fect/event-generator`
요청 브랜치명: `fect://event-generator`

> `fect://event-generator`는 Git branch 이름으로 사용할 수 없다.
> `:`와 `//`가 refname 규칙에 맞지 않기 때문에, 가장 가까운 안전한 이름인
> `fect/event-generator`로 브랜치를 만들었다.

## 1. 현재까지 정리된 큰 방향

이번 과제는 단순히 랜덤 JSON 파일을 만드는 것이 아니라, 웹 서비스에서 발생하는
이벤트가 분석 시스템으로 흘러가고, 그 결과를 SQL과 차트로 확인하는 작은 이벤트
분석 스택을 만드는 방향으로 정리되었다.

현재 합의된 큰 스택은 아래와 같다.

```text
Next.js(TypeScript) frontend
        |
        v
FastAPI backend
        |
        v
PostgreSQL
```

그리고 분석 UI는 Superset을 그대로 붙이는 것이 아니라, Superset의 핵심 사용감을
작게 참고한다.

- 테이블/view 선택
- SQL 입력
- 실행 버튼
- 결과 테이블
- 차트 preview

## 2. 현재 계획 문서 위치

지금까지의 deep-interview / consensus planning 산출물은 아래에 있다.

```text
.omx/specs/deep-interview-event-generator-assignment.md
.omx/plans/prd-event-generator-assignment.md
.omx/plans/test-spec-event-generator-assignment.md
```

이 문서는 위 산출물을 바탕으로, 먼저 **event generator 자체**를 어떻게 설계할지
정리한 문서다.

## 3. 아직 남은 중요한 결정

이벤트 생성 자체보다 더 중요한 질문이 하나 남아 있다.

```text
생성된 이벤트를 어디로, 어떤 방식으로 전송할 것인가?
```

후보는 크게 세 가지다. 최신 방향은 **MQ를 염두에 두되, 먼저 MQ message body가 될 JSON 계약을 고정**하는 것이다.

### 3.1 Generator가 DB에 직접 저장

```text
event generator -> PostgreSQL -> analytics API -> frontend
```

장점:

- 가장 단순하다.
- 과제 요구사항을 빠르게 만족한다.
- MQ, consumer, retry, ack 처리가 필요 없다.

단점:

- 실제 웹 서비스 이벤트 전송 흐름처럼 보이진 않는다.
- “이벤트가 서비스에서 발생해서 수집 시스템으로 들어간다”는 구조가 약하다.

### 3.2 Generator가 FastAPI ingestion API로 전송

```text
event generator -> FastAPI /events/batch -> PostgreSQL -> analytics API -> frontend
```

장점:

- 웹 서비스 이벤트 수집 구조가 명확하다.
- MQ 없이도 “전송” 개념을 보여줄 수 있다.
- 과제 범위 안에서 구현 가능성이 높다.
- FastAPI에서 validation, batch insert, error response를 보여줄 수 있다.

단점:

- generator와 backend 사이 HTTP 통신이 필요하다.
- ingestion endpoint와 batch validation이 필요하다.

### 3.3 Generator가 MQ로 전송

```text
event generator -> MQ -> consumer -> PostgreSQL -> analytics API -> frontend
```

장점:

- event-driven architecture 느낌이 가장 강하다.
- producer / queue / consumer 역할이 분리된다.
- 실제 서비스 아키텍처 설명이 좋아진다.

단점:

- MQ 선택이 필요하다.
- consumer, ack, retry, DLQ, idempotency를 고민해야 한다.
- Docker Compose 서비스가 늘어난다.
- 과제 범위가 커질 수 있다.

## 4. 현재 추천

1차 구현에서는 먼저 아래 방식으로 payload 계약을 고정했다.

```text
event generator -> stdout JSON Lines
stdout JSON line 1개 = future MQ message body 1개
```

이유:

- Step 1의 핵심인 이벤트 생성기를 먼저 단단히 만들 수 있다.
- JSON Lines는 파일, pipe, MQ publish로 확장하기 쉽다.
- DB schema보다 먼저 producer/consumer 사이의 계약인 raw event JSON을 고정할 수 있다.
- MQ broker 선택은 payload 계약이 안정된 뒤 해도 늦지 않다.

이후 Redis Streams pipeline 구현에서 목표 흐름은 아래처럼 확장했다.

```text
event generator -> MQ -> event consumer -> PostgreSQL
```

## 5. v1 event generator 책임

event generator는 아래 책임만 가진다.

1. 랜덤 이벤트 생성
2. MQ message body로 사용할 수 있는 raw event JSON 생성
3. 생성 이벤트를 stdout JSON Lines로 한 줄씩 출력하거나 Redis Streams `payload` field로 publish
4. 시작/종료/요약 로그는 stderr로 분리

event generator가 직접 하지 않을 것:

- PostgreSQL 직접 연결
- SQL 집계
- 차트 생성
- SQL dashboard 제공
- FastAPI ingestion API 호출
- retry/DLQ 같은 운영-grade 전송 보장

## 6. 이벤트 도메인

이벤트는 두 축으로 나눈다.

### 6.1 Commerce funnel events

사용자 행동과 전환 흐름을 보기 위한 이벤트다.

```text
page_view
product_click
add_to_cart
purchase
checkout_error
```

이 이벤트들로 볼 수 있는 것:

- 어떤 페이지/상품을 많이 보는지
- 클릭 대비 장바구니 전환이 얼마나 되는지
- 장바구니 대비 구매 전환이 얼마나 되는지
- checkout 과정에서 에러가 얼마나 나는지

### 6.2 Operational/status events

서비스 내부 상태와 실패 흐름을 보기 위한 이벤트다.

```text
service_status
job_completed
job_failed
api_error
latency_warning
```

이 이벤트들로 볼 수 있는 것:

- 내부 작업이 정상적으로 끝나는지
- 실패 이벤트가 얼마나 자주 발생하는지
- API 오류나 지연 경고가 특정 시간대에 몰리는지
- 사용자 행동 이벤트와 내부 오류 이벤트를 함께 볼 수 있는지

## 7. MQ raw event payload 설계

현재 우선순위는 DB schema가 아니라 MQ에 들어갈 raw event JSON body를 먼저 단단히 잡는 것이다.

event generator의 stdout JSON Lines 한 줄은 이후 MQ message body 한 건으로 그대로 publish할 수 있게 설계한다.

```text
stdout JSON line 1개
  = raw event JSON object 1개
  = MQ message body 1개
```

초기 payload는 batch envelope를 두지 않고 이벤트 1건 자체를 JSON object로 둔다.

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

필드 원칙:

- `schema_version`: MQ consumer가 해석할 payload 계약 버전
- `event_id`: 이벤트 한 건을 구분하는 unique opaque string. 같은 상품/카테고리에서 같은 행동이 반복되어도 이벤트 인스턴스는 다르므로 중복시키지 않는다.
- `event_type`: 실제 이벤트 이름
- `occurred_at`: 이벤트 발생 시각
- `user_id`: 사용자 행동 분석용. 세션 단위 journey는 v1 범위에서 제외한다.
- `traffic_phase`, `producer_id`: producer/traffic 분석용
- `page_path`, `category_id`, `product_id`, `amount`, `currency`: commerce 분석용
- `error_code`, `error_message`: checkout error 분석용

MQ topic, partition, offset, delivery tag 같은 broker metadata는 payload JSON 안에 넣지 않는다. 이 값들은 broker별 metadata로 다루고, payload에는 서비스에서 발생한 event 자체만 둔다.

## 8. 저장 schema와의 관계

요구사항상 최종적으로는 “JSON을 통째로 저장”하면 안 되므로, consumer/backend는 위 MQ payload를 PostgreSQL의 분리된 컬럼으로 저장해야 한다.

다만 현재 설계 순서는 아래처럼 잡는다.

```text
1. MQ raw event JSON contract 확정
2. consumer validation 설계
3. PostgreSQL events table schema 설계
4. SQL 집계/시각화 설계
```

권장 테이블은 아래와 같다.

```text
events
- id
- schema_version
- event_id
- event_type
- occurred_at
- user_id
- traffic_phase
- producer_id
- page_path
- category_id
- product_id
- amount
- currency
- error_code
- error_message
- ingested_at
```

주의:

- `event_id`에는 unique 제약을 둘 수 있다.
- 저장 단계에서 재전송/idempotency가 필요하면 `event_id` 또는 별도 ingestion key 정책을 설계한다.
- 이벤트별로 쓰지 않는 필드는 nullable로 둔다.
- raw JSON 전체 저장은 v1에서 하지 않는다.

## 9. 생성 분포 초안

기본 실행은 재시작 replay를 피하기 위해 seed를 자동 생성한다.
디버깅/데모에서 `--seed`를 명시하면 deterministic random generation을 사용한다.

기본값:

```text
seed = 자동 생성
mode = infinite
max_events = 지정 시 해당 개수만 생성
time = deterministic simulated clock
```

권장 분포:

```text
page_view       45%
product_click   25%
add_to_cart     15%
purchase         8%
checkout_error   7%
```

이 분포의 의도:

- page view가 가장 많아야 실제 웹 서비스 트래픽처럼 보인다.
- purchase는 page view보다 적어 funnel drop-off가 보인다.
- checkout_error는 적지만 분석 가능한 수량은 있어야 한다.
- operational/status 계열 이벤트는 이후 확장으로 분리한다.

## 10. generator 실행 방식

v1 generator는 CLI로 실행한다.

예상 명령:

```bash
python -m event_generator --max-events 100 --seed 20260424
```

Docker Compose에서는 별도 service로 실행할 수 있다.

```text
event-generator -> MQ -> event-consumer -> PostgreSQL -> backend/frontend 조회
```

아직 broker와 consumer는 구현하지 않는다. 현재는 event generator가 만드는 JSON 한 줄을 이후 MQ message body로 사용할 수 있도록 계약을 먼저 고정한다.

```text
현재: event-generator -> stdout JSON Lines
다음: event-generator -> MQ -> consumer -> PostgreSQL
```

## 11. MQ 도입 판단

MQ는 producer와 저장소를 분리한다는 점에서 이 과제의 아키텍처 스토리에 잘 맞는다.

다만 현재 바로 결정할 것은 broker 제품이 아니라 **MQ에 들어갈 message body JSON 계약**이다.

나중에 broker를 고르면 전체 흐름은 아래처럼 잡을 수 있다.

```text
event-generator -> Redis Streams -> event-consumer -> PostgreSQL
```

RabbitMQ나 Kafka도 가능하지만, broker별 차이는 topic/routing/ack/consumer group에서 발생한다. 이벤트 payload 자체는 이 문서의 `web_event.v1` JSON을 유지한다.

MQ 도입 시 추가로 설계해야 하는 것:

- topic 또는 stream 이름
- consumer group
- ack 정책
- retry 정책
- DLQ 여부
- 중복 처리 idempotency
- consumer 장애 시 동작

따라서 현재는 다음처럼 정리한다.

```text
1차: raw event JSON payload contract 확정
2차: broker 선택
3차: producer publish / consumer 저장 구현
```

## 12. 다음 설계 과제

이 문서 다음에는 아래를 결정해야 한다.

1. MQ broker를 Redis Streams, RabbitMQ, Kafka 중 무엇으로 둘지
2. topic/stream/routing key 이름
3. consumer validation 실패 정책
4. unique `event_id`와 저장용 idempotency key 정책
5. generator service와 consumer/backend service의 compose startup order
6. DB schema를 raw event payload field와 어떻게 1:1 매핑할지


---

## 13. Deep-interview update: Step 1 generator ownership

작성일: 2026-04-24
근거 artifact: `.omx/specs/deep-interview-event-generator-step1.md`

Step 1 deep-interview 결과, event generator의 책임과 위치를 다음처럼 다시 정리한다.

### 13.1 Generator는 독립 producer다

`event_generator`는 FastAPI 내부 startup 기능이 아니다.
웹 서비스 외부에서 이벤트를 계속 만들어내는 producer로 본다.

```text
event_generator -> MQ -> future consumer/storage pipeline
```

이 선택의 이유:

- 실시간으로 이벤트가 계속 생성되는 상황을 표현한다.
- 생성 이벤트를 DB에 직접 쓰면 DB write 부하가 커질 수 있다는 문제의식을 보여준다.
- MQ를 통해 producer와 storage/consumer를 분리하는 아키텍처 스토리를 만들 수 있다.

### 13.2 위치는 루트 `event_generator/`

루트의 `event_generator/` 폴더를 canonical producer 위치로 유지한다.

```text
event_generator/
  ... future generator package/files
```

이유:

- FastAPI backend와 분리된 실행 주체임이 분명하다.
- 과제 Step 1의 “이벤트 생성기”가 독립적으로 보인다.
- 나중에 MQ/consumer/backend와 연결하더라도 producer 책임이 흐려지지 않는다.

### 13.3 MQ broker 선택은 아직 하지 않는다

처음에는 Redis Streams, RabbitMQ, Kafka 중 무엇을 쓸지 바로 결정하려 했지만,
interview 결과 broker 선택보다 먼저 generator의 traffic scale/profile을 정해야 한다고 판단했다.

따라서 현재 순서는 아래가 맞다.

```text
1. event generator traffic profile 설계
2. 그 profile에 맞는 MQ 선택
3. consumer/storage 설계
```

### 13.4 기본 실행은 infinite producer

generator는 기본적으로 계속 이벤트를 보낸다.

단, 과제 실행과 테스트 가능성을 위해 아래 안전장치를 반드시 둔다.

- phase별 rate limit
- graceful shutdown
- `--max-events` 테스트 옵션
- shutdown control/button 개념

기본 traffic concept:

```text
slow -> normal -> burst -> normal -> slow ...
```

phase 전환은 seed 기반 random으로 결정해 재현 가능하게 한다.

### 13.5 Step 1에서 하지 않을 것

Step 1 event generator 자체에서는 아래를 하지 않는다.

- FastAPI 내부 startup으로 이벤트 생성
- PostgreSQL 직접 저장
- MQ broker 최종 선택
- MQ publish 실제 연동
- consumer 구현
- retry/DLQ/ack 운영 정책 구현
- dashboard/visualization 구현
- 고부하 stress test 기본값

### 13.6 Step 1 acceptance 초안

- `event_generator/`에 실행 가능한 producer entrypoint가 있다.
- 기본 실행은 infinite mode다.
- 테스트/데모용 `--max-events N` 옵션이 있다.
- seed를 고정하면 이벤트 순서와 traffic phase 순서가 재현된다.
- 최소 2개 이상의 이벤트 타입을 생성한다.
- 목표 taxonomy는 commerce + operational 이벤트를 모두 포함한다.
- 이벤트는 구조화된 필드를 가진다.
- 생성한 이벤트를 stdout에 한 줄씩 출력한다.
- rate limit과 graceful shutdown을 지원한다.
- DB 직접 저장은 하지 않는다.
- MQ publish는 하지 않는다.
- FastAPI 없이도 generator unit test가 가능해야 한다.

### 13.7 현재 추천의 정리

최신 deep-interview 결과로는 Step 1 관점에서 아래 방향이 더 우선이다.

```text
event-generator -> stdout JSON Lines
stdout JSON line 1개 = future MQ message body 1개
```

단, 아직 MQ broker를 고르지는 않는다.
먼저 generator의 traffic profile과 event schema를 설계한 뒤 broker를 선택한다.

---

## 14. 확정된 v1 이벤트 타입

과제 배경은 “웹 서비스에서 유저의 행동(클릭, 구매, 에러 등)을 이벤트 로그로
기록하고, 이를 분석해 서비스를 개선한다”는 것이다.
따라서 v1 event generator는 분석 의미가 분명한 **커머스 퍼널 이벤트**를 먼저
생성한다.

확정 이벤트 타입:

```text
page_view
product_click
add_to_cart
purchase
checkout_error
```

이 조합은 아래 흐름을 표현한다.

```text
페이지 조회
  -> 상품 클릭
  -> 장바구니 담기
  -> 구매 완료
  -> 결제/주문 에러
```

### 14.1 이벤트 타입별 의미

| 이벤트 타입 | 의미 | 분석 목적 |
|---|---|---|
| `page_view` | 사용자가 페이지를 조회함 | 전체 트래픽 규모와 인기 경로 확인 |
| `product_click` | 사용자가 상품을 클릭함 | 상품 관심도와 클릭률 확인 |
| `add_to_cart` | 사용자가 상품을 장바구니에 담음 | 구매 의도와 funnel 중간 전환 확인 |
| `purchase` | 사용자가 구매를 완료함 | 구매 전환과 매출 규모 확인 |
| `checkout_error` | 결제/주문 과정에서 에러가 발생함 | 구매 이탈 원인과 서비스 문제 확인 |

### 14.2 이 이벤트 구성이 좋은 이유

과제 예시인 클릭, 구매, 에러를 모두 포함한다.

- 클릭: `product_click`
- 구매: `purchase`
- 에러: `checkout_error`

추가로 `page_view`와 `add_to_cart`를 넣어 단순한 이벤트 나열이 아니라
분석 가능한 funnel 흐름을 만든다.

이렇게 하면 나중에 아래 SQL 집계가 자연스럽다.

- 이벤트 타입별 발생 횟수
- funnel 단계별 전환 수
- 유저별 이벤트 수
- 구매 대비 checkout error 비율
- 시간대별 페이지 조회/구매/에러 추이

### 14.3 v1 생성 비율 초안

실제 웹 서비스에서는 조회가 가장 많고 구매는 상대적으로 적다.
따라서 기본 생성 비율은 아래처럼 시작한다.

```text
page_view        45%
product_click    25%
add_to_cart       15%
purchase           8%
checkout_error     7%
```

이 비율은 고정 business rule이라기보다, 분석 결과가 자연스럽게 나오도록 하는
초기 traffic profile이다. 이후 slow/normal/burst phase에 따라 초당 생성량은
바뀌지만, 이벤트 타입 비율은 기본적으로 이 분포를 따른다.

---

## 15. 확정된 Step 1 구현 범위

Step 1의 구현 범위는 **B. 이벤트 생성 + stdout 출력**까지로 제한한다.

```text
event_generator 실행
  -> 랜덤 이벤트 생성
  -> 구조화된 이벤트를 stdout으로 출력
```

이번 단계에서 하지 않는 것:

```text
MQ publish
FastAPI 전송
PostgreSQL 저장
consumer 구현
Docker Compose 연결
시각화
```

이 결정의 이유:

- 과제 Step 1의 핵심은 “웹 서비스 이벤트를 랜덤하게 생성하는 스크립트 작성”이다.
- 따라서 먼저 독립 producer가 이벤트를 제대로 생성하고 보여주는 것에 집중한다.
- stdout 출력은 이후 MQ publish, 파일 저장, API 전송으로 확장하기 쉽다.
- MQ는 방향성으로 남기되, broker 선택과 실제 publish는 traffic profile과 storage/consumer 설계 이후로 미룬다.

### 15.1 Step 1 실행 예시

예상 실행 형태:

```bash
python -m event_generator --max-events 100 --seed 20260424
```

기본값:

- 기본 실행은 infinite mode다.
- `--max-events N`을 주면 N개 출력 후 종료한다.
- `--seed`를 생략하면 실행마다 seed를 자동 생성해 producer 재시작 시 같은
  `event_id` sequence를 replay하지 않는다.
- `--seed`를 주면 같은 이벤트 순서와 traffic phase 순서를 재현한다.

### 15.2 Step 1 출력 예시

stdout에는 이벤트를 한 줄씩 출력한다.

```json
{"schema_version":"web_event.v1","event_id":"evt_7f3a9c1e2b4098ab76cd","event_type":"page_view","occurred_at":"2026-04-24T00:00:00.000Z","user_id":"user_001","traffic_phase":"normal","producer_id":"producer_local","page_path":"/products","category_id":null,"product_id":null,"amount":null,"currency":null,"error_code":null,"error_message":null}
{"schema_version":"web_event.v1","event_id":"evt_a8c04d2e9b1190fedcba","event_type":"product_click","occurred_at":"2026-04-24T00:00:00.200Z","user_id":"user_002","traffic_phase":"burst","producer_id":"producer_local","page_path":"/products/prod_iphone_15","category_id":"cat_smartphone","product_id":"prod_iphone_15","amount":null,"currency":null,"error_code":null,"error_message":null}
```

출력 format은 이후 MQ publish 단계에서 message body로 그대로 재사용할 수 있도록 구조화된 JSON line 형태로 둔다.

## 16. Step 1 구현 결과

작성일: 2026-04-24

Step 1은 앞서 확정한 **B안: 이벤트 생성 + stdout 출력** 범위로 구현했다.

구현 위치:

```text
event_generator/
```

실행 예시:

```bash
python -m event_generator --max-events 10 --seed 20260424 --no-sleep
```

로컬 `python`이 3.12 환경을 가리키지 않는 경우에는 기존 backend uv 환경으로 실행한다.

```bash
UV_PROJECT_ENVIRONMENT=../.venv uv run --project backend python -m event_generator --max-events 10 --seed 20260424 --no-sleep
```

구현된 기능:

- 독립 Python producer package.
- stdout JSON Lines 출력.
- stderr start/stop/shutdown summary 분리.
- seed 기반 deterministic event sequence.
- `--max-events` 종료 가능한 demo/test mode.
- 기본 infinite mode.
- slow/normal/burst traffic phase와 phase별 rate limit.
- SIGINT/SIGTERM graceful shutdown.
- `event_generator/README.md`에 이벤트 타입, 필드, 설계 이유, 실행법 정리.
- `make ci` quality gate에 `event_generator/`와 `event_generator/tests` 포함.

검증 결과:

```text
make ci
-> ruff format/check 통과
-> pyrefly 0 errors
-> guardrails 통과
-> pytest 52 passed
```

1000개 sample 검증에서는 5개 이벤트 타입이 모두 등장했다.

```text
page_view
product_click
add_to_cart
purchase
checkout_error
```

Step 1 구현에서도 아래 항목은 의도적으로 제외했다.

- MQ publish
- FastAPI 전송
- PostgreSQL 저장
- consumer 구현
- Docker Compose 연결
- 시각화

## 17. 데이터 포맷 설계 노트

자세한 Step 1 데이터 포맷 설계와 판단 이유는 아래 문서에 분리해 기록했다.

- `docs/event_generator/mq_event_payload_contract.md`
- `docs/event_generator/redis_streams_pipeline_implementation_plan.md`
- `docs/event_generator/event_data_format_design.md`
