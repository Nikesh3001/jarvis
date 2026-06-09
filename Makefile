.PHONY: test lint typecheck clean run

test:
	python -m pytest tests/ -v

lint:
	python -m flake8 core/ memory/ tools/ --max-line-length=100 --exclude=__pycache__,venv

typecheck:
	python -m mypy core/ --ignore-missing-imports || echo "mypy optional"

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name "*.pyo" -delete 2>/dev/null || true

run:
	python jarvis.py

all: test lint
