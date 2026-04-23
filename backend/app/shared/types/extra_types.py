"""공유 타입 alias 모듈."""

from __future__ import annotations

type JSONObject = dict[str, JSONValue]
type JSONValue = str | int | float | bool | None | list[JSONValue] | JSONObject
