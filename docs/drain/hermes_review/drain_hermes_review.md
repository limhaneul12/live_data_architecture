# Drain policy review (updated)

전체적으로 이번 개정본은 이전 버전보다 훨씬 좋아졌습니다. 특히 제가 이전에 우려했던 핵심 지점들인

- lifecycle state의 범위
- 상태 전이 규칙
- unhandled exception의 정의
- expected health 503와 unexpected health failure의 로깅 구분
- threshold 집계 방식

이 문서 안에서 상당 부분 명확해졌습니다.

지금 상태의 문서는 “초기 drain/readiness 정책 문서”로서 꽤 실전적입니다. 구현자가 문서만 읽고도 어디까지가 이번 범위인지, 무엇을 defer하는지, 어떤 상태를 로그로 남겨야 하는지 비교적 명확하게 이해할 수 있습니다.

다만 아직 몇 군데는 구현 전에 한 번 더 고정해두면 좋겠습니다. 아래처럼 정리합니다.

## 1. 이번 개정본에서 특히 좋아진 점

### 1.1 process-local in-memory state를 명시한 점이 좋습니다

`3. lifecycle state 범위`에서 아래를 명시한 것은 매우 좋습니다.

- process-local in-memory state
- multi-worker에서 worker별 상태가 다를 수 있음
- cluster/service-wide coordination은 이번 범위 밖

이 한 단락이 들어가면서 문서의 해석 불확실성이 많이 줄었습니다. 특히 운영자가 “왜 어떤 worker는 draining인데 전체 서비스는 살아 있지?” 같은 상황을 만났을 때 설명이 가능해졌습니다.

### 1.2 상태 전이 규칙이 훨씬 명확해졌습니다

`5.5 상태 전이 규칙`에서

- `starting -> running`
- `running -> draining`
- `draining -> stopping`
- recovery 없음

을 분명히 적은 점이 좋습니다. 초기 정책에서 단방향 상태 머신으로 가는 판단은 보수적이지만 안전합니다. drain/recovery를 동시에 열어두면 테스트와 운영 해석이 급격히 어려워지는데, 그걸 잘 피했습니다.

### 1.3 unhandled exception 정의가 실무적으로 적절합니다

`6. unhandled exception 정의`는 이번 문서의 핵심 개선점입니다.

특히 아래 경계가 좋습니다.

- middleware 최상단 exception path까지 올라온 예외만 집계
- FastAPI exception handler가 정상 변환한 예외는 제외
- known 4xx/정상 변환 오류는 제외
- expected readiness/heartbeat 503는 제외

이렇게 해야 threshold가 “예상된 실패” 때문에 오염되지 않습니다. 이 정의는 구현과 테스트 양쪽 모두에 도움이 됩니다.

### 1.4 health logging 정책이 훨씬 좋아졌습니다

`9.2 healthcheck log`에서 expected 상태 보고와 unexpected failure를 구분한 것은 아주 좋은 수정입니다.

특히 아래 판단이 타당합니다.

- 정상 2xx 미로깅
- expected `/health/ready` 503 미로깅
- expected `/health/heartbeat` 503 미로깅
- health handler 자체 예외나 의도하지 않은 5xx만 로깅

이제 drain 중 probe storm이 와도 로그 노이즈가 커지지 않으면서, 진짜 health endpoint 자체 장애는 놓치지 않게 됩니다.

### 1.5 threshold 집계 방식이 구현 가능한 수준으로 구체화되었습니다

`7.3 threshold 기반 drain`에서

- sliding window
- 최근 exception 시각 목록 보관
- window 밖 제외
- 정확히 threshold 도달 시 drain
- draining 이후 재승격 없음

을 적어둔 것은 매우 좋습니다. 이 정도면 구현자가 자료구조와 테스트 케이스를 바로 떠올릴 수 있습니다.

## 2. 지금 문서에서 여전히 보완하면 좋은 점

## 2.1 readiness의 `app lifecycle이 running이어야 한다`와 실제 초기 ready 판단 문구 사이를 조금 더 정리하면 좋습니다

앞부분 `2.2 Ready`에서는

- app lifecycle이 running이어야 한다.
- 필수 dependency가 ok여야 한다.
- drain 상태면 ready가 아니다.

라고 쓰여 있습니다.

