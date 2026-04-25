# 14. Security follow-up: proxy allowlist and analytics read DSN

## 배경

이전 점검에서 남은 수정 후보는 다음 두 가지였다.

1. Next.js analytics proxy가 `/api/analytics/*`를 넓게 받아 backend로 전달한다.
2. SQL Lab/Explore query가 writer DB DSN을 그대로 사용한다.

## 수정 내용

### 1. Frontend analytics proxy allowlist

`frontend/app/api/analytics/[...path]/route.ts`에서 proxy 가능한 backend analytics
path를 명시적으로 제한했다.

허용 path와 method:

- `GET /api/analytics/datasets`
- `GET /api/analytics/presets`
- `POST /api/analytics/query`
- `POST /api/analytics/explore-query`

그 외 path는 404, method mismatch는 405로 반환한다. POST body는 16KB로 제한해서
SQL Lab 입력 표면이 과도하게 커지지 않게 했다. backend 연결 실패 시 내부 연결 오류
문자열을 그대로 노출하지 않고 고정된 `backend_connection_failed` 사유만 반환한다.

### 2. Analytics read DSN 분리 기반

`AnalyticsDatabaseConfig`를 추가하고, `ANALYTICS_DATABASE_DB_ADDRESS`가 있으면
SQL Lab/Explore query repository가 해당 DSN을 사용하도록 분리했다.

현재 의미:

- 미설정 시 기존 `DATABASE_DB_ADDRESS`를 사용하므로 local 실행은 그대로 동작한다.
- 운영형/보안형 구성에서는 `ANALYTICS_DATABASE_DB_ADDRESS`에 read-only DB role을 넣을 수 있다.
- 실제 role 생성과 grant는 DB 운영/초기화 정책이 필요하므로 별도 작업으로 남긴다.

## 남은 보안 작업

read-only DSN 분리 기반은 들어갔지만, 아래는 아직 별도 작업이다.

1. Postgres read-only role 생성
2. generated view에만 `SELECT` grant
3. raw `events` table 직접 조회 권한 제거
4. SQL Lab을 local/admin feature로 제한할지 결정

## 검증

```bash
make ci
npm run typecheck
npm run lint
npm run build
docker compose config --quiet
git diff --check
uvx bandit -r backend/app event_generator -x backend/tests,event_generator/tests -q
```

결과:

- backend/event_generator: 155 passed
- frontend typecheck/lint/build 통과
- compose config에서 Postgres/Redis host publish가 `127.0.0.1`로 유지됨
- Bandit은 기존 SQL Lab raw SQL wrapper(B608)와 deterministic generator random(B311)을
  계속 지적한다. B608은 SQL Lab을 유지하는 한 read-only role/grant 분리까지
  후속으로 보강해야 하는 잔여 리스크다.
