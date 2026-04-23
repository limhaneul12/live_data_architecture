# 00. Backend Test Rule Sources

## Goal

Backend 테스트 규칙의 source of truth를 명확히 유지한다.

## Source of truth

아래 문서를 backend 테스트 규칙의 근거 문서로 본다.

```text
docs/policy/test_policy_agents.md
docs/policy/setting_rule/Required_Command(make).md
docs/policy/setting_rule/ruff_policy.md
docs/policy/setting_rule/pyrefly.md
```

## Rule

- backend 테스트 규칙이 애매하면 위 문서를 먼저 확인한다.
- 새로운 테스트 규칙을 추가할 때는 위 문서와 충돌하지 않는지 먼저 확인한다.
- 문서와 구현이 어긋나면 조용히 우회하지 말고 source of truth를 먼저 정리한다.
