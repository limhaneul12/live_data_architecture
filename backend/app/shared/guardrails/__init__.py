"""공유 guardrail 실행 helper 모듈."""

from __future__ import annotations

from app.shared.guardrails import (
    check_broad_types,
    check_getattr_usage as check_dynamic_attribute_usage,
    check_lazy_import_usage,
)


def ensure_broad_types_clean() -> None:
    """광범위 타입 사용 가드를 실행한다."""
    check_broad_types.ensure_clean()


def ensure_dynamic_attribute_usage_clean() -> None:
    """동적 attribute 접근 가드를 실행한다."""
    check_dynamic_attribute_usage.ensure_clean()


def ensure_lazy_import_usage_clean() -> None:
    """지연 import 사용 가드를 실행한다."""
    check_lazy_import_usage.ensure_clean()


def ensure_getattr_usage_clean() -> None:
    """기존 호환용 이름으로 동적 attribute 접근 가드를 실행한다."""
    ensure_dynamic_attribute_usage_clean()


def ensure_shared_guardrails_clean() -> None:
    """공유 guardrail 묶음을 모두 실행한다."""
    ensure_broad_types_clean()
    ensure_dynamic_attribute_usage_clean()
    ensure_lazy_import_usage_clean()


__all__ = [
    "ensure_broad_types_clean",
    "ensure_dynamic_attribute_usage_clean",
    "ensure_getattr_usage_clean",
    "ensure_lazy_import_usage_clean",
    "ensure_shared_guardrails_clean",
]
