"""구조화 JSON 로그를 위한 Pydantic payload 모델.

이 모듈은 실제로 stdout에 출력되거나 나중에 OpenTelemetry로 매핑될
로그 이벤트의 내부 계약을 정의한다. 각 모델은 로그 payload를 역할별로
쪼개어 필드가 과도하게 한 클래스에 몰리지 않도록 한다.
"""

from __future__ import annotations

from app.shared.types import JSONObject
from pydantic import BaseModel, ConfigDict, StrictInt, StrictStr


class JsonLoggingModel(BaseModel):
    """구조화 로그 모델의 공통 기반 클래스.

    역할:
        모든 logging payload 모델이 같은 Pydantic 정책을 공유하도록 한다.
        `extra="forbid"`는 정의되지 않은 필드 유입을 막고, `frozen=True`는
        생성된 로그 이벤트가 중간에 변경되지 않게 한다.

        `strict=True`는 모델 전체의 기본 안전망이다. 새 필드가 추가되더라도
        Pydantic이 문자열 숫자 등을 암묵적으로 변환하지 못하게 한다.
        `StrictStr`, `StrictInt`는 이 안전망 위에서 식별자/정수 필드의 의도를
        읽는 사람이 바로 알 수 있게 해주는 가독성 장치다.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class JsonLogServiceContext(JsonLoggingModel):
    """서비스 식별 정보를 담는 로그 context.

    역할:
        어떤 서비스/환경/버전에서 로그가 발생했는지 표현한다. 나중에
        OpenTelemetry resource attribute(`service.name`, deployment environment 등)로
        매핑하기 쉬운 단위다.
    """

    service: StrictStr
    env: StrictStr
    version: StrictStr

    def to_json_value(self) -> JSONObject:
        """서비스 context를 JSON 직렬화 가능한 dictionary로 변환한다.

        반환:
            stdout JSON 로그에 병합될 서비스 필드 dictionary.

        키:
            service: 로그를 생성한 서비스 이름.
            env: 로그를 생성한 실행 환경(local/dev/stage/prod 등).
            version: 로그를 생성한 애플리케이션 버전.
        """
        return {
            "service": self.service,
            "env": self.env,
            "version": self.version,
        }


class JsonLogTraceContext(JsonLoggingModel):
    """요청 식별자와 trace 정보를 담는 로그 context.

    역할:
        `x-request-id`, correlation id, trace id, span id처럼 여러 로그를 하나의
        요청/trace로 묶기 위한 정보를 표현한다. 장애 분석 시 로그와 trace를
        연결하는 핵심 context다.
    """

    request_id: StrictStr | None
    correlation_id: StrictStr | None
    trace_id: StrictStr | None
    span_id: StrictStr | None
    tracer_error: StrictStr | None

    def to_json_value(self) -> JSONObject:
        """추적 context를 JSON 직렬화 가능한 dictionary로 변환한다.

        반환:
            stdout JSON 로그에 병합될 trace/correlation 필드 dictionary.

        키:
            request_id: 단일 HTTP 요청을 식별하는 값. 없으면 middleware에서 생성한다.
            correlation_id: 여러 로그/작업을 같은 흐름으로 묶는 상관관계 식별자.
            trace_id: OpenTelemetry trace 식별자 또는 `x-trace-id` 헤더 값.
            span_id: OpenTelemetry span 식별자.
            tracer_error: tracer 연동/기록 중 발생한 instrumentation 오류 메시지.
        """
        return {
            "request_id": self.request_id,
            "correlation_id": self.correlation_id,
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "tracer_error": self.tracer_error,
        }


class JsonLogHttpContext(JsonLoggingModel):
    """요청/응답 HTTP 정보를 담는 로그 context.

    역할:
        HTTP method, path, status code처럼 API 요청 로그에서 공통으로 필요한
        정보를 표현한다. 나중에 OpenTelemetry HTTP semantic convention으로
        매핑하기 쉬운 단위다.
    """

    method: StrictStr | None
    path: StrictStr | None
    status_code: StrictInt | None

    def to_json_value(self) -> JSONObject:
        """요청 HTTP context를 JSON 직렬화 가능한 dictionary로 변환한다.

        반환:
            stdout JSON 로그에 병합될 HTTP 필드 dictionary.

        키:
            http_method: 요청 HTTP method(GET/POST 등).
            path: query string을 제외한 요청 path.
            status_code: 응답 HTTP status code.
        """
        return {
            "http_method": self.method,
            "path": self.path,
            "status_code": self.status_code,
        }


class JsonLogError(JsonLoggingModel):
    """예외 정보를 담는 로그 payload.

    역할:
        에러 로그에서 예외 타입, 메시지, stack trace를 구조화한다. 일반 로그에서는
        `None`으로 남기고, 실패 로그에서만 채운다.
    """

    type: StrictStr | None
    message: StrictStr | None
    stack: StrictStr

    def to_json_value(self) -> JSONObject:
        """에러 payload를 JSON 직렬화 가능한 dictionary로 변환한다.

        반환:
            stdout JSON 로그의 `error` 필드에 들어갈 dictionary.

        키:
            type: 예외 클래스 이름.
            message: 예외 메시지.
            stack: traceback 전체 문자열.
        """
        return {
            "type": self.type,
            "message": self.message,
            "stack": self.stack,
        }


class JsonLogPayload(JsonLoggingModel):
    """하나의 구조화 JSON 로그 이벤트 전체를 표현하는 payload.

    역할:
        formatter가 최종적으로 출력할 로그 이벤트의 표준 계약이다. 내부적으로는
        service/trace/http/error context로 나누어 관리하지만, `to_json_value()`에서는
        기존 로그 검색과 운영 도구에서 다루기 쉬운 flat JSON 구조로 펼친다.
    """

    ts: StrictStr
    level: StrictStr
    logger: StrictStr
    event: StrictStr
    msg: StrictStr
    func: StrictStr | None
    duration_ms: float | None
    service: JsonLogServiceContext
    trace: JsonLogTraceContext
    http: JsonLogHttpContext
    error: JsonLogError | None

    def _base_json_value(self) -> JSONObject:
        """로그 payload의 최상위 공통 필드를 JSON dictionary로 변환한다.

        반환:
            context 병합 전 기본 로그 필드 dictionary.
        """
        return {
            "ts": self.ts,
            "level": self.level,
            "logger": self.logger,
            "event": self.event,
            "msg": self.msg,
            "func": self.func,
            "duration_ms": self.duration_ms,
        }

    def _error_json_value(self) -> JSONObject | None:
        """에러 context를 JSON dictionary로 변환한다.

        반환:
            실패 로그의 error dictionary. 일반 로그는 None.
        """
        if self.error is None:
            return None
        return self.error.to_json_value()

    def to_json_value(self) -> JSONObject:
        """로그 payload를 stdout용 flat JSON dictionary로 변환한다.

        반환:
            orjson으로 직렬화 가능한 flat log dictionary.
        """
        return {
            **self._base_json_value(),
            **self.service.to_json_value(),
            **self.trace.to_json_value(),
            **self.http.to_json_value(),
            "error": self._error_json_value(),
        }
