.PHONY: setup run lint test docker-build docker-up docker-down docker-logs

setup:
	pip install -r requirements.txt
	cp -n .env.example .env || true

run:
	uvicorn src.main:app --reload

lint:
	black . && isort .

test:
	pytest tests/

docker-build:
	docker-compose build

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

docker-logs:
	docker-compose logs -f
