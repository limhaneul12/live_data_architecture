# 01. Test Location And Discovery

## Goal

Backend 테스트 위치와 pytest discovery 규칙을 일관되게 유지한다.

## Rules

- 모든 backend 테스트는 `backend/tests/` 아래에 둔다.
- 도메인 테스트는 `backend/tests/<domain>/` 구조를 사용한다.
- 파일명은 `test_*.py` 패턴을 따라야 한다.
- pytest는 `--strict-markers` 기준을 따른다.
- 새로운 marker를 추가하면 반드시 `pyproject.toml`에 등록한다.
- 루트 `conftest.py`에는 진짜 공용 fixture만 둔다.
- 도메인 fixture는 `backend/tests/<domain>/conftest.py`로 분리한다.
