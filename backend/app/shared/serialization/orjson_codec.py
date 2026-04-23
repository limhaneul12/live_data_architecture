"""공유 JSON 직렬화 helper 모듈."""

from __future__ import annotations

import orjson
from app.shared.types import JSONValue


# Broad type justified: orjson default callback은 지원하지 않는 임의 객체를 받을 수 있다.
def _json_default(value: object) -> str:
    """지원하지 않는 JSON 값을 안전하게 문자열로 변환한다.

    인자:
        value: Unsupported value passed by orjson.

    반환:
        String representation for fallback serialization.
    """
    return str(value)


def dumps_json(value: JSONValue) -> bytes:
    """호환 가능한 JSON 값을 orjson으로 직렬화한다.

    인자:
        value: JSON-compatible value.

    반환:
        Serialized UTF-8 JSON bytes.
    """
    return orjson.dumps(
        value,
        default=_json_default,
        option=orjson.OPT_UTC_Z,
    )
