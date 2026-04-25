# README submission pack and verification checklist

## 배경

과제 제출 전에 root README가 구현 설명 위주로 길어져 있어, 요구사항별 충족 위치와 실행/검증 방법을 한눈에 보기 어려웠다. 실제 스크린샷 파일은 최종 실행 환경에서 다시 캡처해야 하지만, 어떤 화면을 어디에 저장할지는 먼저 정리할 수 있었다.

## 반영 내용

- `README.md` 상단에 제출 요약과 전체 pipeline을 추가했다.
- Step 1~5 요구사항별 구현 위치와 확인 포인트를 table로 정리했다.
- `docker compose up --build` 빠른 실행 방법과 기본 host port를 명시했다.
- Analytics API 목록에 `view-tables` endpoints를 추가했다.
- SQL 제한 정책을 generated/saved view allowlist 기준으로 최신화했다.
- Frontend 범위를 Charts / SQL Lab / View Tables로 정리했다.
- 제출용 screenshot placeholder 경로를 잡았다.
- 제출 전 verification checklist와 기능 smoke 순서를 README에 추가했다.
- `docs/remaining_work.md`는 README 정리 완료 상태와 실제 증빙 캡처 남은 항목을 분리했다.

## Screenshot placeholder

실제 PNG는 제출 직전에 최신 Docker stack에서 다시 캡처한다. README에는 아래 경로를 placeholder로 고정했다.

```text
docs/screenshots/01_health_ready.png
docs/screenshots/02_event_ingest.png
docs/screenshots/03_charts_builder.png
docs/screenshots/04_sql_lab_table.png
docs/screenshots/05_view_tables.png
docs/screenshots/06_sql_guardrail_rejection.png
```

## 검증 계획

문서 변경이지만 제출 README의 명령이 실제 프로젝트 명령과 맞는지 확인한다.

```bash
git diff --check
make ci
make frontend-ci
cd frontend && npm audit --omit=dev --audit-level=moderate
docker compose config --quiet
```

## 남은 리스크

- 실제 screenshot PNG는 아직 repo에 추가하지 않았다. placeholder는 의도적인 제출 준비 항목이다.
- Docker live smoke는 최종 제출 환경의 port 점유 상태에 따라 다시 실행해야 한다.
