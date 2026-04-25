# Generator log design

## Why we separated generator logs

`event_generator`는 이벤트 데이터를 만들어 stdout 또는 Redis Streams로 보내는 producer다.
여기서 가장 중요한 출력은 **이벤트 자체**다.

그래서 generator에서는 아래 원칙을 잡았다.

- 이벤트 payload는 stdout JSON Lines로 출력
- 시작/종료/신호/요약 같은 운영 로그는 stderr로 출력

이렇게 나눈 이유는 데이터와 운영 로그를 섞지 않기 위해서다.

## Main intent

producer의 stdout은 이후에 바로 MQ body가 될 수 있는 계약 데이터다.
즉, stdout은 사람이 읽기 위한 설명 로그가 아니라 downstream이 받아도 되는 payload여야 했다.

반대로 이런 정보는 stderr로 분리했다.

- generator started
- seed / max_events / no_sleep
- 종료 요약
- signal/shutdown 메시지

이 설계 덕분에 다음 두 사용 방식이 모두 가능해진다.

1. 로컬에서 stdout만 보고 payload shape 확인
2. 실제 sink가 stdout이든 redis든 동일 payload 재사용

## What we worried about

### 1. 데이터와 운영 로그가 섞이는 문제

stdout에 설명 문장이 섞이면 JSON Lines 계약이 깨진다.
consumer나 파이프 처리에서 바로 깨질 수 있으므로, 이것은 가장 먼저 막아야 했다.

### 2. infinite mode와 graceful shutdown

기본 실행은 계속 이벤트를 생성하는 infinite mode다.
그래서 `--max-events`가 없는 기본 실행에서도 종료 시점에 깔끔하게 요약 로그가 남고,
Ctrl+C/SIGTERM에 graceful shutdown 되는 흐름이 필요했다.

### 3. 재현성과 현실감의 균형

완전히 랜덤한 데이터는 테스트 재현성이 떨어지고, 너무 고정된 데이터는 데모 품질이 떨어진다.
그래서 seed 기반 deterministic random + Faker catalog 조합을 선택했다.

## Final decision

- payload는 항상 같은 top-level schema
- stdout은 payload 전용
- stderr는 운영 로그 전용
- infinite mode + `--max-events` 둘 다 지원
- seed를 주면 재현 가능, seed를 생략하면 매 실행마다 다른 ID 생성

즉, generator logging은 “관측을 위한 로그”보다 먼저 “데이터 스트림 계약을 보호하는 로그
분리”가 핵심이었다.
