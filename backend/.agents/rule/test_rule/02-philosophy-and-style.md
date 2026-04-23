# 02. Test Philosophy And Style

## Goal

구현이 아니라 행동을 검증하는 테스트 문화를 유지한다.

## Philosophy

- 구현이 아니라 **행동(behavior)** 을 테스트한다.
- Mock은 시스템 경계(DB, 외부 API, 네트워크, 시간, 프로세스 경계)에서만 사용한다.
- 내부 순수 로직, 엔티티, DTO, 유틸은 mock하지 않는다.
- 1차 검증은 observable result(리턴값, 상태, 에러, 외부효과)로 한다.
- `assert_called_*` 류는 보조 증거로만 사용한다.

## Style

- 네이밍: `<subject>_<expected_behavior>_when_<condition>`
- 구조: setup -> action -> grouped assertion
- payload 검증은 가능하면 grouped assertion으로 작성한다.
- 복잡한 테스트 데이터는 `builders/`, `factories/` 사용을 우선한다.

## One-line rule

```text
Hide the implementation from the test.
Hide the test from the implementation.
Only behavior connects them.
```
