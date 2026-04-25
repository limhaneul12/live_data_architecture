# 18. Connections top navigation UI

작성일: 2026-04-25  
브랜치: `fect/structured-explore-query`

> 상태: 이후 `19_remove_connections_feature.md`에서 Connections 화면과
> connection-test API는 과제 범위 축소를 위해 삭제했다. 이 문서는 당시
> 검토/구현 이력으로만 남긴다.

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

## 추가 보강: DB address connection check

후속 요청으로 “깊게 갈 필요 없이 DB 주소 연결 성공까지만” 확인하는 범위가 추가됐다.

구현 범위:

- Connections 화면에 PostgreSQL address 입력 form 추가
- `POST /analytics/connection-test` backend endpoint 추가
- backend가 user-submitted DSN으로 `SELECT 1` connectivity check 수행
- 결과 address는 password masking 후 반환
- 성공/실패 결과를 Connections 화면에 표시

의도적으로 제외한 범위:

- 입력한 DSN을 서버 설정으로 영구 저장하지 않는다.
- SQL Lab/Chart Builder runtime connection을 즉시 교체하지 않는다.
- DB별 schema introspection이나 table 자동 생성은 하지 않는다.
- PostgreSQL 외 DB는 지원하지 않는다.

즉, 현재 Connections 화면은 “현재 연결 상태 + generated table catalog + DB address
connectivity check”까지만 담당한다.
