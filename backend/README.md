# Backend

FastAPI backend skeleton for the Oracle AUD Generator.

This phase includes a minimal application structure, local settings, a health endpoint, and pytest coverage. It does not include a database, file uploads, OCI integration, authentication, document extraction, or LLM calls.

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

## Run Tests

From the `backend/` directory:

```powershell
python -m pytest
```

If your terminal is opened at the repository root, either run `cd backend` first or use:

```powershell
.\backend\.venv\Scripts\python.exe -m pytest
```
