.PHONY: up down logs migrate reset shell-db lint test

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f

migrate:
	cd backend && alembic upgrade head

reset:
	docker compose down -v
	docker compose up -d
	sleep 3
	cd backend && alembic upgrade head

shell-db:
	docker compose exec postgres psql -U tenderit tenderit

lint:
	cd backend && ruff check . && ruff format --check .
	cd frontend && npx tsc --noEmit

test:
	cd backend && pytest -x -q
	cd frontend && npx jest --passWithNoTests
