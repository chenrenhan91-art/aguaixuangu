PYTHON ?= python3
PIP ?= $(PYTHON) -m pip

.PHONY: install check-trade-day snapshot

install:
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements-pipeline.txt

check-trade-day:
	$(PYTHON) -m data_pipeline.jobs.check_trade_day

snapshot:
	$(PYTHON) -m data_pipeline.jobs.generate_daily_candidates
