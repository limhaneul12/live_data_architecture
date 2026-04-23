"""데이터베이스 연결 설정 모델.

이 모듈은 `.env`와 환경변수에서 데이터베이스 접속 주소를 읽는다.
모든 필드는 `DATABASE_` 접두어를 사용한다.
"""

from __future__ import annotations

from app.platform.config.common import settings_model_config
from pydantic import Field, PostgresDsn
from pydantic_settings import BaseSettings


class DatabaseConfig(BaseSettings):
    """데이터베이스 설정 모델.

    역할:
        앱이 사용할 데이터베이스 연결 문자열을 중앙화한다.
    """

    model_config = settings_model_config(env_prefix="DATABASE_")

    # 데이터베이스 연결 주소.
    db_address: PostgresDsn = Field()
