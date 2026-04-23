# Logging error stack policy

작성일: 2026-04-23  
대상: backend JSON error log의 `error.stack` 출력 정책

## 1. 목적

에러 로그의 stack trace는 개발/디버깅에는 매우 유용하지만, 운영 환경에서는 다음 위험이 있다.

- 내부 코드 구조 노출
- 예외 메시지나 stack 주변 context에 민감정보가 섞일 가능성
- 반복 에러 발생 시 로그 크기와 수집 비용 증가
- OpenTelemetry/exporter 연동 시 중복 exception 정보 전송 가능성

따라서 stack trace 출력 여부를 환경에 따라 명확히 제한한다.

## 2. 현재 로그 error 구조

에러 로그는 다음 구조를 유지한다.

```json
{
  "error": {
    "type": "ValueError",
    "message": "...",
    "stack": "Traceback ..."
  }
}
```

`error.type`과 `error.message`는 모든 환경에서 유지한다.  
`error.stack`은 환경 정책에 따라 전체 traceback 또는 빈 문자열이 된다.

## 3. 정책

### 3.1 stack 포함 환경

다음 환경에서는 stack trace를 포함한다.

```text
local
dev
test
stage
```

이유:

- 개발/스테이징에서는 디버깅 속도가 중요하다.
- test에서는 현재 formatter 테스트가 stack 생성 경로를 보호해야 한다.

### 3.2 stack 제외 환경

다음 환경에서는 stack trace를 제외한다.

```text
prod
production
```

이유:

- production 로그에서 민감정보와 내부 구현 노출 위험을 줄인다.
- 반복 장애 시 로그 수집 비용 폭증을 줄인다.

### 3.3 알 수 없는 환경

`SERVICE_APP_ENV`는 이미 필수 환경변수다.  
알 수 없는 값은 일단 stack trace를 제외한다.

이유:

- 관측성 로그에서는 모르는 환경일수록 보수적으로 동작해야 한다.
- 잘못된 환경명 때문에 production에서 stack이 노출되는 것을 피한다.

## 4. 구현 원칙

- 별도 환경변수를 새로 추가하지 않는다.
- 이미 필수인 `SERVICE_APP_ENV`로 stack 포함 여부를 결정한다.
- `JsonLogError` schema는 유지한다.
- stack을 제외하는 경우에도 `error.stack` key는 유지하고 빈 문자열을 넣는다.
- `error.type`, `error.message`는 유지한다.

## 5. 나중에 검토할 항목

이번 패스에서는 단순 환경 기반 정책만 적용한다.  
운영 전에는 아래를 추가 검토한다.

- stack 길이 제한
- PII redaction
- error sampling
- OpenTelemetry exception event와 중복 여부
- logger별 stack 포함 정책
