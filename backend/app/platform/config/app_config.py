"""서비스 공통 앱 설정 모델.

이 모듈은 `.env`와 환경변수에서 서비스 공통 설정을 읽는다.
모든 필드는 `SERVICE_` 접두어를 사용한다.
"""

from __future__ import annotations

from typing import Literal

from app.platform.config.common import settings_model_config
from pydantic import Field
from pydantic_settings import BaseSettings


class AppConfig(BaseSettings):
    """서비스 공통 설정 모델.

    역할:
        앱 이름, 실행 환경, 버전, 로그 레벨 같은 서비스 전역 설정을 중앙화한다.
    """

    model_config = settings_model_config(env_prefix="SERVICE_")

    # 서비스 식별 이름. JSON logging과 운영 식별에 사용한다.
    app_name: str = Field()
    # 실행 환경. 현재 정책은 local/stage/prod 세 가지만 허용한다.
    app_env: Literal["local", "stage", "prod"] = Field()
    # 애플리케이션 버전 문자열.
    app_version: str = Field()
    # Python logging level 이름.
    app_log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field()
    # local/demo 환경에서 Redis Stream consumer background task를 실행할지 여부.
    event_consumer_enabled: bool = Field(default=False)
