# 500 error drain policy review

전체적으로는 적절합니다. 이 문서는 “500은 모두 심각하지만, 모두가 즉시 drain 사유는 아니다”라는 핵심 구분을 꽤 명확하게 잡고 있습니다. 특히 이전 `drain_policy.md`와도 큰 충돌 없이 잘 이어집니다.

좋은 점부터 말하면, 이 문서는 다음 세 가지를 잘 분리하고 있습니다.

- 500 자체는 개별 요청 실패 signal이라는 점
- drain은 process lifecycle 결정이라는 점
- 초기 구현은 threshold 기반으로만 시작하고, exception taxonomy 기반 즉시 drain은 defer한다는 점

이 세 축이 분리되어 있어서 정책이 과도하게 공격적이지 않고, 동시에 운영상 중요한 실패를 가볍게 보지도 않습니다. 방향 자체는 실용적입니다.

다만 몇 군데는 더 명확히 하면 훨씬 좋아집니다. 특히 아래가 중요합니다.

- “모든 500”과 “middleware top-level unhandled exception”의 관계를 더 분명히 써야 함
- metric/alert 후보라고 했을 때 어느 레벨까지를 이번 범위에 포함하는지 경계를 조금 더 분명히 해야 함
- drain 후보 예시와 실제 자동 drain 기준(threshold only) 사이를 한 번 더 정리하면 구현자가 덜 헷갈림
- 문서 참조 경로에 오타 가능성이 있음

아래처럼 상세히 리뷰드립니다.

## 1. 좋은 점

### 1.1 500과 drain을 분리한 구조가 좋습니다

`3. 500 error와 drain의 차이`는 문서의 핵심이고, 이 부분이 가장 잘 되어 있습니다.

특히 아래 표는 좋습니다.

- 500 error signal = 개별 요청 실패
- drain decision = process가 새 트래픽을 계속 받아도 되는지 판단

이 구분이 있어야 운영 중 “500이 났는데 왜 바로 readiness를 내리지 않았나?” 혹은 반대로 “왜 단일 버그 때문에 서비스 전체를 빼버렸나?” 같은 질문에 답할 수 있습니다.

### 1.2 단발 500과 반복/전역 손상 후보를 나눈 점이 적절합니다

`4. drain하지 않는 500 후보`와 `5. drain 후보가 되는 500`의 구분도 합리적입니다.

좋은 이유:
- 단발 payload edge case나 외부 API timeout 1회 같은 것은 서비스 전체 lifecycle 전환까지 갈 이유가 약함
- 반면 schema mismatch, invariant 붕괴, 필수 dependency 붕괴 같은 것은 process-level 위험 신호일 수 있음

즉 문서가 “500은 다 똑같지 않다”를 잘 설명하고 있습니다.

### 1.3 초기에는 threshold 기반만 도입한다는 점이 좋습니다

`7. 즉시 drain 정책은 defer`는 매우 좋은 판단입니다.

현재 단계에서 `FATAL_EXCEPTION_TYPES`를 성급히 만들면 다음 문제가 생깁니다.

- 예외 taxonomy가 아직 안정적이지 않을 수 있음
- 이름만 fatal이고 실제로는 recoverable일 수 있음
- 코드보다 문서가 앞서가며 오판 위험이 커짐

따라서 threshold 기반 drain으로 먼저 시작하고, taxonomy는 나중에 운영 경험을 바탕으로 추가하겠다는 방향은 타당합니다.

### 1.4 기록 정책 최소 필드가 실용적입니다

`8. 기록 정책`의 최소 필드 목록도 좋습니다.

특히 아래 필드가 명시된 점이 좋습니다.

- `event`
- `status_code=500`
- `request_id`, `trace_id`, `span_id`
- `http_method`, `path`, `duration_ms`
- `error.type`, `error.message`, `error.stack`

이 정도면 500 분석에 필요한 기본 관측성 계약으로 충분히 쓸 수 있습니다.

## 2. 가장 먼저 보완하면 좋은 부분

## 2.1 “모든 500”과 “threshold 집계 대상”의 관계를 더 또렷하게 적는 것이 좋습니다

