PYTHON_VERSION := 3.12.10
CHECK_PATHS := backend/app backend/tests
TEST_PATHS := backend/tests
TYPECHECK_PATHS := backend/app backend/tests
UV := UV_PROJECT_ENVIRONMENT=../.venv uv

.PHONY: install-local install install-prod install-qa install-stage \
	format format_check type_checking guardrails test ci \
	dev run db_init migrate db_upgrade makemigration db_revision \
	generate generator compose-build compose-up compose-down compose-logs

install-local:
	$(UV) sync --project backend --all-groups

install:
	$(UV) sync --project backend

install-prod:
	$(UV) sync --project backend --only-group prod

install-qa:
	$(UV) sync --project backend --only-group qa

install-stage:
	$(UV) sync --project backend --only-group stage

format:
	$(UV) run --project backend ruff format $(CHECK_PATHS)
	$(UV) run --project backend ruff check $(CHECK_PATHS) --fix

format_check:
	$(UV) run --project backend ruff format --check $(CHECK_PATHS)
	$(UV) run --project backend ruff check $(CHECK_PATHS)

type_checking:
	$(UV) run --project backend pyrefly check $(TYPECHECK_PATHS)

guardrails:
	PYTHONPATH=backend $(UV) run --project backend python -c "from app.shared.guardrails import ensure_dynamic_attribute_usage_clean; ensure_dynamic_attribute_usage_clean(); print('dynamic attribute usage check passed')"
	PYTHONPATH=backend $(UV) run --project backend python -c "from app.shared.guardrails import ensure_lazy_import_usage_clean; ensure_lazy_import_usage_clean(); print('lazy import usage check passed')"
	PYTHONPATH=backend $(UV) run --project backend python -c "from app.shared.guardrails import ensure_broad_types_clean; ensure_broad_types_clean(); print('Broad type usage check passed')"

test:
	$(UV) run --project backend python -m pytest $(TEST_PATHS)

ci: format_check type_checking guardrails test

dev:
	$(UV) run --project backend uvicorn app.main:app --reload --port 8000 --app-dir backend --no-access-log

run:
	$(UV) run --project backend uvicorn app.main:app --host 0.0.0.0 --port 8000 --app-dir backend --no-access-log

db_init:
	@echo "db_init target is reserved for database bootstrap integration."

migrate db_upgrade:
	@echo "Migration target is reserved for Alembic integration."

makemigration db_revision:
	@test -n "$(MESSAGE)" || (echo "Usage: MESSAGE='schema change' make makemigration" && exit 1)
	@echo "Create migration revision: $(MESSAGE)"

generate generator:
	@test -n "$(word 2,$(MAKECMDGOALS))$(APP_NAME)" || (echo "Usage: make generate <domain> or make generate APP_NAME=<domain>" && exit 1)
	@domain="$(or $(APP_NAME),$(word 2,$(MAKECMDGOALS)))"; \
	if ! echo "$$domain" | grep -Eq '^[a-z][a-z0-9_]*$$'; then \
		echo "Domain must be snake_case and start with a lowercase letter"; exit 1; \
	fi; \
	mkdir -p backend/app/$$domain/{application,domain/repositories,infrastructure/repositories,interface/{schemas,router}} backend/tests/$$domain; \
	touch backend/app/$$domain/containers.py backend/tests/$$domain/__init__.py; \
	echo "Generated domain scaffold: $$domain"

compose-build:
	docker compose build

compose-up:
	docker compose up

compose-down:
	docker compose down

compose-logs:
	docker compose logs -f

%:
	@:
