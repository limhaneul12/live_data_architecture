# 04. platform / shared 역할 분리

## 무엇을 했는지

운영/런타임 성격의 코드를 `backend/app/platform/`으로 이동하고, 진짜 공용적인 코드만 `backend/app/shared/`에 남겼습니다.  
또한 logging 내부를 `formatter / context / mapping` 하위 폴더로 다시 나누어 파일 하나에 함수가 과도하게 몰리지 않도록 정리했습니다.

## 왜 이렇게 했는지

`shared` 폴더가 커질수록 공용 코드가 아니라 “아직 소속이 안 정해진 것들의 집합”이 되기 쉽습니다.  
그래서 runtime/운영 코드는 `platform`으로 옮기고, `shared`에는 타입, 직렬화, schema, guardrail처럼 진짜 공용적인 요소만 남겼습니다.

## 현재 기준

- `platform/`: logging, middleware, lifecycle, health_router, config
- `shared/`: types, serialization, schemas, guardrails
