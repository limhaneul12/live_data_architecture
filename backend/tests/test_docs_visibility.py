from typing import Literal

from app.main import create_app
from app.platform.config import AppConfig
from fastapi.testclient import TestClient


def _app_config(env: Literal["local", "stage", "prod"]) -> AppConfig:
    return AppConfig(
        app_name="live-data-api",
        app_env=env,
        app_version="0.1.0",
        app_log_level="INFO",
    )


def test_docs_redoc_and_openapi_are_available_in_local() -> None:
    app = create_app(_app_config("local"))

    with TestClient(app) as client:
        docs_response = client.get("/docs")
        redoc_response = client.get("/redoc")
        openapi_response = client.get("/openapi.json")

    assert docs_response.status_code == 200
    assert redoc_response.status_code == 200
    assert openapi_response.status_code == 200


def test_docs_redoc_and_openapi_are_blocked_in_stage() -> None:
    app = create_app(_app_config("stage"))

    with TestClient(app) as client:
        docs_response = client.get("/docs")
        redoc_response = client.get("/redoc")
        openapi_response = client.get("/openapi.json")

    assert docs_response.status_code == 404
    assert redoc_response.status_code == 404
    assert openapi_response.status_code == 404


def test_docs_redoc_and_openapi_are_blocked_in_prod() -> None:
    app = create_app(_app_config("prod"))

    with TestClient(app) as client:
        docs_response = client.get("/docs")
        redoc_response = client.get("/redoc")
        openapi_response = client.get("/openapi.json")

    assert docs_response.status_code == 404
    assert redoc_response.status_code == 404
    assert openapi_response.status_code == 404
