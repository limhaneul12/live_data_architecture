# Schemas design

## What we meant by schema

이번 작업에서 schema는 두 층으로 나뉜다.

1. 이벤트 payload schema
2. PostgreSQL 저장 schema

이 둘을 분리해서 생각한 이유는 producer와 storage의 책임이 다르기 때문이다.
producer는 MQ로 흘려보낼 이벤트 계약을 책임지고, storage는 SQL 집계가 잘 되는 컬럼 구조를
책임진다.

## Event payload schema

MQ로 보내는 이벤트는 `web_event.v1` payload로 고정했다.

공통 필드:

- `schema_version`
- `event_id`
- `event_type`
- `occurred_at`
- `user_id`
- `traffic_phase`
- `producer_id`

상세 필드:

- `page_path`
- `category_id`
- `product_id`
- `amount`
- `currency`
- `error_code`
- `error_message`

의도는 “이벤트 타입이 달라도 top-level contract는 같게 유지한다”였다.
이렇게 해야 consumer 입장에서 타입마다 전혀 다른 payload parser를 만들지 않아도 된다.

## PostgreSQL storage schema

DB에서는 JSON blob 전체 저장 대신 컬럼 분리 저장을 선택했다.

이유는 명확하다.

- `GROUP BY event_type`
- `GROUP BY user_id`
- `DATE_TRUNC('hour', occurred_at)`
- `WHERE error_code IS NOT NULL`

같은 분석을 바로 SQL로 하기 위해서다.

이번 과제의 핵심이 “저장 후 분석과 시각화”이므로, 저장 schema는 조회 편의성이 가장 중요했다.

## Nullable field strategy

모든 이벤트 타입이 같은 상세 필드를 갖지는 않는다.

예를 들어:

- `purchase`만 `amount`, `currency`가 의미 있다.
- `checkout_error`만 `error_code`, `error_message`가 의미 있다.
- `page_view`는 `page_path`가 중요하다.

그래서 이벤트 타입별 별도 테이블을 여러 개 두기보다는, 공통 테이블 하나에 nullable detail
column을 두는 방식을 택했다.

장점:

- 단일 테이블에서 전체 이벤트 흐름 분석 가능
- ingest 로직 단순
- Docker 과제 범위에 맞게 구조가 단순함

단점:

- 일부 컬럼은 특정 이벤트에서만 채워짐

이번 과제에서는 단순성과 집계 용이성이 더 중요하다고 판단했다.

## 고민했던 부분

### event_id를 완전 random으로 할지

중복 허용 ID는 분석/적재 안정성에 불리하다.
그래서 `event_id`는 opaque unique identifier로 보고, 반복 가능한 것은 `product_id`,
`category_id`, `event_type` 같은 분석 축으로 남겼다.

### raw events를 SQL Lab에 직접 열어둘지

원본은 저장 기준 테이블이고, SQL Lab은 generated view / saved view table 중심으로
보여주도록 설계했다. 원본 직접 조회를 열면 안전성과 UX가 같이 복잡해지기 때문이다.
