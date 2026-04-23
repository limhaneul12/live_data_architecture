from app.main import healthcheck


def test_healthcheck_returns_ok_status() -> None:
    payload = healthcheck()
    assert payload == {"status": "ok"}
