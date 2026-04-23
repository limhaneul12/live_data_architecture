"""공유 테스트 환경 설정."""

from __future__ import annotations

import os

os.environ["SERVICE_APP_NAME"] = "live-data-api"
os.environ["SERVICE_APP_ENV"] = "local"
os.environ["SERVICE_APP_VERSION"] = "0.1.0"
