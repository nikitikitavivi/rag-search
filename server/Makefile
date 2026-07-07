.PHONY: install test cov lint format typecheck up down seed seed-docs logs

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

logs:
	docker-compose logs -f
