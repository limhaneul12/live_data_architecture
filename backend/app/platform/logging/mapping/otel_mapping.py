"""로그 payload를 OpenTelemetry 친화 구조로 변환하는 모듈."""

from __future__ import annotations

from dataclasses import dataclass

from app.platform.schemas.logging_schema import JsonLogPayload

type OtelAttributeValue = str | int | float | bool
type OtelAttributes = dict[str, OtelAttributeValue]


@dataclass(frozen=True, slots=True)
class OtelLogMapping:
    """로그 record로 보낼 수 있는 OpenTelemetry 중간 매핑 결과."""

    timestamp: str
    severity_text: str
    body: str
    trace_id: str | None
    span_id: str | None
    attributes: OtelAttributes


def _put_attribute(
    attributes: OtelAttributes,
    key: str,
    value: OtelAttributeValue | None,
) -> None:
    """값이 None이 아니면 primitive attribute dictionary에 넣는다.

    인자:
        attributes: 값을 넣을 attribute dictionary.
        key: attribute key.
        value: 넣을 값. None이면 생략한다.

    반환:
        없음.
    """
    if value is None:
        return
    attributes[key] = value


def payload_to_otel_log_mapping(payload: JsonLogPayload) -> OtelLogMapping:
    """로그 payload를 최소 OpenTelemetry 친화 log mapping으로 변환한다.

    인자:
        payload: 구조화된 JSON log payload.

    반환:
        exporter 연결 전 테스트 가능한 OTEL-friendly 중간 매핑 결과.
    """
    attributes: OtelAttributes = {}

    _put_attribute(attributes, "service.name", payload.service.service)
    _put_attribute(attributes, "deployment.environment.name", payload.service.env)
    _put_attribute(attributes, "service.version", payload.service.version)
    _put_attribute(attributes, "event.name", payload.event)
    _put_attribute(attributes, "app.request_id", payload.trace.request_id)
    _put_attribute(attributes, "http.request.method", payload.http.method)
    _put_attribute(attributes, "url.path", payload.http.path)
    _put_attribute(attributes, "http.response.status_code", payload.http.status_code)

    if payload.error is not None:
        _put_attribute(attributes, "exception.type", payload.error.type)
        _put_attribute(attributes, "exception.message", payload.error.message)
        _put_attribute(attributes, "exception.stacktrace", payload.error.stack)

    return OtelLogMapping(
        timestamp=payload.ts,
        severity_text=payload.level,
        body=payload.msg,
        trace_id=payload.trace.trace_id,
        span_id=payload.trace.span_id,
        attributes=attributes,
    )
