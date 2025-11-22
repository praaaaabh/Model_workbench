.PHONY: backend-install backend-lint backend-format backend-test frontend-install frontend-lint frontend-build

backend-install:
cd backend && poetry install --with dev

backend-lint:
cd backend && poetry run ruff check . && poetry run black --check .

backend-format:
cd backend && poetry run black .

backend-test:
cd backend && poetry run pytest

frontend-install:
cd frontend && npm install

frontend-lint:
cd frontend && npm run lint

frontend-build:
cd frontend && npm run build
