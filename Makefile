.PHONY: setup test run migrate verify
setup:
	python3 -m venv .venv
	.venv/bin/python -m pip install -r backend/requirements-dev.txt
test:
	cd backend && ../.venv/bin/python -m pytest -q
run:
	cd backend && ../.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
migrate:
	cd backend && ../.venv/bin/python -m alembic upgrade head
verify:
	./scripts/verify.sh
