# 01. Step 1 이벤트 생성기 구현

## 무엇을 했는지

과제 Step 1 요구사항에 맞춰 루트에 독립 실행 가능한 `event_generator/` 패키지를 만들었습니다.

구현한 핵심은 아래와 같습니다.

- `python -m event_generator`로 실행되는 독립 producer
- 기본 실행은 계속 생성하는 infinite mode
- `--max-events`로 데모/테스트용 생성 건수 제한
- `--no-sleep`으로 테스트에서 rate sleep 생략
- `--seed`를 명시하면 재현 가능한 deterministic 출력
- `--seed`를 생략하면 producer 재시작 시 같은 `event_id` sequence를 replay하지 않도록 실행마다 seed 자동 생성
- stdout에는 JSON Lines 이벤트만 출력
- 시작/종료/요약 로그는 stderr로 분리
- SIGINT/SIGTERM graceful shutdown 지원

## 이벤트 타입

커머스 웹 서비스의 기본 funnel을 보여주기 위해 5개 이벤트를 사용했습니다.

```text
page_view
product_click
add_to_cart
purchase
checkout_error
```

비율은 페이지 조회와 클릭이 구매/오류보다 많이 나오도록 잡았습니다.
이렇게 해야 이후 SQL 분석에서 `page_view -> product_click -> add_to_cart -> purchase` 흐름이 자연스럽게 보입니다.

## event_id 결정

처음에는 `event_id` 중복 허용도 고민했지만, 최종적으로는 이벤트 한 건의 idempotency key로 보기 위해 unique opaque string으로 결정했습니다.
같은 상품을 여러 번 클릭하는 반복 행동은 `event_id` 반복이 아니라 `product_id`, `category_id`, `event_type` 반복으로 표현합니다.

추가로 Codex CLI review에서 infinite mode의 메모리 증가와 producer restart replay 위험이 지적되어 아래처럼 보정했습니다.

- `_seen_event_ids` set을 제거해 장기 실행 시 메모리 선형 증가를 막음
- run별 prefix + counter 기반 opaque id로 변경
- 기본 seed를 고정값이 아니라 자동 생성으로 바꿔 재시작 replay를 피함
- 테스트/데모에서만 `--seed`로 재현성을 고정

## 현재 기준

- 이벤트 출력 계약: `web_event.v1`
- 출력 형식: JSON Lines
- 기본 모드: infinite realtime producer
- 테스트 모드: `--max-events`, `--no-sleep`, `--seed`
- 관련 문서: `event_generator/README.md`, `docs/event_generator/step1_summary.md`
