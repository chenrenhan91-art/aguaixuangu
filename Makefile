PYTHON ?= python3
PIP ?= $(PYTHON) -m pip

.PHONY: backend-install backend-dev backend-test pipeline-refresh pipeline-candidates

backend-install:
	$(PIP) install -e ./backend[dev,pipeline]

backend-dev:
	cd backend && uvicorn app.main:app --reload

backend-test:
	cd backend && pytest

pipeline-refresh:
	$(PYTHON) -m data_pipeline.jobs.daily_refresh

pipeline-candidates:
	$(PYTHON) -m data_pipeline.jobs.generate_daily_candidates
