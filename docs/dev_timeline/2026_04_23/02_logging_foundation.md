# 02. Logging foundation 구축

## 무엇을 했는지

JSON logging formatter를 만들고, request/trace 필드가 구조화되어 출력되도록 정리했습니다.  
또한 `hasattr/getattr`, lazy import, broad type에 대한 guardrail도 추가해 logging 주변 코드가 쉽게 흐트러지지 않도록 했습니다.

## 왜 이렇게 했는지

초기에는 단순 print로 시작할 수도 있지만, 나중에 운영 로그를 읽어야 할 때 request id, trace id, HTTP metadata가 없다면 장애 분석이 매우 어려워집니다.  
다만 과한 추상화를 피하기 위해 현재는 app 기준 logging까지만 남기고, 실제 exporter/collector 연동은 보류했습니다.

## 현재 기준

- JSON logging 유지
- request id / trace id 필드 유지
- OTEL은 최소 mapping 초안까지만 유지
- 과한 runtime 관측성 확장은 보류
