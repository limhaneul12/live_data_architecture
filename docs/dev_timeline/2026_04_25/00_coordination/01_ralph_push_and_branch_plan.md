# 01. Ralph 실행 시작과 브랜치 분리 계획

## 무엇을 했는지

2026-04-25에는 사용자의 `$ralph` 요청에 따라 현재 `fect/event-generator` 작업을 먼저 정리하고 push한 뒤, 이후 작업을 성격별 브랜치로 분리하기로 했다.

현재 기준은 아래와 같다.

```text
현재 브랜치: fect/event-generator
목적: Step 1 event generator + Redis Streams/DB 저장 기반까지 정리한 현재 작업 push
다음 backend/Step2 브랜치: fect/step2-event-storage-analytics
다음 frontend 브랜치: fect/frontend-event-analytics
```

## push 전 보정한 것

Codex CLI review와 사용자 피드백을 반영해 push 전에 아래를 보정했다.

- `docker-compose.yml`에서 `.env` 사용을 복구했다.
- compose network에서 달라지는 값만 service `environment`로 override한다.
  - `DATABASE_DB_ADDRESS=postgresql://...@db:5432/...`
  - `STREAM_REDIS_URL=redis://redis:6379/0`
  - `SERVICE_EVENT_CONSUMER_ENABLED=true`
- backend architecture rule의 Google-style docstring 기준에 맞춰 public 함수 docstring을 `Args:` / `Returns:` 형식으로 정리했다.
- `WebEventPayload`는 nullable field도 required nullable로 유지해 `web_event.v1`의 “모든 필드 존재” 계약을 강제한다.
- Redis consumer group setup 실패도 retry loop 안에서 복구되도록 했다.

## 왜 이렇게 했는지

`.env`는 이미 프로젝트 실행 설정의 기준이다. compose에서 `.env`를 제거하면 로컬 실행과 Docker 실행의 설정 source가 갈라진다.
따라서 `.env`는 유지하고, Docker network alias 때문에 반드시 달라지는 접속 주소만 compose에서 override하는 방식이 더 맞다.

또한 Step2와 frontend는 변경 성격이 다르므로 같은 브랜치에서 계속 누적하지 않고 분리한다.
이렇게 해야 현재 Step1/기반 작업을 안전하게 리뷰/추적하고, 이후 backend 저장/분석 API와 frontend 시각화 작업을 독립적으로 관리할 수 있다.

## 검증 계획

push 전에는 아래를 확인한다.

```text
make ci
docker compose config
git diff --check
다른 Codex agent review
```

push 후에는 backend Step2 브랜치에서 SQL 집계/분석 API/문서 보강을 진행하고, frontend 브랜치에서 Next.js 기반 SQL 입력/결과/차트 UI를 진행한다.

## 실제 push 결과

`fect/event-generator`는 아래 commit으로 push했다.

```text
5f74f59 Build a resilient event ingestion path
origin/fect/event-generator
```

push 전 검증 결과:

- `make ci` 통과
- `docker compose config` 통과
- `git diff --check` 통과
- Compose E2E smoke 통과
  - `/health/ready` -> app/redis/database 모두 `ok`
  - generator 10건 Redis publish
  - Redis `XLEN web.events.raw.v1` -> 10
  - Redis `XPENDING web.events.raw.v1 event_analytics_writer` -> 0
  - PostgreSQL `SELECT count(*) FROM events` -> 10

이후 `fect/step2-event-storage-analytics` 브랜치를 새로 만들어 backend Step2/Step3 작업을 시작했다.
