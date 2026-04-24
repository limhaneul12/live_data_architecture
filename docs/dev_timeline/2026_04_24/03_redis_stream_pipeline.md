# 03. Redis Streams 기반 이벤트 전송 파이프라인

## 무엇을 했는지

Step 1 generator가 만든 `web_event.v1` payload를 Redis Streams로 전송하고, backend가 batch로 읽을 수 있도록 파이프라인을 추가했습니다.

현재 흐름은 아래와 같습니다.

```text
event_generator --sink redis
  -> Redis Streams web.events.raw.v1
  -> FastAPI lifespan background consumer
  -> event_analytics application usecase
  -> PostgreSQL batch insert
  -> DB commit 성공 후 XACK
```

## 왜 Redis Streams를 선택했는지

Kafka, RabbitMQ Streams, Redis Streams 중에서 과제 범위와 현재 프로젝트 환경을 같이 봤습니다.
Redis Streams는 다음 이유로 v1에 적합하다고 판단했습니다.

- Docker Compose에 붙이기 쉽다.
- consumer group / pending / ack 개념을 보여줄 수 있다.
- `COUNT` 기반 batch read가 가능하다.
- Kafka Connect까지 도입하는 것보다 과제 범위를 덜 키운다.
- 기존에 참고 가능한 Redis stream runtime 개념이 있었다.

단, 기존 stream runtime을 그대로 복사하지 않고 이 과제 범위에 맞는 작은 adapter로 새로 작성했습니다.

## consumer 실행 위치

consumer는 별도 worker service가 아니라 FastAPI lifespan background task로 실행합니다.
이유는 사용자가 지적한 것처럼 DB 저장 로직은 결국 backend의 application/repository 로직을 타기 때문입니다.

v1에서는 `SERVICE_EVENT_CONSUMER_ENABLED=true`일 때만 app lifespan에서 consumer를 시작합니다.
운영형 확장에서는 같은 image의 별도 command나 worker process로 분리할 수 있습니다.

## 실패 처리 보정

Codex CLI review에서 Redis consumer에 대해 몇 가지 data-loss / hot-loop 위험이 지적되어 보정했습니다.

- consumer group은 `0-0`부터 생성해 app보다 producer가 먼저 쓴 이벤트도 읽도록 함
- 같은 consumer의 pending entry를 먼저 읽고, 없을 때만 `>`로 새 메시지 read
- DB 저장 실패 시 valid message는 ack하지 않음
- DB 실패 후 같은 pending batch를 즉시 무한 재시도하지 않도록 backoff 추가
- Redis read/group setup 오류가 background task를 죽이지 않도록 retry loop 안에서 처리
- malformed JSON/UTF-8 payload는 invalid payload로 분류해 ack/drop

## 아직 남긴 것

아래는 Step 2 핵심 범위 밖이라 v2 후보로 남겼습니다.

- 다른 consumer가 소유한 stale pending reclaim (`XAUTOCLAIM`)
- DLQ stream
- poison message quarantine
- redrive tooling
- multi-consumer scale-out strategy

## 현재 기준

- Stream key: `web.events.raw.v1`
- Consumer group: `event_analytics_writer`
- Consumer name: `app-consumer-1`
- key/group/name/maxlen은 계약 상수
- Redis URL/mode/batch/block만 `.env` 기반 runtime 설정
- 관련 문서: `docs/event_generator/redis_streams_pipeline_implementation_plan.md`
