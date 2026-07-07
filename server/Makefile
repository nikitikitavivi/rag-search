.PHONY: install test cov lint format typecheck db-up db-down seed

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

db-up:
	docker compose up -d db

db-down:
	docker compose down

seed:
	python scripts/seed_fixtures.py

dev:
	docker compose up -d db && \
	sleep 3 && \
	uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
