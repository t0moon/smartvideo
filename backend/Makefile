.PHONY: install test run clean docker-build docker-up

install:
	pip install -e .[all]

install-dev:
	pip install -e .[dev,web]

test:
	python -m pytest tests -v --tb=short

run:
	uvicorn app.main:app --reload --port 8765

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	rm -rf data/projects/* 2>/dev/null || true

docker-build:
	docker-compose build

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

docker-logs:
	docker-compose logs -f
