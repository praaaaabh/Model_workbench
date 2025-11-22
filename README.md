# Model Workbench

This repository provides a starter backend and frontend for the Model Workbench project.

## Backend (FastAPI)
- Located in `backend/`
- Managed with Poetry and targets Python 3.11
- Linting/formatting via Ruff and Black
- Testing with Pytest
- Basic `/health` endpoint

### Backend commands
```bash
make backend-install  # Install backend dependencies
make backend-lint     # Run Ruff and Black checks
make backend-format   # Format with Black
make backend-test     # Run Pytest
```

To run the API locally:
```bash
cd backend
poetry run uvicorn app.main:app --reload
```

## Frontend (Vite + React + TypeScript)
- Located in `frontend/`
- Uses MUI for styling and React Query for data fetching
- React Router set up with a basic layout and placeholder routes

### Frontend commands
```bash
make frontend-install  # Install frontend dependencies
make frontend-lint     # Run ESLint
make frontend-build    # Build the app for production
```

To start the dev server:
```bash
cd frontend
npm run dev
```

## Continuous Integration
GitHub Actions workflows run linting and tests/build for both backend and frontend.
