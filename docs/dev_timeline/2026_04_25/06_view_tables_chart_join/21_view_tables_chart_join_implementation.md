# View Tables and Chart JOIN implementation notes

## Implemented backend behavior

- Added `analytics_view_tables` metadata table through Alembic revision `20260425_0004`.
- Added a dynamic catalog service that returns built-in generated views plus user-created view table datasets.
- Added View Tables APIs:
  - `GET /analytics/view-tables`
  - `POST /analytics/view-tables/preview`
  - `POST /analytics/view-tables`
- View table creation accepts user `SELECT` SQL, validates it through the existing SQL policy, then the backend generates `CREATE OR REPLACE VIEW`.
- View table source SQL may reference `events` plus already-exposed datasets.
- SQL Lab still does not expose raw `events`; saved view tables become datasets and can be queried through the normal dataset allowlist.
- Structured Chart Builder requests now support one 1-hop JOIN from the base dataset to another dataset.
- Chart JOIN SQL is generated with SQLAlchemy Core, not raw SQL assembled by the frontend.

## Implemented frontend behavior

- Added top navigation item: `View Tables`.
- View Tables page supports:
  - view table name
  - description
  - source SELECT editor
  - preview
  - save as dataset
  - saved view table list
  - open saved dataset in Charts
- Charts page supports:
  - enabling a single JOIN target
  - selecting join type (`INNER`, `LEFT`)
  - selecting base key and join key
  - selecting columns from both datasets
  - generated SQL preview for joined chart queries

## Boundary decisions

- No external DB connection management.
- No dashboard persistence.
- No arbitrary DDL input from the user.
- No multi-hop join graph builder yet.
- Permissions/auth are intentionally not solved in this pass per current product direction.

## Verification

- Backend event analytics tests pass.
- Full `make ci` pass was collected after backend implementation.
- Frontend `typecheck`, `lint`, and `build` pass after UI implementation.
