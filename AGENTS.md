# AGENTS.md

## Scope
이 문서는 저장소 루트와 하위 디렉터리에 적용됩니다.

## Backend Test Rules (필수)
Source of truth:
- `docs/policy/test_policy_agents.md`
- `docs/policy/Required_Command(make).md`
- `docs/policy/ruff_policy.md`
- `docs/policy/pyrefly.md`

### 1) 테스트 위치/발견 규칙
- 모든 backend 테스트는 `backend/tests/` 아래에 둡니다.
- 도메인 테스트는 `backend/tests/<domain>/` 구조를 사용합니다.
- 파일명은 `test_*.py` 패턴을 따라야 합니다.
- pytest는 `--strict-markers` 기준을 따릅니다.
- 신규 marker 추가 시 반드시 `pyproject.toml`에 등록합니다.

### 2) 테스트 철학
- 구현이 아니라 **행동(behavior)** 을 테스트합니다.
- Mock은 시스템 경계(DB/외부 API/네트워크/시간/프로세스 경계)에서만 사용합니다.
- 내부 순수 로직/엔티티/DTO/유틸은 mock하지 않습니다.
- 1차 검증은 observable result(리턴값/상태/에러/외부효과)로 합니다.
- `assert_called_*` 류는 보조 증거로만 허용합니다.

### 3) 테스트 작성 스타일
- 네이밍: `<subject>_<expected_behavior>_when_<condition>`
- 구조: setup -> action -> grouped assertion
- payload 검증은 가능하면 grouped assertion으로 작성합니다.
- 복잡한 테스트 데이터는 `builders/`, `factories/` 사용을 우선합니다.
- 루트 `conftest.py`에는 진짜 공용 fixture만 두고, 도메인 fixture는 `backend/tests/<domain>/conftest.py`로 분리합니다.

### 4) Flaky 금지
- flaky 테스트는 커밋 금지.
- 임시 조치로 `sleep`, 무의미한 retry, 과도한 timeout 증가 금지.
- 불가피한 skip은 **이슈 링크 + 담당자 + 기한**이 있어야 합니다.

### 5) TDD / 회귀 정책
신규 기능/버그 수정 시:
1. 실패하는 behavior 테스트를 먼저 작성/수정
2. 최소 구현으로 통과
3. 관련 테스트 실행
4. 완료 전 `make ci` 실행

### 6) 품질 게이트 (완료 조건)
Backend 변경 완료 전 아래를 반드시 통과해야 합니다.

```bash
make ci
```

`make ci`에는 다음이 포함됩니다.
- `make format_check`
- `make type_checking`
- `make test`

### 7) 실행 규칙
- `pip` 직접 호출 금지, `uv` + `Makefile`만 사용합니다.
- 의존성/환경 동기화는 `make install-local` 우선.
- backend 작업의 canonical 커맨드는 `make` 타깃입니다.

### 8) PR/Test Red Flags (리뷰 차단)
아래 항목이 있으면 테스트를 재작업합니다.
- mock 설정이 assertion보다 많음
- `assert_called_with`류가 유일한 assertion임
- private/internal 경로 import
- 비결정적 snapshot 의존
- 사유 없는 `pytest.skip`
- 테스트 이름이 구현 메서드명을 그대로 반영
- 사소한 코드에 과도한 길이의 테스트 파일

### 9) 테스트를 쓰지 않는 경우
아래는 기본적으로 테스트를 추가하지 않습니다.
- 비즈니스 로직 없는 단순 CRUD
- 프레임워크 wiring만 있는 코드
- 상수/설정만 변경
- 곧 삭제될 코드

### 10) 최종 보고 규칙
작업 완료 보고에는 반드시 포함:
- 실행한 검증 명령
- pass/fail 결과
- 생략한 항목과 이유

### One-line Rule
Hide the implementation from the test.
Hide the test from the implementation.
Only behavior connects them.
