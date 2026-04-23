from app.main import app
from fastapi.testclient import TestClient


def test_health_live_returns_ok_status() -> None:
    with TestClient(app) as client:
        response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
