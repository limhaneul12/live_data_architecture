# 02. MQ raw event payload 계약 정리

## 무엇을 했는지

DB schema보다 먼저 producer와 consumer 사이에서 오갈 raw event JSON 계약을 고정했습니다.
이 계약은 `event_generator` stdout JSON Lines 한 줄이 Redis Streams `payload` field에 그대로 들어가도 같은 의미를 갖도록 설계했습니다.

현재 payload는 아래 top-level field set을 항상 가집니다.

```text
schema_version
event_id
event_type
occurred_at
user_id
traffic_phase
producer_id
page_path
category_id
product_id
amount
currency
error_code
error_message
```

이벤트 타입에 해당하지 않는 값은 필드를 생략하지 않고 `null`로 둡니다.

## 왜 이렇게 했는지

과제 Step 2에서 “JSON을 통째로 저장하지 말고 필드를 구분하여 저장”해야 하므로, Step 1부터 모든 이벤트가 같은 컬럼 후보를 가지도록 했습니다.
필드를 생략하면 consumer/DB 단계에서 이벤트 타입별 분기와 schema drift가 커집니다.

따라서 v1 payload는 다음 기준을 따릅니다.

- 모든 field는 항상 존재
- nullable field도 생략은 금지하고 `null`로 명시
- `schema_version`으로 consumer가 계약 버전을 먼저 확인
- broker metadata는 payload 안에 넣지 않음
- `session_id`, `seller_id`, `listing_id`, `sku`, nested items는 v2 후보로 보류

## Codex CLI review 반영

Codex CLI review에서 nullable field가 Pydantic 기본값으로 조용히 채워지면 문서화한 “모든 필드는 항상 존재” 계약을 깨뜨릴 수 있다고 지적했습니다.
그래서 backend boundary schema인 `WebEventPayload`에서 nullable field도 default 없이 required nullable field로 바꿨습니다.

즉 아래는 허용합니다.

```json
{"error_message": null}
```

하지만 아래처럼 필드를 생략한 payload는 reject합니다.

```json
{}
```

## 현재 기준

- producer output과 MQ message body는 같은 `web_event.v1` 계약
- Pydantic은 IO boundary에서만 사용
- 내부 application/domain에서는 dataclass `WebEvent` 사용
- `session_id`는 현재 v1에서 제외
- 관련 문서: `docs/event_generator/event_data_format_design.md`, `docs/event_generator/mq_event_payload_contract.md`
