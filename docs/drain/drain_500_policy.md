# 500 error drain policy

작성일: 2026-04-23  
대상: backend 500 error 기록, 관측, drain 전환 기준

## 1. 목적

이 문서는 500 error를 어떻게 해석하고, 언제 drain 전환으로 승격할지 정의한다.
핵심 원칙은 다음이다.

```text
모든 500은 치명적인 error signal이다.
하지만 모든 500이 즉시 process drain 대상은 아니다.
```

## 2. 500 error의 의미

사용자와 운영 관점에서 500은 모두 심각한 실패다.

500 error가 의미하는 것:

- 요청이 실패했다.
- 서버 내부에서 예상하지 못한 문제가 발생했거나 정상 처리하지 못했다.
- 신뢰도와 사용자 경험에 직접 영향을 준다.
- 반드시 기록하고 추적해야 한다.
- 알림/집계/장애 분석 후보가 된다.

따라서 모든 500은 아래처럼 다룬다.

```text
500 = error log + trace correlation + metric/alert 후보
```

초기 구현 범위:

- 모든 500을 구조화 error log로 남긴다.
- request id / trace id / span id로 추적 가능하게 한다.
- metric과 alert 연동은 observability stack 도입 시 순차적으로 추가한다.

## 3. 500 error와 drain의 차이

500 error는 개별 요청 실패 신호다.

Drain은 더 높은 수준의 lifecycle 결정이다.

Drain이 답해야 하는 질문:

```text
이 process가 새 트래픽을 계속 받아도 되는가?
```

따라서 500 error가 발생해도 아래 두 판단은 분리한다.

| 판단 | 의미 | 기본 조치 |
|---|---|---|
| 500 error signal | 개별 요청이 실패함 | error log, trace 연결, metric/alert 후보 |
| drain decision | process가 새 트래픽을 받아도 되는지 판단 | readiness에서 제외 |

중요한 경계:

```text
모든 500 response는 error signal로 기록한다.
하지만 초기 drain threshold 집계는 모든 500이 아니라,
request logging middleware의 top-level exception path까지 전파된 unhandled exception에 의해 발생한 500만 대상으로 한다.
```

즉:

```text
기록 대상 = 모든 500
drain count 대상 = middleware top-level unhandled exception 기반 500
```

## 4. drain하지 않는 500 후보

아래 500은 심각하게 기록해야 하지만, 단발이면 즉시 drain하지 않는다.

- 특정 payload edge case에서만 발생한 오류
- 외부 API timeout 1회
- 특정 endpoint의 국소적 버그
- 사용자의 특이 입력으로 드러난 단일 실패
- downstream 일시 장애
- domain/application에서 아직 분류되지 않은 단발 unhandled exception

이 경우 조치:

- error log 남김
- request id / trace id로 추적 가능하게 함
- middleware top-level unhandled exception이면 sliding window에 기록
- threshold 전까지는 running 상태 유지

Downstream/dependency 연결:

- 단발 downstream 장애는 즉시 drain하지 않는다.
- 그러나 필수 dependency의 반복적/장기적 실패는 readiness 실패 또는 drain 승격 후보가 된다.
- dependency readiness 정책은 `docs/drain/drain_policy.md`의 dependency health 기준을 따른다.

## 5. drain 후보가 되는 500

아래 500은 process가 계속 새 트래픽을 받으면 피해가 커질 가능성이 있다.
따라서 반복되거나 명확히 치명적이면 drain 대상으로 본다.

- DB schema mismatch
- migration 누락 또는 잘못된 schema 적용
- 필수 설정 누락이 runtime 중 발견됨
- 모든 요청 또는 핵심 요청 대부분에서 같은 예외 반복
- connection pool 또는 필수 dependency가 지속적으로 깨짐
- 내부 invariant 붕괴
- 데이터 무결성을 더 이상 보장할 수 없는 오류
- 메모리/디스크 등 필수 runtime resource 문제
- 짧은 시간 내 unhandled exception 폭증

정책/구현 경계:

- 위 사례들은 운영적으로 drain 후보로 본다.
- 그러나 초기 자동화 구현은 threshold 기반 drain만 도입한다.
- 즉시 drain이 필요한 치명적 사례는 우선 수동 운영 판단 또는 향후 exception taxonomy 도입 이후 자동화한다.

## 6. 초기 drain 전환 정책

초기 구현에서는 다음 기준을 사용한다.

