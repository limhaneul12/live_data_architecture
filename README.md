# live_data_architecture

## 스키마 설명

현재 단계에서는 데이터베이스 테이블 스키마보다, 애플리케이션이 실제로 사용하는 **구조화 JSON logging / health schema**를 먼저 정리했습니다.  
로그와 헬스체크 응답을 Pydantic schema로 고정한 이유는 필드 drift를 줄이고, 이후 운영 환경에서 필요한 request/trace 상관관계를 안정적으로 유지하기 위해서입니다.

자세한 내용은 아래 문서를 참고해 주시기 바랍니다.

- `docs/logging_structure/logging_refactoring_plan.md`
- `docs/logging_structure/logging_trace_context_policy.md`
- `docs/drain/drain_policy.md`

## 구현하면서 고민한 점

이번 작업에서 가장 많이 고민한 부분은 **운영 기반을 어디까지 먼저 만들 것인지**였습니다.  
초기에는 drain, lifecycle, OpenTelemetry, dependency health를 더 많이 넣을 수도 있었지만, 아직 실제 서비스 로직이 없는 단계에서 과하게 앞서가는 것은 오히려 유지보수 부담이 된다고 판단했습니다.

그래서 현재는 다음 원칙으로 정리했습니다.

- logging은 JSON formatter와 request/trace 상관관계까지만 유지합니다.
- drain은 app 기준 상태 표현까지만 두고, 자동 drain은 제거했습니다.
- DB/Redis 같은 운영 인프라는 실제 서비스 로직이 생긴 뒤 다시 판단하기로 했습니다.
- `shared`에는 공용 타입/직렬화/schema만 남기고, runtime 성격의 코드는 `platform`으로 옮겼습니다.

상세한 설계 배경과 단계별 변경 내역은 아래 문서를 참고해 주시면 감사하겠습니다.

- `docs/dev_timeline/2026_04_23/01_environment_bootstrap.md`
- `docs/dev_timeline/2026_04_23/02_logging_foundation.md`
- `docs/dev_timeline/2026_04_23/03_health_and_app_drain.md`
- `docs/dev_timeline/2026_04_23/04_platform_and_shared_split.md`
- `docs/dev_timeline/2026_04_23/05_config_and_docs_cleanup.md`
- `docs/remaining_work.md`
