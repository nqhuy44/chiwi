VENV := .venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip
UVICORN := $(VENV)/bin/uvicorn

REPORTS_DIR := reports

.PHONY: setup venv install run lint test test-integration test-all test-cov test-report clean-reports \
        docker-build docker-up docker-down docker-logs

venv:
	@test -d $(VENV) || python3 -m venv $(VENV)
	@echo "Virtual environment ready: $(VENV)"

install: venv
	$(PIP) install -r requirements.txt

setup: install
	cp -n .env.example .env || true
	@echo "Setup complete. Edit .env with your keys."

run: venv
	$(UVICORN) src.main:app --reload

lint: venv
	$(VENV)/bin/black . && $(VENV)/bin/isort .

test: venv
	$(VENV)/bin/pytest tests/ -v -m "not integration"

test-integration: venv
	$(VENV)/bin/pytest tests/ -v -m integration --tb=long

test-all: venv
	$(VENV)/bin/pytest tests/ -v --tb=long

test-cov: venv
	@mkdir -p $(REPORTS_DIR)
	$(VENV)/bin/pytest tests/ -v \
		--cov=src \
		--cov-report=term-missing \
		--cov-report=html:$(REPORTS_DIR)/coverage \
		--cov-report=xml:$(REPORTS_DIR)/coverage.xml

# MODE: unit (default) | integration | all
MODE ?= unit
MARKER_FLAG := $(if $(filter unit,$(MODE)),-m "not integration",$(if $(filter integration,$(MODE)),-m integration,))

test-report: venv
	@mkdir -p $(REPORTS_DIR)
	$(VENV)/bin/pytest tests/ -v $(MARKER_FLAG) \
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

docker-build:
	docker-compose build

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

docker-logs:
	docker-compose logs -f
