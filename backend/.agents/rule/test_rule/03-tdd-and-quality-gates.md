# 03. TDD And Quality Gates

## Goal

기능/버그 수정 시 테스트를 먼저 고정하고, backend 품질 게이트를 반드시 통과한다.

## TDD / Regression policy

신규 기능/버그 수정 시:

1. 실패하는 behavior 테스트를 먼저 작성하거나 수정한다.
2. 최소 구현으로 통과시킨다.
3. 관련 테스트를 실행한다.
4. 완료 전 `make ci`를 실행한다.

## Quality gate

Backend 변경 완료 전 아래를 반드시 통과해야 한다.

```bash
make ci
```

`make ci`에는 다음이 포함된다.

- `make format_check`
- `make type_checking`
- `make guardrails`
- `make test`

## Execution rule

- `pip` 직접 호출 금지, `uv` + `Makefile`만 사용한다.
- 의존성/환경 동기화는 `make install-local`을 우선한다.
- backend 작업의 canonical command는 `make` 타깃이다.
