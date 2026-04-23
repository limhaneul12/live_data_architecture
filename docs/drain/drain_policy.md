# App drain policy

작성일: 2026-04-24  
대상: FastAPI backend app-level lifecycle, heartbeat, readiness, drain 상태 관리

## 1. 목적

이 문서는 backend 앱 자체가 언제 정상 상태이고 언제 새 트래픽에서 빠져야 하는지를 정의한다.
현재 단계에서는 DB/외부 dependency 상태를 포함하지 않고 **app 기준 drain**까지만 다룬다.

핵심 의도:

1. 앱을 즉시 죽이지 않는다.
2. 먼저 app lifecycle을 drain 상태로 전환할 수 있게 한다.
3. readiness에서 빠져서 새 트래픽을 받지 않게 한다.
4. 이미 들어온 요청은 마무리할 시간을 준다.
5. 이후 orchestrator, Docker, Kubernetes, 상위 프로세스 또는 운영자가 재시작/격리/확인을 수행할 수 있게 한다.

## 2. 현재 구현 범위

현재 구현은 아래로 제한한다.

- process-local in-memory lifecycle state
- `/health/live`
- `/health/ready`
- `/health/heartbeat`
- app 기준 running/draining/stopping 상태 표현
- 정상 healthcheck request log skip

현재 구현하지 않는다.

- DB checker
- unhandled exception threshold drain
- lifecycle event history
- 일반 요청 강제 503

## 3. 운영 인프라 전제

현재 in-memory lifecycle 구현은 최종 운영 모델이 아니라 bootstrap 단계다.
서비스가 DB 같은 운영 인프라를 도입하면 health, readiness, heartbeat 정책은 다시 검토한다.

예상 역할:

- DB: 영속 데이터, lifecycle/drain event history, 운영 audit, 장애 이력 조회

이번 범위에서는 외부 shared state나 자동 복구 메커니즘을 앱 코드에 넣지 않는다.

## 4. endpoint 정책

### 4.1 `/health`

기존 호환용 endpoint다.

HTTP 200:

```json
{"status":"ok"}
```

### 4.2 `/health/live`

프로세스 생존 확인용 endpoint다.

HTTP 200:

```json
{"status":"ok"}
```

Draining 상태여도 live는 200을 유지한다.
Drain은 프로세스 사망이 아니라 새 트래픽에서 빠지는 신호다.

### 4.3 `/health/ready`

새 트래픽 수신 가능 여부 확인용 endpoint다.

Running 상태:

```json
{
  "status": "ok",
  "checks": {"app": "ok"},
  "reason": null
}
```

Draining 상태:

```json
{
  "status": "draining",
  "checks": {"app": "draining"},
  "reason": "manual"
}
```

### 4.4 `/health/heartbeat`

운영자와 자동화 도구가 상세 app 상태를 읽기 위한 endpoint다.

Running 상태:

```json
{
  "heartbeat": {
    "app": "ok",
    "lifecycle": "running",
    "draining": false,
    "drain_reason": null,
    "started_at": "2026-04-23T00:00:00Z",
    "drain_started_at": null
  }
}
```

Draining 상태:

```json
{
  "heartbeat": {
    "app": "draining",
    "lifecycle": "draining",
    "draining": true,
    "drain_reason": "manual",
    "started_at": "2026-04-23T00:00:00Z",
    "drain_started_at": "2026-04-23T00:01:00Z"
  }
}
```

## 5. lifecycle 상태와 전이

상태 enum:

```text
starting
running
draining
stopping
```

전이:

```text
starting -> running
running -> draining
draining -> stopping
starting -> stopping
running -> stopping
```

```text
draining -> running
```

전이는 현재 앱 코드 범위에 포함하지 않는다. 이 판단은 향후 운영 정책/오케스트레이터 책임으로 남겨둔다.

## 6. 500 error와 drain

현재 구현에서는 500 error가 자동으로 drain을 유발하지 않는다.

정책:

- 모든 500은 error log로 남긴다.
- 단발 500은 app lifecycle을 바꾸지 않는다.
- unhandled exception threshold drain은 아직 구현하지 않는다.
- 어떤 500이 drain-worthy인지 판단하려면 실제 서비스 로직과 dependency가 더 필요하다.

관련 미래 정책은 `docs/drain/drain_500_policy.md`에 남긴다.

## 7. healthcheck logging

정상 healthcheck 로그는 남기지 않는다.

대상:

```text
/health
/health/live
/health/ready
/health/heartbeat
```

Expected status 보고는 로그 노이즈로 본다.
Unexpected health endpoint exception이나 의도하지 않은 5xx는 로그를 남긴다.

## 8. 이번 정책에서 아직 결정하지 않은 것

- unhandled exception threshold drain 도입 여부
- drain 상태에서 일반 요청을 강제 503으로 막을지 여부
- fatal exception taxonomy
- lifecycle event history 저장 여부

## 9. 현재 결론

현재 구현은 app 기준 drain만 제공한다.

1. app lifecycle 상태를 process-local로 관리한다.
2. ready는 app lifecycle 기준으로 판단한다.
3. heartbeat는 app 상태만 노출한다.
4. DB/dependency 상태는 아직 포함하지 않는다.
5. 500 error는 기록하지만 자동 drain하지 않는다.
