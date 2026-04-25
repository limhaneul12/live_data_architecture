# 16. Analytics connection selector UI

## 배경

SQL Lab/Explore가 어떤 DB를 보고 있는지 사용자가 UI에서 바로 확인할 수 있어야 한다.
다만 브라우저에서 임의 DB address를 입력해 backend가 접속하게 만들면 SSRF, credential
노출, 내부망 스캔 위험이 커진다.

## 결정

v1에서는 안전한 connection metadata 표시만 제공한다.

- DB 선택 UI는 PostgreSQL 단일 선택으로 표시한다.
- address 입력칸은 password-masked DSN을 read-only로 보여준다.
- 실제 runtime 연결은 기존 `ANALYTICS_DATABASE_DB_ADDRESS` 환경변수 기반이다.
- 임의 address submit/connect 기능은 v1에서 제외한다.

## Backend 변경

추가 endpoint:

```text
GET /analytics/connection
```

반환 정보:

- `database`: `postgresql`
- `address`: password-masked DSN
- `source`: `analytics_read_only_dsn` 또는 `writer_fallback_dsn`
- `editable`: `false`
- `supported_databases`: 현재는 `["postgresql"]`
- `message`: UI 안내 문구

## Frontend 변경

Chart Builder control panel 상단에 `Database` 카드가 추가됐다.

- DB type select: PostgreSQL만 표시, disabled
- Address input: password-masked DSN 표시, read-only
- read-only DSN 사용 여부 메시지 표시

## 후속 확장 조건

정말 runtime에서 DB address를 입력받아 연결하려면 아래가 선행되어야 한다.

1. 인증/관리자 권한
2. backend-side saved connection catalog
3. host allowlist 또는 private network egress 제한
4. secret 암호화 저장
5. `test-connection` endpoint의 timeout/rate limit
6. DB별 generated view contract 검증

## 검증

```bash
ruff format/check
pytest test_analytics_connection.py test_analytics_router.py test_platform_config.py
npm run typecheck
npm run lint
make ci
npm run build
docker compose config --quiet
git diff --check
uvx bandit -r backend/app event_generator -x backend/tests,event_generator/tests -q
```

결과:

- backend full gate: 165 passed
- frontend typecheck/lint/build 통과
- compose config/diff check 통과
- Bandit은 기존 SQL Lab raw SQL wrapper(B608)와 deterministic generator random(B311)을
  계속 지적하며, 이번 connection metadata 변경에서 새 high finding은 확인하지 못했다.