현재 문서 초반에서는 반복적으로 “모든 500은 치명적인 error signal”이라고 말합니다. 이 표현 자체는 운영 감각상 맞습니다. 그런데 뒤에 가면 실제 drain threshold 집계 대상은 이렇게 제한됩니다.

- `middleware top-level unhandled exception`

즉, 실질적으로는 다음 두 문장이 동시에 존재합니다.

- 모든 500은 기록/추적/관측 대상이다.
- 하지만 drain threshold 집계는 모든 500이 아니라 middleware top-level unhandled exception만 대상으로 한다.

이 둘은 양립 가능하지만, 지금 문서에서는 독자가 한 번 추론해야 합니다.

권장 보강 문장:

- 모든 500 response는 error signal로 기록한다.
- 다만 초기 drain threshold 집계는 그중에서도 middleware top-level unhandled exception에 의해 발생한 500만 대상으로 한다.

이 한 줄이 들어가면 구현자가 훨씬 덜 헷갈립니다.

왜 중요하냐면, 실제 서비스에서는 500이더라도
- framework가 특정 예외를 500 response로 변환했지만 known class일 수 있고
- health endpoint의 expected 상태 보고와 섞이면 안 되고
- 장차 domain/application 예외 taxonomy가 생기면 500의 종류가 더 다양해질 수 있기 때문입니다.

## 2.2 `500 = error log + metric + trace correlation + alert 후보`의 범위를 조금 더 명확히 하면 좋습니다

이 문구는 방향상 맞습니다. 다만 “이번 문서가 정책인지, 즉시 구현 범위인지”가 살짝 섞여 보입니다.

예를 들어 지금 backend에는
- error log는 바로 가능할 수 있지만
- metric은 아직 exporter/collector/aggregation이 없을 수 있고
- alert는 더더욱 운영 스택이 정리돼야 함

즉 문서에서 이걸 “정책 목표”로 쓰는 것은 좋지만, 구현 범위와 혼동되지 않게 한 줄 보강하면 좋습니다.

권장 표현:
- 초기 구현에서는 모든 500을 구조화 error log로 남긴다.
- metric/alert 연동은 observability stack 도입 시 순차적으로 추가한다.

이렇게 하면 문서가 더 현실적이 됩니다.

## 2.3 `drain 후보가 되는 500`과 `즉시 drain 정책은 defer`의 관계를 더 분명히 해주면 좋습니다

현재 `5. drain 후보가 되는 500`에는 다음처럼 강한 사례들이 들어 있습니다.

- DB schema mismatch
- 필수 설정 누락
- 내부 invariant 붕괴
- 데이터 무결성 손상
- 필수 resource 문제

독자가 읽으면 “그럼 이런 건 바로 drain해야 하는 것 아닌가?”라고 느낄 수 있습니다.

그런데 `7. 즉시 drain 정책은 defer`에서는 특정 exception type 기반 즉시 drain을 아직 도입하지 않는다고 합니다. 이것도 맞는 판단입니다.

문제는 둘 사이의 다리 문장이 조금 부족하다는 점입니다.

권장 보강:
- 위 사례들은 운영적으로는 drain 후보로 본다.
- 그러나 초기 자동화 구현은 threshold 기반만 도입한다.
- 즉시 drain이 필요한 치명적 사례는 우선 수동 운영 판단 또는 향후 exception taxonomy 도입 이후 자동화한다.

이렇게 적으면 정책 가이드와 구현 범위가 더 잘 분리됩니다.

## 2.4 `downstream 일시 장애`를 drain하지 않는 500 후보에 넣은 것은 맞지만, dependency health 정책과의 연결 문장이 있으면 좋습니다

`4. drain하지 않는 500 후보`에 `downstream 일시 장애`가 들어 있는데, 이건 맞습니다. 다만 `drain_policy.md`에서는 dependency failure와 readiness 실패를 별도로 다루고 있으므로, 두 문서를 연결하는 문장이 있으면 더 좋습니다.

