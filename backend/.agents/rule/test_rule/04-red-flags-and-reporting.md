# 04. Test Red Flags And Reporting

## Goal

불필요하게 취약한 테스트를 막고, 완료 보고 형식을 일관되게 유지한다.

## PR / Test red flags

아래 항목이 있으면 테스트를 재작업한다.

- mock 설정이 assertion보다 많음
- `assert_called_with`류가 유일한 assertion임
- private/internal 경로 import
- 비결정적 snapshot 의존
- 사유 없는 `pytest.skip`
- 테스트 이름이 구현 메서드명을 그대로 반영
- 사소한 코드에 과도한 길이의 테스트 파일

## When not to write tests

아래는 기본적으로 테스트를 추가하지 않는다.

- 비즈니스 로직 없는 단순 CRUD
- 프레임워크 wiring만 있는 코드
- 상수/설정만 변경
- 곧 삭제될 코드

## Final reporting rule

작업 완료 보고에는 반드시 아래를 포함한다.

- 실행한 검증 명령
- pass/fail 결과
- 생략한 항목과 이유
