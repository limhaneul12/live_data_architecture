"""로그 레코드 extra 필드를 타입에 맞게 읽는 helper 모듈."""

from __future__ import annotations

import logging


def log_record_extra_str(
    *,
    record: logging.LogRecord,
    key: str,
    default: str | None = None,
) -> str | None:
    """문자열 extra 필드를 읽는다.

    인자:
        record: Python logging record.
        key: extra 필드 이름.
        default: 필드가 없거나 문자열이 아닐 때 반환할 값.

    반환:
        문자열 extra 값 또는 기본값.
    """
    value = record.__dict__.get(key)
    if isinstance(value, str):
        return value
    return default


def log_record_extra_str_or_default(
    *,
    record: logging.LogRecord,
    key: str,
    default: str,
) -> str:
    """문자열 extra 필드를 필수 fallback과 함께 읽는다.

    인자:
        record: Python logging record.
        key: extra 필드 이름.
        default: 필드가 없거나 문자열이 아닐 때 반환할 필수 기본값.

    반환:
        문자열 extra 값 또는 필수 기본값.
    """
    value = log_record_extra_str(record=record, key=key, default=default)
    if value is None:
        return default
    return value


def log_record_extra_float(
    *,
    record: logging.LogRecord,
    key: str,
    default: float | None = None,
) -> float | None:
    """숫자 extra 필드를 float로 읽는다.

    인자:
        record: Python logging record.
        key: extra 필드 이름.
        default: 필드가 없거나 숫자가 아닐 때 반환할 값.

    반환:
        float로 변환된 숫자 extra 값 또는 기본값.
    """
    value = record.__dict__.get(key)
    if isinstance(value, int | float) and not isinstance(value, bool):
        return float(value)
    return default


def log_record_extra_int(
    *,
    record: logging.LogRecord,
    key: str,
    default: int | None = None,
) -> int | None:
    """정수 extra 필드를 읽는다.

    인자:
        record: Python logging record.
        key: extra 필드 이름.
        default: 필드가 없거나 정수가 아닐 때 반환할 값.

    반환:
        정수 extra 값 또는 기본값.
    """
    value = record.__dict__.get(key)
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    return default
