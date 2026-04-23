# 03. Health / app drain 정리

## 무엇을 했는지

`/health/live`, `/health/live`, `/health/ready`, `/health/heartbeat`를 만들고, app 기준 lifecycle 상태를 표현할 수 있도록 정리했습니다.  
처음에는 threshold 기반 drain까지 들어갔지만, 실제 서비스 로직보다 운영 기반이 앞서간다는 판단에 따라 app 기준 drain만 남기고 자동 drain은 제거했습니다.

## 왜 이렇게 했는지

health endpoint는 필요하지만, DB/Redis가 아직 없는 단계에서 dependency까지 포함한 readiness를 너무 이르게 만들면 오히려 가짜 정교함이 됩니다.  
그래서 현재는 app 상태만 표현하고, 외부 dependency와 자동 drain은 문서로만 남겨 두었습니다.

## 현재 기준

- process-local app lifecycle 상태만 유지
- 자동 drain 없음
- DB 상태 미포함
- 정상 healthcheck 로그는 skip
