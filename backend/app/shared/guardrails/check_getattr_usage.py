"""문법 트리(AST) 기반 동적 attribute 접근 가드."""

from __future__ import annotations

import ast
from pathlib import Path

from app.shared.guardrails._common import (
    DYNAMIC_ATTRIBUTE_JUSTIFICATION_MARKERS,
    has_justification,
    iter_guard_target_paths,
    parse_module,
)

FORBIDDEN_DYNAMIC_ATTRIBUTE_CALLS = {"getattr", "hasattr"}


class DynamicAttributeVisitor(ast.NodeVisitor):
    """동적 attribute 호출 위반을 수집한다."""

    def __init__(self, *, path: Path, lines: list[str]) -> None:
        """동적 attribute visitor를 초기화한다.

        인자:
            path: 현재 검사 중인 파일 경로.
            lines: 파일 원본 줄 목록.

        반환:
            없음.
        """
        self._path = path
        self._lines = lines
        self.failures: list[str] = []

    def visit_Call(self, node: ast.Call) -> None:
        """동적 attribute 호출을 찾아 정당화 여부를 검사한다.

        인자:
            node: 함수 호출 AST 노드.

        반환:
            없음.
        """
        if not isinstance(node.func, ast.Name):
            self.generic_visit(node)
            return

        call_name = node.func.id
        if call_name not in FORBIDDEN_DYNAMIC_ATTRIBUTE_CALLS:
            self.generic_visit(node)
            return

        if has_justification(
            lines=self._lines,
            lineno=node.lineno,
            markers=DYNAMIC_ATTRIBUTE_JUSTIFICATION_MARKERS,
        ):
            self.generic_visit(node)
            return

        self.failures.append(
            f"{self._path}:{node.lineno}: {call_name} usage without justification"
        )
        self.generic_visit(node)


def collect_failures(backend_root: Path | None = None) -> list[str]:
    """동적 attribute 접근 가드 위반 목록을 수집한다.

    인자:
        backend_root: 선택적 backend 루트 경로.

    반환:
        위반 메시지 목록.
    """
    failures: list[str] = []
    for path in iter_guard_target_paths(
        reference_file=Path(__file__), backend_root=backend_root
    ):
        lines = path.read_text(encoding="utf-8").splitlines()
        visitor = DynamicAttributeVisitor(path=path, lines=lines)
        visitor.visit(parse_module(path))
        failures.extend(visitor.failures)
    return failures


def ensure_clean(backend_root: Path | None = None) -> None:
    """동적 attribute 접근 위반이 있으면 예외를 발생시킨다.

    인자:
        backend_root: 선택적 backend 루트 경로.

    반환:
        없음.
    """
    failures = collect_failures(backend_root)
    if not failures:
        return

    rendered = "\n".join(failures[:20])
    if len(failures) > 20:
        rendered = f"{rendered}\n... and {len(failures) - 20} more"
    message = f"dynamic attribute usage check failed:\n{rendered}"
    raise RuntimeError(message)


def main() -> int:
    """명령줄(CLI) 진입점에서 동적 attribute 접근 가드를 실행한다.

    인자:
        없음.

    반환:
        위반이 있으면 1, 없으면 0.
    """
    failures = collect_failures()
    if failures:
        print("dynamic attribute usage check failed:\n")
        for failure in failures:
            print(failure)
        return 1

    print("dynamic attribute usage check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
