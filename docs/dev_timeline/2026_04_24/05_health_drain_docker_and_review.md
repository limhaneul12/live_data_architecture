# 05. Health / drain / Docker Compose / Codex review 보정

## 무엇을 했는지

Redis Streams와 PostgreSQL이 이벤트 수집 경로에 들어오면서 health와 Docker 실행도 같이 보강했습니다.

변경한 핵심은 아래와 같습니다.

- `/health/ready`에 `app`, `redis`, `database` check 포함
- `/health/heartbeat`에 Redis/PostgreSQL dependency 상태 포함
- consumer enabled 상태에서 Redis는 `PING`, PostgreSQL은 `SELECT 1`로 probe
- drain/stopping 시 healthy dependency를 `draining`으로 표시
- `docker compose up` 한 번으로 app + db + redis + event-generator 실행 가능
- app container 시작 시 Alembic `upgrade head` 실행 후 uvicorn 실행
- `exec uvicorn`으로 Docker stop 시 FastAPI lifespan shutdown이 가능하도록 보정

## .env와 docker-compose 기준

사용자가 지적한 것처럼 `.env`는 이미 프로젝트 설정의 기준입니다.
그래서 compose에서 `.env` 사용을 제거했던 것은 과한 변경이었고 다시 복구했습니다.

현재 기준은 아래입니다.

- app service와 event-generator service는 `env_file: .env`를 읽음
- compose network 안에서 달라져야 하는 값만 service `environment`로 override
  - `DATABASE_DB_ADDRESS=postgresql://...@db:5432/...`
  - `STREAM_REDIS_URL=redis://redis:6379/0`
  - `SERVICE_EVENT_CONSUMER_ENABLED=true`
- 로컬 `.env`의 localhost 값은 개발 실행 기준으로 유지

## Codex CLI review 반영

사용자 요청에 따라 `codex review --uncommitted`를 실행해서 아키텍처/안정성을 점검했습니다.
검토 결과로 아래 문제들을 반영했습니다.

- Redis group을 `$`가 아니라 `0-0`부터 생성
- pending message 재시도 경로 추가
- malformed payload가 consumer task를 죽이지 않도록 invalid 처리
- stream read/group setup 실패 후 consumer task가 죽지 않도록 retry loop로 이동
- DB 실패 pending retry에 backoff 추가
- generator 기본 seed 고정으로 인한 restart replay 제거
- infinite mode event id 중복 방지 set 제거로 메모리 증가 방지
- Docker CMD에 `exec` 추가
- nullable field 생략을 허용하지 않도록 Pydantic schema 보정

## 검증 기록

로컬 품질 게이트:

```text
make ci
- ruff format/check 통과
- pyrefly 0 errors
- guardrails 통과
- pytest 82 passed
```

Docker Compose E2E:

```text
/health/ready -> {"status":"ok","checks":{"app":"ok","redis":"ok","database":"ok"},"reason":null}
/health/heartbeat -> app/redis/database 모두 ok
Redis XLEN web.events.raw.v1 -> 10
Redis XPENDING web.events.raw.v1 event_analytics_writer -> 0
PostgreSQL SELECT count(*) FROM events -> 10
```

## 남은 리스크

Step 2 v1에서는 과제 핵심인 “생성 → MQ → batch 저장”을 우선했습니다.
운영-grade로 확장할 때는 아래를 추가 검토해야 합니다.

- DLQ / poison message quarantine
- stale pending reclaim (`XAUTOCLAIM`)
- consumer lag metric
- 별도 worker process 분리
- SQL 분석 API와 visualization 단계
