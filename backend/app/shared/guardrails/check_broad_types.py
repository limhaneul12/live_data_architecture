"""문법 트리(AST) 기반 broad type 사용 가드."""

from __future__ import annotations

import ast
import re
from pathlib import Path

from app.shared.guardrails._common import (
    TYPE_JUSTIFICATION_MARKERS,
    has_justification,
    iter_guard_target_paths,
    parse_module,
)

ANY_PATTERN = re.compile(r"\bAny\b")
OBJECT_PATTERN = re.compile(r"\bobject\b")
BROAD_DICT_PATTERN = re.compile(r"\b(?:dict|Mapping)\[[^\]]*\b(?:Any|object)\b[^\]]*\]")


class BroadTypeVisitor(ast.NodeVisitor):
    """타입 표현식 안의 broad type 사용을 수집한다."""

    def __init__(self, *, path: Path, lines: list[str]) -> None:
        """광범위 타입 visitor를 초기화한다.

        인자:
            path: 현재 검사 중인 파일 경로.
            lines: 파일 원본 줄 목록.

        반환:
            없음.
        """
        self._path = path
        self._lines = lines
        self.failures: list[str] = []

    def _check_type_node(self, node: ast.expr | ast.arg | None) -> None:
        """타입 노드 하나를 검사해 broad type 위반을 기록한다.

        인자:
            node: 검사할 타입 표현식 노드.

        반환:
            없음.
        """
        if node is None:
            return
        rendered = ast.unparse(node)
        has_any = ANY_PATTERN.search(rendered) is not None
        has_object = OBJECT_PATTERN.search(rendered) is not None
        has_broad_dict = BROAD_DICT_PATTERN.search(rendered) is not None
        if not has_any and not has_object and not has_broad_dict:
            return
        if has_justification(
            lines=self._lines,
            lineno=node.lineno,
            markers=TYPE_JUSTIFICATION_MARKERS,
        ):
            return
        if has_broad_dict:
            self.failures.append(
                f"{self._path}:{node.lineno}: broad dictionary type without justification"
            )
            return
        self.failures.append(
            f"{self._path}:{node.lineno}: broad type without justification"
        )

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        """변수 주석 타입을 검사한다.

        인자:
            node: 주석이 달린 대입 AST 노드.

        반환:
            없음.
        """
        self._check_type_node(node.annotation)
        self.generic_visit(node)

    def visit_arg(self, node: ast.arg) -> None:
        """함수 인자 타입을 검사한다.

        인자:
            node: 함수 인자 AST 노드.

        반환:
            없음.
        """
        self._check_type_node(node.annotation)
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """동기 함수의 반환 타입을 검사한다.

        인자:
            node: 함수 정의 AST 노드.

        반환:
            없음.
        """
        self._check_type_node(node.returns)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """비동기 함수의 반환 타입을 검사한다.

        인자:
            node: 비동기 함수 정의 AST 노드.

        반환:
            없음.
        """
        self._check_type_node(node.returns)
        self.generic_visit(node)

    def visit_TypeAlias(self, node: ast.TypeAlias) -> None:
        """타입 별칭 정의를 검사한다.

        인자:
            node: 타입 별칭 AST 노드.

        반환:
            없음.
        """
        self._check_type_node(node.value)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        """타입 변환(cast) 호출의 타입 인자를 검사한다.

        인자:
            node: 함수 호출 AST 노드.

        반환:
            없음.
        """
        if isinstance(node.func, ast.Name) and node.func.id == "cast" and node.args:
            first_arg = node.args[0]
            if isinstance(first_arg, ast.expr):
                self._check_type_node(first_arg)
        self.generic_visit(node)


def collect_failures(backend_root: Path | None = None) -> list[str]:
    """광범위 타입 가드 위반 목록을 수집한다.

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
        visitor = BroadTypeVisitor(path=path, lines=lines)
        visitor.visit(parse_module(path))
        failures.extend(visitor.failures)
    return failures


def ensure_clean(backend_root: Path | None = None) -> None:
    """광범위 타입 위반이 있으면 예외를 발생시킨다.

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
    message = f"Broad type usage check failed:\n{rendered}"
    raise RuntimeError(message)


def main() -> int:
    """명령줄(CLI) 진입점에서 broad type 가드를 실행한다.

    인자:
        없음.

    반환:
        위반이 있으면 1, 없으면 0.
    """
    failures = collect_failures()
    if failures:
        print("Broad type usage check failed:\n")
        for failure in failures:
            print(failure)
        return 1

    print("Broad type usage check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
