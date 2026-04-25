# Event analytics frontend

Next.js(TypeScript) 기반의 Superset-style analytics workspace입니다.

과제 Step5의 “SQL 집계 결과 시각화”를 위해 아래 두 흐름을 제공합니다.

- **Explore**: generated dataset과 columns/chart/limit/sort control을 선택하면 `/analytics/explore-query` structured API가 SQLAlchemy Core로 SELECT를 생성하고 chart/table을 렌더링합니다.
- **SQL Lab**: preset SQL 또는 사용자가 입력한 SELECT를 실행하고 결과 table 전체를 확인합니다.

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

- Superset을 참고한 top navigation / sidebar / chart control panel
- generated dataset selector
- dataset column metadata 기반 Explore controls
- backend structured Explore query execution
- preset SQL buttons
- SQL Lab textarea
- Run Chart / Run SQL button
- query result table
- chart preview (`bar`, `line`, `pie`, `metric`, `table`)
- generated SQL preview

인증, 저장 dashboard, query history, dashboard drag-and-drop builder는 v1 범위에서 제외했습니다.

## 검증

```bash
npm run lint
npm run typecheck
npm run build
npm audit --omit=dev --audit-level=moderate
```