그런데 뒤쪽 `7.4 dependency health 기반 drain/readiness`에서는 초기 구현에서

- DB checker가 정식으로 들어오기 전까지 ready는 app lifecycle 기준을 우선한다.
- `db`는 heartbeat 관측 필드로 노출한다.
- production-ready 정책에서는 필수 dependency가 `ok`가 아니면 ready=false로 바꾼다.

라고 되어 있습니다.

방향은 이해되지만, 지금 문서만 보면 “현재 초기 구현에서 db가 unknown/not_configured여도 ready=200인가?”를 한 번 더 해석해야 합니다.

권장 보완:
- `초기 구현에서는 필수 dependency readiness 판정을 아직 lifecycle에 포함하지 않는다` 또는
- `DB checker 도입 전까지 ready는 lifecycle 기준만 사용한다`

를 `2.2 Ready` 또는 `7.4`에 한 줄 더 강하게 써두면 좋습니다.

지금도 충분히 읽히긴 하지만, 이 부분은 구현자가 가장 먼저 질문할 만한 지점입니다.

## 2.2 `/health/live`에서 `stopping` 상태를 어떻게 볼지 한 줄 더 정하면 좋습니다

현재 문서에서는

- stopping: live는 상황에 따라 200 또는 실패 가능

이라고 되어 있습니다.

이 문장은 현실적이긴 하지만, probe 정책을 짜는 입장에서는 다소 모호합니다. 초기 문서라면 더 단순한 규칙이 나을 수 있습니다.

예를 들면 아래 둘 중 하나로 고정하는 편이 낫습니다.

- 정책 A: stopping 동안에도 live는 가능한 한 200 유지, 프로세스 종료 시점에만 실패
- 정책 B: stopping 진입 시 live 실패 허용

제 추천은 A입니다. 이유는 이 문서 전체 철학이 “즉시 죽이지 말고 ready에서 먼저 빼자”에 더 가깝기 때문입니다. live를 stopping에서 너무 일찍 깨버리면 그 철학과 약간 어긋날 수 있습니다.

## 2.3 `즉시 drain 후보`와 `threshold 기반 drain`의 우선순위를 한 줄 더 적으면 좋습니다

지금 `7.1 즉시 drain 후보`와 `7.3 threshold 기반 drain`이 나란히 있는데, 구현자는 다음을 궁금해할 수 있습니다.

- 즉시 drain 후보는 threshold를 무시하고 바로 drain인가?
- 아니면 “즉시 drain을 고려”만 하고 실제 구현은 아직 threshold만 할 건가?

문구상 `고려할 수 있는 오류`라고 되어 있어 보수적이긴 한데, 구현 범위 관점에서는 조금 애매합니다.

권장 보완:
- 이번 초기 구현에서는 threshold 기반 drain만 자동화하고, 즉시 drain 후보는 운영 정책 가이드로만 둔다
또는
- 특정 즉시 drain 후보는 `start_draining()`을 즉시 호출한다

둘 중 하나를 명시하면 좋습니다.

지금 상태로도 정책 문서로는 괜찮지만, 구현 문서로 넘어가면 이 부분이 분기점이 됩니다.

## 2.4 drain reason의 갱신 정책을 조금 더 고정하면 좋습니다

테스트 계획에는

- drain reason을 덮어쓸지 유지할지 정책을 테스트로 고정한다

라고 적혀 있습니다. 좋은 접근입니다. 다만 정책 문서 본문에도 한 줄 있으면 더 좋습니다.

제 추천:
- 최초 drain reason을 유지하고 이후 reason은 보조 로그로만 남긴다

이유:
- 운영자가 “처음 왜 drain됐는가”를 보는 것이 보통 더 중요합니다.
- draining 이후 새 예외가 들어와도 root cause보다 후속 noise일 가능성이 큽니다.

반대로 최신 reason으로 덮어쓰면 상황 해석이 흔들릴 수 있습니다.

## 2.5 heartbeat status code 정책을 한 번 더 점검할 필요가 있습니다

현재 `/health/heartbeat`는

- running/ready: 200
- draining/not_ready: 503

입니다.

이건 충분히 가능하지만, heartbeat를 “상세 관측 endpoint”로 쓸 경우엔 항상 200 + body status만 보는 설계도 흔합니다. 현재 정책이 틀렸다는 뜻은 아니고, probe/monitoring 도구에서 이 endpoint를 readiness probe처럼 재사용할 가능성이 있다면 의도를 더 분명히 적는 편이 좋습니다.