예를 들면:
- 단발 downstream 장애는 즉시 drain하지 않는다.
- 그러나 필수 dependency의 반복적/장기적 실패는 readiness 실패 또는 drain 승격 후보가 된다.

지금도 두 문서를 함께 읽으면 이해되지만, 이 문서 단독으로도 연결감이 있으면 더 좋습니다.

## 2.5 참조 경로 정리 완료

`8. 기록 정책`의 마지막 줄은 현재 다음 실제 경로를 가리킨다.

- `docs/logging_structure/logging_error_stack_policy.md`

초기 리뷰 당시에는 `logging_strcture` 오타 가능성이 있었지만, 현재 문서 폴더는 `logging_structure`로 정리되었다.

## 3. 정책적으로 좋은데, 한 줄만 더 있으면 좋은 부분

## 3.1 drain 이후 추가 500을 어떻게 볼지 한 줄 있으면 좋습니다

현재 threshold 도달 시 drain한다고만 되어 있고, drain 이후의 500은 암묵적으로 계속 error log로 남을 것으로 보입니다. 이건 자연스럽지만, 정책 문서에 한 줄 있으면 더 좋습니다.

예:
- drain 이후에도 개별 500은 계속 error signal로 기록한다.
- 다만 drain 상태는 이미 시작되었으므로 추가 500은 상태 전이를 다시 유발하지 않는다.

이건 `drain_policy.md`와도 정합적입니다.

## 3.2 “모든 500은 alert 후보”의 레벨링을 나중에 분리할 가능성을 적어두면 좋습니다

운영적으로는 모든 500을 다 alert로 보내면 noisy할 수 있습니다. 지금 문서의 “alert 후보”라는 표현은 괜찮지만, 나중에 아래처럼 레벨링할 수 있다는 메모가 있으면 더 좋습니다.

- 단발 500: 집계/대시보드
- 반복 500: 경고 알림
- drain 승격 500 cluster: 강한 알림

지금 꼭 추가해야 하는 건 아니지만, 정책 진화 방향으로는 유용합니다.

## 4. 테스트 기준은 적절합니다

`10. 테스트 기준`도 전반적으로 좋습니다. 특히 아래가 적절합니다.

- 단발 500은 drain하지 않음
- threshold 미만 반복 500은 drain하지 않음
- sliding window 밖 제외
- threshold 도달 시 drain
- drain 후 ready=503, live=200 유지
- 모든 500은 error log
- drain 전환 시 lifecycle event log

추가로 하나만 더 권하면:

- threshold 집계 대상이 아닌 500은 error log는 남지만 drain 카운트에는 포함되지 않는지 검증

예를 들어 장차 known exception이 500으로 응답되는 경로가 생길 수 있으므로, threshold 집계와 logging 집계가 분리된다는 점을 테스트로 고정하면 더 튼튼합니다.

## 5. 최종 판단

제 판단으로는 이 문서는 충분히 적절한 정책 문서입니다. 특히 아래 판단들은 유지해도 좋습니다.

- 모든 500을 가볍게 보지 않음
- 하지만 단발 500로 즉시 drain하지 않음
- drain은 process lifecycle 판단으로 더 높은 기준을 둠
- 초기 자동화는 threshold 기반만 사용
- 즉시 drain exception taxonomy는 defer
- 모든 500은 구조화 error log 대상으로 삼음
- threshold 초과 시 별도 lifecycle event를 남김

보완 우선순위를 정리하면 아래와 같습니다.

1. “모든 500”과 “threshold 집계 대상은 middleware top-level unhandled exception만”의 관계를 명시
2. metric/alert는 정책 목표인지 이번 구현 범위인지 구분
3. `drain 후보`와 `즉시 drain defer`의 연결 문장 추가
4. downstream 일시 장애와 dependency health/readiness 정책 연결 보강
5. 문서 참조 경로 오타 확인

## 6. 한 줄 결론

문서 방향은 적절하고 실용적입니다. 다만 “모든 500을 기록한다”와 “그중 어떤 500만 drain 판단에 사용한다”의 경계를 한 번만 더 또렷하게 써주면, 구현과 운영에서 훨씬 덜 흔들리는 정책 문서가 됩니다.
