"""공유 FastAPI middleware export 모듈."""

from app.platform.middleware.request_logging import install_request_logging_middleware

__all__ = ["install_request_logging_middleware"]
