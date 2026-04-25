# 2026-04-25 — Frontend event analytics workspace

브랜치: `fect/frontend-event-analytics`  
기준 브랜치: `fect/step2-event-storage-analytics`

## 1. 진행 배경

backend Step2 브랜치에서 아래 API를 준비했다.

```text
GET  /analytics/datasets
GET  /analytics/presets
POST /analytics/query
```

이번 frontend 브랜치에서는 과제 Step5의 “SQL 집계 결과 시각화”를 위해 Next.js(TypeScript) 단일 페이지 workspace를 추가했다.

## 2. 구현 범위

추가 위치:

```text
frontend/
  app/
    components/
      analytics-workspace.tsx
      chart-preview.tsx
      result-table.tsx
    lib/api.ts
    globals.css
    layout.tsx
    page.tsx
  Dockerfile
  package.json
  package-lock.json
```

UI 구성:

- generated view selector
- preset SQL buttons
- SQL textarea
- Run SQL button
- result table
- chart preview

Chart preview 정책:

| result shape | preview |
|---|---|
| label + numeric | bar |
| temporal + numeric | line |
| numeric-only | metric |
| 기타 | table |

## 3. 설계 결정

- Next.js App Router를 사용한다.
- SQL editor와 API 호출은 state/event handler가 필요하므로 Client Component로 둔다.
- 별도 chart dependency를 추가하지 않고 CSS/SVG 기반 preview만 구현한다.
- backend의 SQL safety 정책을 신뢰하되, frontend는 generated view/preset 중심 UX로 위험한 입력을 줄인다.
- 복잡한 Superset clone, dashboard 저장, auth, query history는 제외한다.

참고한 공식 문서:

- Next.js App Router docs: https://nextjs.org/docs/app
- Next.js Server/Client Components docs: https://nextjs.org/docs/app/getting-started/server-and-client-components
- Next.js `use client` directive docs: https://nextjs.org/docs/app/api-reference/directives/use-client
- Next.js standalone output docs: https://nextjs.org/docs/app/api-reference/config/next-config-js/output

## 4. Docker Compose 반영

`docker-compose.yml`에 `frontend` service를 추가했다.

```text
frontend -> Next.js app, port 3000
app      -> FastAPI backend, port 8000
redis    -> Redis Streams
_db      -> PostgreSQL
```

브라우저 CORS를 피하기 위해 프론트는 same-origin `/api/analytics/*` route handler를 호출한다. 이 route handler가 `BACKEND_API_BASE_URL`로 FastAPI에 server-side proxy한다. Compose에서는 `BACKEND_API_BASE_URL=http://app:8000`을 사용한다.

## 5. 검증 계획

Frontend local quality gate:

```bash
cd frontend
npm run lint
npm run typecheck
npm run build
npm audit --omit=dev --audit-level=moderate
```

Full stack smoke:

```bash
docker compose up --build
curl http://localhost:3000
curl http://localhost:3000/api/analytics/datasets
```

최종 검증 결과는 실행 후 이 문서에 이어서 기록한다.

## 6. 최종 검증 결과

공식 문서 기준 확인:

- Next.js App Router는 file-system router와 Server/Client Component 기반으로 동작한다.
- SQL editor처럼 state/event handler가 필요한 UI는 `use client` boundary가 필요하다.

Frontend quality gate:

```bash
make frontend-ci
cd frontend && npm audit --omit=dev --audit-level=moderate
```

결과:

```text
eslint passed
tsc --noEmit passed
next build passed
npm audit --omit=dev --audit-level=moderate -> found 0 vulnerabilities
```

Backend regression:

```bash
make ci
```

결과:

```text
ruff format/check passed
pyrefly: 0 errors
guardrails passed
111 passed
```

Compose smoke:

```bash
DOCKER_BUILDKIT=0 APP_PORT=18002 FRONTEND_PORT=13000 POSTGRES_PORT=15434 REDIS_PORT=16381 \
  docker compose -p lda_frontend build app event-generator frontend

APP_PORT=18002 FRONTEND_PORT=13000 POSTGRES_PORT=15434 REDIS_PORT=16381 \
  docker compose -p lda_frontend up -d db redis app frontend
```

확인 결과:

```text
GET http://localhost:18002/health/ready -> app/redis/database ok
GET http://localhost:13000 -> HTML 7072 bytes, contains "Event Analytics SQL Workspace"
GET http://localhost:13000/api/analytics/datasets -> 6 generated views through frontend proxy
GET http://localhost:18002/analytics/datasets -> 6 generated views from backend
producer emitted 20 events to Redis
Redis XLEN web.events.raw.v1 -> 20
PostgreSQL SELECT count(*) FROM events -> 20
Redis XPENDING web.events.raw.v1 event_analytics_writer -> 0
POST http://localhost:13000/api/analytics/query event_type_counts -> 5 rows + bar chart suggestion
POST http://localhost:13000/api/analytics/query DROP TABLE events -> 400 sql_policy_violation
```

Smoke 이후 stack은 `docker compose -p lda_frontend down -v`로 정리했다.

## 7. 협업 리뷰 반영

frontend code review에서 아래 지적을 받았고 모두 반영했다.

- 브라우저가 FastAPI를 직접 호출하면 CORS와 build-time public env coupling이 생긴다.
  - 조치: Next.js route handler `/api/analytics/*`를 추가하고 server-side에서 `BACKEND_API_BASE_URL`로 proxy한다.
- backend chart suggestion의 `series_axis`를 UI가 무시하면 시간대별 이벤트 추이 같은 multi-series line chart가 부정확하다.
  - 조치: line chart는 series별 SVG path로 분리하고, bar chart label에도 series 값을 포함한다.
- backend 연결 실패 시 status card가 성공처럼 보일 수 있다.
  - 조치: metadata loading/success/error 상태를 분리했다.
- backend가 내려간 상태에서 Next.js proxy가 exception을 그대로 터뜨리면 빈 500 응답이 내려간다.
  - 조치: proxy에서 connection failure를 `503 backend_unavailable` JSON으로 변환하고, client parser는 empty/non-JSON error body도 안전하게 처리한다.

추가 확인:

```text
PORT=13101 BACKEND_API_BASE_URL=http://127.0.0.1:65534 npm run start
GET http://localhost:13101/api/analytics/datasets -> 503 backend_unavailable JSON
```

## 8. Deslop / regression

Ralph 마무리 전에 변경 파일 범위만 대상으로 정리했다.

- multi-series chart grouping에서 매 row마다 새 배열을 만들던 부분을 in-place push로 단순화했다.
- public browser env stale reference가 없는지 재확인했다.
- `package.json`의 production start는 standalone output 규칙에 맞춰 `node .next/standalone/server.js`로 맞췄다.
- verifier가 clean tree에서 `.next/standalone/server.js`가 없으면 `npm run start`가 실패한다고 지적했다.
  - 조치: `prestart`에서 standalone artifact가 없으면 `npm run build`를 먼저 실행하도록 보강했다.

Post-cleanup verification:

```text
make frontend-ci -> eslint/typecheck/next build passed
npm audit --omit=dev --audit-level=moderate -> found 0 vulnerabilities
make ci -> 111 passed
docker compose config -> passed
git diff --check -> passed
```

추가 local production start 확인:

```text
rm -rf frontend/.next frontend/tsconfig.tsbuildinfo
PORT=13102 BACKEND_API_BASE_URL=http://127.0.0.1:65534 npm run start
prestart -> next build executed
test -f frontend/.next/standalone/server.js -> present
GET http://localhost:13102/api/analytics/datasets -> 503 backend_unavailable JSON
```
