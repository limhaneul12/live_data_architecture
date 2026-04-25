# Drain design

## Why drain existed

drain은 “지금 이 서비스가 정상 처리 상태인지, 종료 준비 상태인지”를 명확히 표현하기 위해
도입했다.

이 프로젝트에는 background consumer가 있고, Redis와 PostgreSQL 같은 외부 의존성이 있다.
따라서 단순히 프로세스가 떠 있다는 사실만으로는 서비스가 안전하게 요청을 받을 수 있는지
판단하기 어렵다.

## Design intent

drain의 목적은 복잡한 orchestration을 만드는 것이 아니라, 현재 상태를 건강 체크 응답에
드러내는 것이었다.

즉:

- 앱이 정상 상태면 `ok`
- 종료 준비 중이면 `draining`
- 의존성이 꺼져 있으면 `disabled`

처럼, 운영자가 지금 상태를 바로 이해할 수 있게 하는 것이 핵심이었다.

## How we thought about dependencies

이번 과제에서 drain은 app 단독 상태가 아니라 dependency 상태와도 연결된다.

- Redis가 consumer 경로에 포함되면 health에 보여야 한다.
- PostgreSQL이 ingest/storage 경로에 포함되면 health에 보여야 한다.
- drain 전환 시 app만 draining이고 dependency는 ok인 식의 모호한 상태를 피하고 싶었다.

그래서 drain 상태에서는 Redis/database status도 같이 `draining`으로 내려가게 맞췄다.

## Why we kept it simple

초기에는 자동 drain, 500 연동 drain, 복구 자동화까지 갈 수도 있었다.
하지만 이번 과제는 운영 플랫폼이 아니라 이벤트 파이프라인 구현이 핵심이었다.

그래서 drain은 아래 수준까지만 유지했다.

- 명시적인 상태 표현
- health/readiness 응답 반영
- dependency 상태와 일관된 표시

의도적으로 하지 않은 것:

- 500 에러 기반 자동 drain
- 일반 요청 일괄 503 차단
- 고급 장애 복구 정책
- distributed drain coordination

이번 단계의 drain은 “과제 범위에 맞는 운영 상태 표현”이라고 보는 것이 맞다.
