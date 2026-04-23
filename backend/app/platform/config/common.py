"""플랫폼 설정 모델 공통 helper 모듈."""

from __future__ import annotations

from pydantic_settings import SettingsConfigDict


def settings_model_config(*, env_prefix: str) -> SettingsConfigDict:
    """공통 SettingsConfigDict를 만든다.

    인자:
        env_prefix: 환경변수 접두어.

    반환:
        `.env` 기반 설정을 읽는 SettingsConfigDict.
    """
    return SettingsConfigDict(
        env_prefix=env_prefix,
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
