# JSON log design

## Why we used JSON logs

이 프로젝트는 이벤트 파이프라인을 구현하는 과제이기 때문에, 애플리케이션 자체 로그도
사람이 읽기 쉽고 기계가 다시 집계하기 쉬운 형태가 필요했다. 그래서 plain text 로그 대신
JSON 한 줄 로그를 기본 형식으로 잡았다.

핵심 의도는 세 가지였다.

1. 요청/배치 처리 흐름을 한 줄 단위로 추적할 수 있게 만들기
2. 에러가 나더라도 필드 이름이 고정된 구조로 남기기
3. 나중에 로그 수집기나 검색 도구로 넘겨도 바로 필드 기반 필터링이 가능하게 만들기

## What we logged

JSON 로그에는 아래 성격의 필드를 담도록 설계했다.

- 공통 실행 정보: `ts`, `level`, `logger`, `event`, `msg`
- 서비스 문맥: `service`, `env`, `version`
- 요청 문맥: `request_id`, `correlation_id`, `http_method`, `path`, `status_code`
- 추적 문맥: `trace_id`, `span_id`
- 에러 문맥: `error`

이렇게 나눈 이유는 “로그를 처음 볼 때 무엇부터 읽는가”를 기준으로 했기 때문이다.
사람은 먼저 무슨 일이 있었는지(`event`, `msg`)를 보고, 그다음 어느 요청인지
(`request_id`, `path`)를 보고, 마지막에 실패 원인(`error`)을 본다.

## Design intent

JSON 로그는 단순히 예쁘게 출력하려는 목적이 아니었다.

- HTTP 요청 로그와 background consumer 로그를 같은 포맷으로 맞춘다.
- Redis ingest, analytics SQL, health check 같은 서로 다른 기능도 같은 검색 축으로 본다.
- 장애 시 사람이 grep으로 보더라도 필드가 안정적으로 남는다.

즉, “관찰 가능한 애플리케이션”의 최소 단위로 JSON 로그를 선택한 것이다.

## Main trade-offs

- 너무 많은 필드를 넣으면 noisy 해진다.
- 너무 적게 넣으면 장애 분석이 어려워진다.

그래서 이번 과제 범위에서는 OpenTelemetry exporter나 별도 log pipeline까지는 가지 않고,
request/trace correlation이 가능한 최소 구조만 남겼다.

## What we intentionally did not do

- log shipping/aggregation stack 도입
- metric/trace backend 연동
- 고급 sampling 정책
- 사용자별 민감정보 마스킹 엔진

이번 단계에서는 “작은 파이프라인 과제에 맞는 구조화 로그”가 목표였다.
