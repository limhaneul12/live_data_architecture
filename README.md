# live_data_architecture

## 스키마 설명

이번 단계에서 먼저 정리한 것은 데이터베이스 스키마가 아니라 **로깅 스키마와 health 응답 스키마**입니다.
이렇게 한 이유는 애플리케이션의 모든 모듈에서 **같은 JSON logging format**을 사용하게 만들고, 로그를 사람이 읽기 쉽게 유지하면서도 모니터링할 때 같은 필드 기준으로 검색·집계할 수 있게 하려는 목적이 있었기 때문입니다.

제가 중요하게 본 것은 "무슨 정보를 남길까"보다 먼저 **"로그 한 줄을 읽을 때 사람이 어떤 순서로 이해할까"**였습니다.
그래서 포맷은 아래 순서가 보이도록 맞췄습니다.

1. `level`, `event`, `msg`로 먼저 사건의 종류를 파악할 수 있게 한다.
2. `request_id`, `trace_id`, `path`, `status_code`로 어떤 요청인지 바로 이어서 볼 수 있게 한다.
3. `error.type`, `error.message`, `error.stack`은 실패 원인을 마지막에 자세히 보게 한다.

즉, 이 설계의 목적은 **가독성이 좋은 구조화 로그를 만들고**, **모든 모듈에서 같은 형식으로 로그를 남기게 하며**, **에러가 발생했을 때도 같은 JSON 구조 안에서 바로 원인을 추적할 수 있게 하는 것**입니다.

자세한 설명과 예시는 아래 문서를 참고해 주시기 바랍니다.

- `docs/dev_timeline/2026_04_23/02_logging_foundation.md`
- `docs/logging_structure/logging_refactoring_plan.md`
- `docs/logging_structure/logging_trace_context_policy.md`
- `docs/logging_structure/logging_error_stack_policy.md`
- `docs/drain/drain_policy.md`

## 구현하면서 고민한 점

이번 작업에서 가장 많이 고민한 부분은 **운영 기반을 어디까지 먼저 만들 것인지**였습니다.
초기에는 drain, lifecycle, OpenTelemetry, dependency health를 더 많이 넣을 수도 있었지만, 아직 실제 서비스 로직이 없는 단계에서 과하게 앞서가는 것은 오히려 유지보수 부담이 된다고 판단했습니다.

그래서 현재는 다음 원칙으로 정리했습니다.

- logging은 JSON formatter와 request/trace 상관관계까지만 유지합니다.
- drain은 app 기준 상태 표현까지만 두고, 자동 drain은 제거했습니다.
- DB/Redis 같은 운영 인프라는 실제 서비스 로직이 생긴 뒤 다시 판단하기로 했습니다.
- `shared`에는 공용 타입/직렬화만 남기고, runtime 성격의 코드는 `platform`으로 옮겼습니다.

상세한 설계 배경과 단계별 변경 내역은 아래 문서를 참고해 주시면 감사하겠습니다.

- `docs/dev_timeline/2026_04_23/01_environment_bootstrap.md`
- `docs/dev_timeline/2026_04_23/02_logging_foundation.md`
- `docs/dev_timeline/2026_04_23/03_health_and_app_drain.md`
- `docs/dev_timeline/2026_04_23/04_platform_and_shared_split.md`
- `docs/dev_timeline/2026_04_23/05_config_and_docs_cleanup.md`
- `docs/remaining_work.md`
