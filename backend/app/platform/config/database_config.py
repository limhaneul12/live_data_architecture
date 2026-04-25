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


class AnalyticsDatabaseConfig(BaseSettings):
    """Analytics read database settings.

    역할:
        SQL Lab과 structured Explore query가 사용할 읽기 전용 데이터베이스
        연결 문자열을 선택적으로 분리한다.
    """

    model_config = settings_model_config(env_prefix="ANALYTICS_DATABASE_")

    db_address: PostgresDsn | None = Field(default=None)


def resolve_analytics_database_address(
    *,
    database_config: DatabaseConfig,
    analytics_database_config: AnalyticsDatabaseConfig,
) -> PostgresDsn:
    """Analytics query용 database address를 결정한다.

    Args:
        database_config: 기본 writer/consumer 데이터베이스 설정.
        analytics_database_config: 선택적 analytics read-only 데이터베이스 설정.

    Returns:
        analytics 전용 주소가 있으면 그 값을, 없으면 기본 데이터베이스 주소를 반환한다.
    """
    if analytics_database_config.db_address is None:
        return database_config.db_address
    return analytics_database_config.db_address
