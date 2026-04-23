# 05. Config 및 문서 정리

## 무엇을 했는지

`platform/config`에 `AppConfig`, `DatabaseConfig`를 추가하고, `pydantic-settings`로 `.env`를 읽도록 정리했습니다.  
환경변수 이름도 `SERVICE_`, `DATABASE_` 접두어 기준으로 통일했고, 남은 작업은 `docs/remaining_work.md`에 지금 꼭 필요한 것만 남기도록 정리했습니다.

## 왜 이렇게 했는지

설정 이름이 제각각이면 운영 과정에서 실수가 나기 쉽고, 코드에서 직접 `os.environ[...]`을 흩어 읽으면 수정 포인트가 많아집니다.  
그래서 지금 단계에서 필요한 설정만 중앙화하되, 추상화를 과도하게 늘리지 않는 수준으로 정리했습니다.

## 현재 기준

- `SERVICE_APP_*`, `DATABASE_DB_ADDRESS` 사용
- AppConfig / DatabaseConfig로 중앙화
- remaining work는 실제 서비스 로직 우선 순서로 축소
