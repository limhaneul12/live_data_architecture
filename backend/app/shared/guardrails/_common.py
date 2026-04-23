"""공유 guardrail 공통 유틸리티 모듈."""

from __future__ import annotations

import ast
from pathlib import Path

TYPE_JUSTIFICATION_MARKERS = (
    "Any justified:",
    "Broad type justified:",
)
DYNAMIC_ATTRIBUTE_JUSTIFICATION_MARKERS = (
    "getattr justified:",
    "hasattr justified:",
    "dynamic attribute justified:",
)
LAZY_IMPORT_JUSTIFICATION_MARKERS = (
    "lazy import justified:",
    "local import justified:",
)


def resolve_backend_root(reference_file: Path, backend_root: Path | None) -> Path:
    """가드 검사에 사용할 backend 루트를 결정한다.

    인자:
        reference_file: 현재 가드 파일 경로.
        backend_root: 호출자가 명시적으로 넘긴 backend 루트. 없으면 reference 기준으로 계산한다.

    반환:
        검사 대상이 되는 backend 루트 경로.
    """
    return backend_root or reference_file.resolve().parents[3]


def should_check(path: Path, *, backend_root: Path) -> bool:
    """주어진 파일이 가드 검사 대상인지 판단한다.

    인자:
        path: 검사 후보 파일 경로.
        backend_root: backend 루트 경로.

    반환:
        검사 대상이면 ``True``, 아니면 ``False``.
    """
    try:
        relative = path.relative_to(backend_root)
    except ValueError:
        return False
    return (
        path.suffix == ".py"
        and relative.parts[0] == "app"
        and "tests" not in relative.parts
        and not (
            relative.parts[:3] == ("app", "shared", "guardrails")
            and path.name.startswith("check_")
        )
    )


def iter_guard_target_paths(
    *, reference_file: Path, backend_root: Path | None = None
) -> list[Path]:
    """가드가 순회해야 할 backend 앱 파일 목록을 수집한다.

    인자:
        reference_file: 현재 가드 파일 경로.
        backend_root: 선택적 backend 루트 경로.

    반환:
        검사 대상 Python 파일 목록.
    """
    resolved_root = resolve_backend_root(reference_file, backend_root)
    return [
        path
        for path in resolved_root.rglob("*.py")
        if should_check(path, backend_root=resolved_root)
    ]


def parse_module(path: Path) -> ast.AST:
    """소스 Python 파일을 AST로 파싱한다.

    인자:
        path: 파싱할 Python 파일 경로.

    반환:
        파싱된 AST 루트 노드.
    """
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def has_justification(
    *,
    lines: list[str],
    lineno: int,
    markers: tuple[str, ...],
) -> bool:
    """지정한 줄 근처에 정당화 주석이 있는지 확인한다.

    인자:
        lines: 원본 파일의 줄 목록.
        lineno: 검사 대상 줄 번호(1-indexed).
        markers: 허용 정당화 마커 문자열 목록.

    반환:
        정당화 주석이 있으면 ``True``, 없으면 ``False``.
    """
    current_line = lines[lineno - 1]
    if any(marker in current_line for marker in markers):
        return True

    index = lineno - 2
    while index >= 0:
        stripped = lines[index].strip()
        if not stripped:
            index -= 1
            continue
        if stripped.startswith("#"):
            if any(marker in stripped for marker in markers):
                return True
            index -= 1
            continue
        break
    return False