권장 보강:
- `/health/heartbeat`는 상세 상태 확인용이며 probe보다는 운영자/관측 도구 소비를 우선한다
또는
- `/health/heartbeat`는 503를 통해 unhealthy 상태를 기계적으로도 반영한다

지금 문서에는 암묵적으로 후자 뜻이 담겨 있는데, 한 줄만 더 있으면 혼동이 줄어듭니다.

## 3. 구현 관점에서 좋았던 부분

아래는 구현 단계 설계로서 좋았습니다.

- `platform/lifecycle/state.py`를 별도 모듈 후보로 둔 점
- lifecycle state에 `started_at`, `drain_started_at`, `drain_reason`, 최근 exception 기록을 함께 모으려는 점
- health endpoint를 별도 `shared/health/routes.py`로 분리 후보로 둔 점
- middleware exception path에서 lifecycle을 기록하되, health/DB checker는 순차적으로 붙이려는 점
- 테스트 계획이 상태/전이/threshold/logging까지 폭넓게 커버하는 점

특히 “state 저장소 -> health endpoint -> middleware 연결 -> DB checker” 순서는 점진적으로 붙이기 좋습니다.

## 4. 테스트 계획에 추가되면 더 좋은 항목

현재 테스트 계획도 충분히 좋지만, 아래 두세 가지가 있으면 더 안전합니다.

### 4.1 multi-worker 전제 문서화 테스트는 아니더라도 코드 주석/문서 동기화 확인

이건 자동 테스트보다 문서/코드 주석 정합성 문제에 가깝지만, 최소한 state 객체 docstring이나 module docstring에 process-local임을 명시해두는 것이 좋습니다. 문서에는 이미 들어갔으니 코드에도 같은 문장이 있으면 좋습니다.

### 4.2 drain event log payload 테스트

문서가 `lifecycle_draining_started` 이벤트 필드까지 정의했으므로, 나중 구현 시 아래를 테스트로 고정하면 좋습니다.

- event 이름
- drain_reason
- lifecycle
- error_count
- window_seconds
- timestamp 필드 존재

이건 운영 디버깅에 직접 쓰이는 contract라서 테스트 가치가 큽니다.

### 4.3 expected health 503 미로깅 테스트를 body/status 기준으로 분리

예를 들어

- `/health/ready`가 draining이라 503인 경우 로그 없음
- `/health/heartbeat`가 draining이라 503인 경우 로그 없음
- health handler 자체 exception이면 로그 있음

이 세 케이스를 분리하면 policy regression을 막기 좋습니다.

## 5. 최종 판단

이번 개정본은 “초기 drain 정책 문서”로서 승인 가능한 수준에 상당히 가깝습니다. 이전 리뷰에서 지적했던 핵심 리스크들이 실제로 많이 정리되었습니다.

유지해도 좋은 핵심 판단은 아래입니다.

- live / ready / heartbeat 분리
- lifecycle state를 process-local in-memory로 시작
- multi-worker에서는 worker-local 상태임을 인정
- automatic recovery는 이번 범위에서 제외
- middleware top-level unhandled exception만 threshold 집계
- expected health 503는 미로깅
- unexpected health handler failure만 로깅
- drain 상태에서는 readiness 503만 우선 사용하고 일반 요청 강제 503은 defer

남은 보완 포인트는 주로 “구현자가 헷갈릴 수 있는 경계”를 더 줄이는 일입니다.

우선순위 순으로 정리하면:

1. 초기 ready 판단에서 DB 상태를 실제로 어떻게 반영하는지 한 줄 더 고정
2. stopping 상태에서 live를 어떻게 볼지 좀 더 명확화
3. 즉시 drain 후보가 이번 구현 범위에서 자동 동작인지 운영 가이드인지 명시
4. drain reason overwrite 정책을 본문에도 명시
5. heartbeat endpoint의 503 의도를 한 줄 더 설명

## 6. 한 줄 결론

개정본은 확실히 좋아졌고, 지금 상태로도 좋은 설계 문서입니다. 이제 남은 것은 큰 방향 수정이 아니라, 몇몇 경계 조건을 더 고정해서 구현 시 해석 차이를 줄이는 일입니다.
