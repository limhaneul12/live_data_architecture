# 01. 환경 구성 시작

## 무엇을 했는지

이 단계에서는 Python 3.12.10과 `uv`를 기준으로 백엔드 실행 환경을 고정했습니다.  
루트 `.venv`, `backend/pyproject.toml`, `Makefile`, `docker-compose.yml` 기본 구조를 만들고 `make ci`를 품질 게이트로 삼았습니다.

## 왜 이렇게 했는지

초기 단계에서 실행 환경이 흔들리면 이후 logging, health, drain 설계가 모두 불안정해집니다.  
그래서 먼저 Python 버전, formatter/linter/type checker, 테스트 경로를 고정해 팀이 같은 기준으로 움직일 수 있도록 정리했습니다.

## 현재 기준

- Python: 3.12.10
- 패키지/실행: `uv`
- 검증: `make ci`
