PYTHON ?= python3
PIP ?= $(PYTHON) -m pip

.PHONY: install check-trade-day trade-calendar-sql snapshot history-index

install:
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements-pipeline.txt

check-trade-day:
	$(PYTHON) -m data_pipeline.jobs.check_trade_day

trade-calendar-sql:
	$(PYTHON) -m data_pipeline.jobs.export_trade_calendar_sql

snapshot:
	A_SHARE_WRITE_DATED_SNAPSHOT=1 $(PYTHON) -m data_pipeline.jobs.generate_daily_candidates
	$(PYTHON) -m data_pipeline.jobs.rebuild_snapshot_history

history-index:
	$(PYTHON) -m data_pipeline.jobs.rebuild_snapshot_history
