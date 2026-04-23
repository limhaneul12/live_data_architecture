# .agents AGENTS.md

## Scope
이 문서는 `backend/.agents/`와 그 하위 전체에 적용됩니다.

## Purpose
`backend/.agents/rule/` 아래 문서는 backend 개발 시 참고해야 하는 규칙 문서 모음입니다.
이 디렉터리의 문서를 수정할 때는 단순 보관용이 아니라, 실제 backend 개발 기준 문서라는 점을 유지해야 합니다.

## Rule groups

- `rule/archtecture_rule/`: backend 구조/계층/타입/예외/DI 규칙
- `rule/test_rule/`: backend 테스트 철학/위치/품질 게이트/보고 규칙

## Rules

- 각 rule 하위 폴더의 번호 체계와 파일 역할은 유지합니다.
- 문서를 수정할 때는 현재 backend 구현/정책과의 정합성을 우선 확인합니다.
- 오래된 설명이나 더 이상 쓰지 않는 규칙은 그대로 방치하지 말고 명확히 정리합니다.
- backend 코드에서 실제로 참조하는 규칙 문서이므로, 모호한 표현보다 실행 가능한 기준을 우선합니다.
