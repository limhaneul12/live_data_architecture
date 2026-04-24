# Event analytics frontend

Next.js(TypeScript) 기반의 단일 페이지 SQL analytics workspace입니다.

## 실행

```bash
cd frontend
npm install
npm run dev
```

브라우저는 Next.js same-origin `/api/analytics/*` proxy를 호출합니다. Next.js 서버가 바라보는 backend 주소는 `BACKEND_API_BASE_URL`로 설정하며, 로컬 기본값은 `http://localhost:8000`입니다.

Production smoke는 standalone output 기준입니다.

```bash
BACKEND_API_BASE_URL=http://localhost:8000 npm run start
```

`npm run start`는 `.next/standalone/server.js`가 없으면 먼저 `next build`를 실행합니다.

## 화면 범위

- generated view selector
- preset SQL buttons
- SQL textarea
- Run SQL button
- query result table
- chart preview (`bar`, `line`, `metric`, `table`)

인증, 저장 dashboard, query history, 복잡한 BI builder는 v1 범위에서 제외했습니다.

## 검증

```bash
npm run lint
npm run typecheck
npm run build
npm audit --omit=dev --audit-level=moderate
```
