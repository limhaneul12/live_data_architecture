from typing import cast

from event_generator.constants import EVENT_STREAM_KEY, EVENT_STREAM_MAXLEN
from event_generator.sinks import RedisStreamEventSink, RedisXAddClient, StdoutEventSink


class FakeRedisClient:
    def __init__(self) -> None:
        self.published: list[dict[str, object]] = []

    def xadd(
        self,
        name: str,
        fields: dict[str, str],
        *,
        id: str = "*",
        maxlen: int | None = None,
        approximate: bool = True,
    ) -> str:
        self.published.append(
            {
                "name": name,
                "fields": fields,
                "id": id,
                "maxlen": maxlen,
                "approximate": approximate,
            }
        )
        return "1-0"

    def close(self) -> None:
        return None


def test_redis_stream_sink_publishes_json_line_as_payload_field() -> None:
    client = FakeRedisClient()
    sink = RedisStreamEventSink(
        client=cast(RedisXAddClient, client),
    )

    sink.emit('{"schema_version":"web_event.v1","event_id":"evt_1"}')

    assert client.published == [
        {
            "name": EVENT_STREAM_KEY,
            "fields": {
                "payload": '{"schema_version":"web_event.v1","event_id":"evt_1"}'
            },
            "id": "*",
            "maxlen": EVENT_STREAM_MAXLEN,
            "approximate": True,
        }
    ]


def test_stdout_sink_writes_line_to_stdout(capsys) -> None:
    sink = StdoutEventSink()

    sink.emit('{"event_id":"evt_1"}')

    captured = capsys.readouterr()
    assert captured.out == '{"event_id":"evt_1"}\n'
    assert captured.err == ""
