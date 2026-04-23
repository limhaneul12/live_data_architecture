"""문법 트리(AST) 기반 지연 import 사용 가드."""

from __future__ import annotations

import ast
from pathlib import Path

from app.shared.guardrails._common import (
    LAZY_IMPORT_JUSTIFICATION_MARKERS,
    has_justification,
    iter_guard_target_paths,
    parse_module,
)

_DYNAMIC_IMPORT_CALLS = {"__import__"}


class LazyImportVisitor(ast.NodeVisitor):
    """함수/클래스 내부 import와 동적 import 호출 위반을 수집한다."""

    def __init__(self, *, path: Path, lines: list[str]) -> None:
        """지연 import visitor를 초기화한다.

        인자:
            path: 현재 검사 중인 파일 경로.
            lines: 파일 원본 줄 목록.

        반환:
            없음.
        """
        self._path = path
        self._lines = lines
        self._scope_depth = 0
        self._type_checking_depth = 0
        self.failures: list[str] = []

    def visit_If(self, node: ast.If) -> None:
        """타입 검사(TYPE_CHECKING) 블록 내부 import는 허용하고 나머지는 검사한다.

        인자:
            node: if AST 노드.

        반환:
            없음.
        """
        if self._is_type_checking_guard(node.test):
            self._type_checking_depth += 1
            for child in node.body:
                self.visit(child)
            self._type_checking_depth -= 1
            for child in node.orelse:
                self.visit(child)
            return
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """함수 scope 내부를 검사한다.

        인자:
            node: 함수 정의 AST 노드.

        반환:
            없음.
        """
        self._scope_depth += 1
        self.generic_visit(node)
        self._scope_depth -= 1

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """비동기 함수 scope 내부를 검사한다.

        인자:
            node: 비동기 함수 정의 AST 노드.

        반환:
            없음.
        """
        self._scope_depth += 1
        self.generic_visit(node)
        self._scope_depth -= 1

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """클래스 body 내부를 검사한다.

        인자:
            node: 클래스 정의 AST 노드.

        반환:
            없음.
        """
        self._scope_depth += 1
        self.generic_visit(node)
        self._scope_depth -= 1

    def visit_Import(self, node: ast.Import) -> None:
        """로컬 import 사용 여부를 검사한다.

        인자:
            node: import AST 노드.

        반환:
            없음.
        """
        self._check_local_import(node=node, label="local import")
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """로컬 import-from 사용 여부를 검사한다.

        인자:
            node: import-from AST 노드.

        반환:
            없음.
        """
        self._check_local_import(node=node, label="local import-from")
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        """동적 import 호출 여부를 검사한다.

        인자:
            node: 함수 호출 AST 노드.

        반환:
            없음.
        """
        call_name = self._call_name(node.func)
        if call_name in _DYNAMIC_IMPORT_CALLS or call_name == "importlib.import_module":
            self._add_failure_if_unjustified(
                lineno=node.lineno,
                label=f"dynamic import call `{call_name}`",
            )
        self.generic_visit(node)

    def _check_local_import(
        self, *, node: ast.Import | ast.ImportFrom, label: str
    ) -> None:
        """로컬 import 위반 여부를 검사한다.

        인자:
            node: import 또는 import-from AST 노드.
            label: 실패 메시지에 사용할 import 종류.

        반환:
            없음.
        """
        if self._type_checking_depth > 0:
            return
        if self._scope_depth == 0:
            return
        self._add_failure_if_unjustified(lineno=node.lineno, label=label)

    def _add_failure_if_unjustified(self, *, lineno: int, label: str) -> None:
        """정당화 주석이 없는 지연 import 위반을 추가한다.

        인자:
            lineno: 위반 후보 줄 번호.
            label: 위반 종류.

        반환:
            없음.
        """
        if has_justification(
            lines=self._lines,
            lineno=lineno,
            markers=LAZY_IMPORT_JUSTIFICATION_MARKERS,
        ):
            return
        self.failures.append(f"{self._path}:{lineno}: {label} without justification")

    def _is_type_checking_guard(self, node: ast.expr) -> bool:
        """타입 검사(TYPE_CHECKING) guard인지 확인한다.

        인자:
            node: if 조건 AST 노드.

        반환:
            TYPE_CHECKING guard면 True.
        """
        if isinstance(node, ast.Name):
            return node.id == "TYPE_CHECKING"
        if isinstance(node, ast.Attribute):
            return node.attr == "TYPE_CHECKING"
        return False

    def _call_name(self, node: ast.expr) -> str | None:
        """호출 대상 이름을 문자열로 변환한다.

        인자:
            node: 호출 대상 AST 노드.

        반환:
            식별 가능한 호출 이름. 알 수 없으면 None.
        """
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            return f"{node.value.id}.{node.attr}"
        return None


def collect_failures(backend_root: Path | None = None) -> list[str]:
    """지연 import 가드 위반 목록을 수집한다.

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
        visitor = LazyImportVisitor(path=path, lines=lines)
        visitor.visit(parse_module(path))
        failures.extend(visitor.failures)
    return failures


def ensure_clean(backend_root: Path | None = None) -> None:
    """지연 import 위반이 있으면 예외를 발생시킨다.

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
    message = f"lazy import usage check failed:\n{rendered}"
    raise RuntimeError(message)


def main() -> int:
    """명령줄(CLI) 진입점에서 지연 import 가드를 실행한다.

    인자:
        없음.

    반환:
        위반이 있으면 1, 없으면 0.
    """
    failures = collect_failures()
    if failures:
        print("lazy import usage check failed:\n")
        for failure in failures:
            print(failure)
        return 1

    print("lazy import usage check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
