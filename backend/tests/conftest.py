"""공유 테스트 환경 설정."""

from __future__ import annotations

import os

os.environ["SERVICE_APP_NAME"] = "live-data-api"
os.environ["SERVICE_APP_ENV"] = "local"
os.environ["SERVICE_APP_VERSION"] = "0.1.0"
os.environ["SERVICE_APP_LOG_LEVEL"] = "INFO"
os.environ["DATABASE_DB_ADDRESS"] = (
    "postgresql://live_data:live_data@localhost:5432/live_data"
)
os.environ["STREAM_REDIS_URL"] = "redis://localhost:6379/0"
os.environ["STREAM_REDIS_MODE"] = "single"
os.environ["STREAM_BATCH_SIZE"] = "100"
os.environ["STREAM_BLOCK_MS"] = "1000"