```text
단발 500은 drain하지 않는다.
middleware top-level unhandled exception을 sliding window에 기록한다.
60초 안에 unhandled exception 5회 이상 발생하면 drain 상태로 전환한다.
```

기본값:

```text
drain_window_seconds = 60
drain_unhandled_exception_threshold = 5
```

정확히 threshold에 도달한 시점에 drain한다.

집계 대상:

- request logging middleware의 `except Exception` path까지 전파된 예외
- 이 예외로 인해 생성된 500 응답

집계 제외:

- known exception이 정상 response로 변환된 500
- expected readiness/heartbeat 503
- health endpoint가 상태를 정상적으로 보고한 503
- route-level에서 직접 처리된 오류

## 7. drain 이후 추가 500 처리

drain 상태에 들어간 뒤에도 개별 500은 계속 error signal로 기록한다.

다만 drain 상태는 이미 시작되었으므로 추가 500은 상태 전이를 다시 유발하지 않는다.

정책:

- 추가 500은 error log로 남긴다.
- request id / trace id로 추적 가능하게 한다.
- drain reason은 최초 원인을 유지한다.
- 이후 오류는 보조 로그/metric으로만 남기고 기존 drain reason을 덮어쓰지 않는다.

## 8. 즉시 drain 정책은 defer

특정 exception type을 즉시 drain으로 승격하는 정책은 아직 도입하지 않는다.

예상 future 후보:

```python
FATAL_EXCEPTION_TYPES = {
    ConfigurationRuntimeError,
    SchemaMismatchError,
    DataIntegrityInvariantError,
}
```

하지만 현재는 exception taxonomy가 충분하지 않으므로, 즉시 drain 타입 목록을 만들지 않는다.
먼저 threshold 기반 drain으로 시작한다.

## 9. 기록 정책

모든 500 error log에는 최소한 아래 정보가 있어야 한다.

```text
level=ERROR
event=request_failed 또는 request_server_error
status_code=500
request_id
trace_id
span_id
http_method
path
duration_ms
error.type
error.message
error.stack 정책에 따른 stack 값
```

`error.stack`은 `docs/drain/drain_policy.md`와 `docs/logging_structure/logging_error_stack_policy.md`의 정책을 따른다.

## 10. metric / alert 정책 방향

초기 구현에서는 error log를 우선한다.
metric과 alert는 observability stack 도입 이후 추가한다.

향후 alert 레벨링 후보:

| 상황 | 처리 방향 |
|---|---|
| 단발 500 | 대시보드/집계 중심 |
| 반복 500 | warning alert 후보 |
| drain 승격 500 cluster | critical alert 후보 |

주의:

- 모든 단발 500을 즉시 alert로 보내면 운영 노이즈가 커질 수 있다.
- alert는 빈도, endpoint 중요도, drain 승격 여부를 함께 고려한다.

## 11. drain 전환 로그

500 error가 threshold를 초과해 drain으로 승격되면 별도 lifecycle event를 남긴다.

예상 event:

```text
lifecycle_draining_started
```

예상 필드:

```json
{
  "event": "lifecycle_draining_started",
  "lifecycle": "draining",
  "drain_reason": "unhandled_exception_threshold_exceeded",
  "error_count": 5,
  "window_seconds": 60,
  "last_error_at": "2026-04-23T00:00:00Z",
  "drain_started_at": "2026-04-23T00:00:01Z"
}
```

## 12. 테스트 기준

구현 시 반드시 보호할 테스트:

1. 단발 unhandled 500은 drain하지 않는다.
2. threshold 미만 반복 500은 drain하지 않는다.
3. sliding window 밖 오래된 500은 집계에서 제외한다.
4. threshold에 도달하면 drain한다.
5. threshold 집계 대상이 아닌 500은 error log는 남지만 drain 카운트에는 포함되지 않는다.
6. drain 후 ready는 503을 반환한다.
7. drain 후 live는 200을 유지한다.
8. drain 이후 추가 500은 error log로 남지만 drain reason을 덮어쓰지 않는다.
9. 모든 500은 error log로 남는다.
10. drain 전환 시 `lifecycle_draining_started` 로그가 남는다.

## 13. 결론

이 정책의 결론은 다음이다.

```text
모든 500은 치명적인 error signal로 기록한다.
하지만 drain은 process lifecycle 전환이므로 더 높은 기준으로 판단한다.
단발 500은 기록/집계하고, 반복되거나 전역 상태 손상을 시사하는 500만 drain으로 승격한다.
```
