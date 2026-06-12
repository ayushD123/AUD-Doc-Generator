# Backend

FastAPI backend skeleton for the Oracle AUD Generator.

This phase includes a minimal application structure, local settings, a health endpoint, a SQLite-backed SQLAlchemy database foundation, project/job APIs, and pytest coverage. It does not include file uploads, OCI integration, authentication, document extraction, LLM calls, or Alembic migrations.

## Create a Virtual Environment

From the `backend/` directory:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If Python 3.11 is not installed, use any available Python 3.11+ runtime. For example:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

## Install Requirements

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Run the API

```powershell
uvicorn app.main:app --reload
```

The API will be available at:

```text
http://127.0.0.1:8000
```

Health check:

```text
GET http://127.0.0.1:8000/health
```

Expected response:

```json
{
  "status": "ok",
  "service": "aud-generator-api"
}
```

## Local Database

The backend uses SQLAlchemy 2.x with SQLite for local development.

Default database URL:

```text
sqlite:///./aud_generator.db
```

The app creates tables automatically on startup for local development. The SQLite database file is ignored by git.

`create_all()` creates missing tables, but it does not alter existing tables when model columns change. Until Alembic migrations are introduced, either delete `aud_generator.db` during local development or manually add simple nullable columns when needed.

To override the database URL for a local run:

```powershell
$env:DATABASE_URL = "sqlite:///./aud_generator.db"
uvicorn app.main:app --reload
```

The same `DATABASE_URL` setting is the future switch point for Oracle Autonomous Database once that integration is introduced.

## Current API Endpoints

```text
GET  /health
POST /projects
GET  /projects
GET  /projects/{project_id}
POST /projects/{project_id}/jobs
GET  /projects/{project_id}/jobs
```

## Run Tests

From the `backend/` directory:

```powershell
python -m pytest
```

If your terminal is opened at the repository root, either run `cd backend` first or use:

```powershell
.\backend\.venv\Scripts\python.exe -m pytest
```
