.PHONY: install run test clean

install:
	uv pip install -r requirements.txt

run:
	uvicorn serve:app --host 0.0.0.0 --port 8000 --workers 1

test:
	pytest -q tests/test_serve.py

clean:
	find . -name "__pycache__" -type d -prune -exec rm -rf {} +
