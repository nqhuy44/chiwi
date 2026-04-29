VENV := .venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip
UVICORN := $(VENV)/bin/uvicorn

REPORTS_DIR := reports

.PHONY: setup venv install run ngrok webhook-set webhook-delete lint test test-integration test-all test-cov test-report clean-reports \
        docker-build docker-up docker-down docker-logs backup

venv:
	@test -d $(VENV) || python3 -m venv $(VENV)
	@echo "Virtual environment ready: $(VENV)"

install: venv
	$(PIP) install -r requirements.txt

setup: install
	cp -n .env.example .env || true
	@echo "Setup complete. Edit .env with your keys."

run: venv
	$(UVICORN) src.main:app --host 0.0.0.0 --reload

migrate: venv
	PYTHONPATH=. $(PYTHON) scripts/migrate_to_beanie.py

seed-profiles: venv
	PYTHONPATH=. $(PYTHON) scripts/seed_profiles.py

backup:
	bash scripts/backup_db.sh

ngrok:
	ngrok http 8000

webhook-set:
	bash scripts/set_webhook.sh

webhook-delete:
	bash scripts/set_webhook.sh --delete

lint: venv
	$(VENV)/bin/black . && $(VENV)/bin/isort .

test: venv
	$(VENV)/bin/pytest tests/unit/ -v

test-integration: venv
	$(VENV)/bin/pytest tests/integration/ -v --tb=long

test-all: venv
	$(VENV)/bin/pytest tests/ -v --tb=long

test-cov: venv
	@mkdir -p $(REPORTS_DIR)
	$(VENV)/bin/pytest tests/unit/ -v \
		--cov=src \
		--cov-report=term-missing \
		--cov-report=html:$(REPORTS_DIR)/coverage \
		--cov-report=xml:$(REPORTS_DIR)/coverage.xml

# MODE: unit (default) | integration | all
MODE ?= unit
TEST_DIR := $(if $(filter unit,$(MODE)),tests/unit/,$(if $(filter integration,$(MODE)),tests/integration/,tests/))

test-report: venv
	@mkdir -p $(REPORTS_DIR)
	$(VENV)/bin/pytest $(TEST_DIR) -v \
		--html=$(REPORTS_DIR)/test-report.html \
		--self-contained-html \
		--cov=src \
		--cov-report=term-missing \
		--cov-report=html:$(REPORTS_DIR)/coverage
	@echo ""
	@echo "Test report:     $(REPORTS_DIR)/test-report.html"
	@echo "Coverage report: $(REPORTS_DIR)/coverage/index.html"

clean-reports:
	rm -rf $(REPORTS_DIR) .coverage .pytest_cache

# Docker Configuration
DOCKER_REPO := nqh44/chiwi
VERSION ?= latest

docker-build:
	docker build -t $(DOCKER_REPO):local .

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

docker-logs:
	docker-compose logs -f

release:
	@if [ -z "$(VERSION)" ] || [ "$(VERSION)" = "latest" ]; then \
		echo "Error: Please specify a version, e.g., make release VERSION=1.0.0"; \
		exit 1; \
	fi
	docker build -t $(DOCKER_REPO):$(VERSION) .
	docker tag $(DOCKER_REPO):$(VERSION) $(DOCKER_REPO):latest
	docker push $(DOCKER_REPO):$(VERSION)
	docker push $(DOCKER_REPO):latest
