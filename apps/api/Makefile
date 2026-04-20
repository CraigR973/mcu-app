.PHONY: dev lint typecheck test install

VENV := .venv
PYTHON := $(VENV)/bin/python
UV := uv

install:
	$(UV) venv $(VENV) --python 3.12
	$(UV) pip install -e ".[dev]" --python $(PYTHON)

dev:
	$(PYTHON) -m uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

lint:
	$(VENV)/bin/ruff check src/

typecheck:
	$(VENV)/bin/mypy src/

test:
	$(VENV)/bin/pytest tests/ -v
