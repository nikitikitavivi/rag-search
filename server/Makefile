.PHONY: install test cov lint format typecheck up down seed seed-docs seed-all seed-all-fresh migrate logs

-include .env
export

install:
	pip install -e ".[dev]"

test:
	pytest tests/ -v

cov:
	pytest tests/ --cov=app --cov-report=term-missing

lint:
	ruff check .

format:
	ruff check --fix .

typecheck:
	mypy app

up:
	docker-compose up -d

down:
	docker-compose down

seed:
	python scripts/seed_fixtures.py

seed-docs:
	python scripts/seed_documents.py

seed-all: seed seed-docs

seed-all-fresh: migrate seed seed-docs

migrate:
	alembic upgrade head

logs:
	docker-compose logs -f
