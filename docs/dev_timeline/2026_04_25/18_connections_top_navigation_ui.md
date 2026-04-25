# 18. Connections top navigation UI

작성일: 2026-04-25  
브랜치: `fect/structured-explore-query`

## 배경

사용자는 database connection UI가 Chart Builder control panel 안에 섞여 있는 것보다,
Superset의 Data/Databases 화면처럼 상단 navigation의 별도 `Connections` 항목으로
분리되는 구성이 더 자연스럽다고 제안했다.

참고한 방향:

- top navigation에서 `Charts`, `SQL Lab`, `Connections`를 명확히 분리한다.
- connection status pill을 누르면 Connections 화면으로 이동한다.
- Connections 화면에서는 현재 연결된 DB와 SQL Lab에서 조회 가능한 table 목록을 함께 보여준다.

## 구현

### 1. workspace mode 확장

`WorkspaceMode`에 `connections`를 추가했다.

```text
explore -> Charts
sql-lab -> SQL Lab
connections -> Connections
```

기존 page toolbar의 tab button은 제거하고, topbar navigation을 실제 mode switch로 사용한다.

### 2. Connections 화면

새 `ConnectionsWorkspace` component를 추가했다.

구성:

- connected database card
- read-only analytics DSN / writer fallback 여부
- masked DB address
- supported database type
- generated table 목록
- 각 table의 column metadata
- `Open in SQL Lab` action

`Open in SQL Lab`은 해당 generated table의 sample SELECT를 SQL Lab editor에 주입하고
SQL Lab 화면으로 이동한다.

### 3. Chart Builder 정리

Chart Builder control panel에서 database connection card를 제거했다. 이 정보는 이제
Connections 화면에서만 집중적으로 보여준다.

## 검증

```bash
cd frontend
npm run typecheck
npm run lint
npm run build
```

결과:

```text
passed
```

## 남은 범위

- 실제 DB address 입력/신규 연결 생성은 보안상 v1 범위에서 제외한다.
- 현재 Connections 화면은 “연결 생성 wizard”가 아니라 “현재 연결 상태 + 조회 가능한 generated table catalog” 화면이다.
