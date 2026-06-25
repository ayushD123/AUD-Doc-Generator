# Architecture Notes

Architecture notes for the Oracle AUD Generator.

## Current Scope

The repository now contains a working local-first application rather than only
an empty skeleton. The active deployment shape is still intentionally simple:
FastAPI backend, Next.js frontend, SQLAlchemy with SQLite by default, local
filesystem storage by default, and a database-backed local worker loop for jobs.

Docker, Redis, authentication, and mandatory cloud services are still outside
the current boundary. Optional OCI adapters exist behind explicit environment
configuration and should remain disabled until a task requires them.

## Boundaries

- `frontend/`: Next.js and TypeScript user interface.
- `backend/`: FastAPI service layer and local APIs.
- `docs/`: Architecture notes, decisions, and workflow documentation.
- `scripts/`: Utility scripts for development and maintenance once needed.

## Deployment Intent

- Local development uses `uvicorn --reload`, `npm run dev`, and the local worker.
- The first OCI VM deployment uses systemd for the API, worker, and frontend.
- Nginx is the public reverse proxy; backend port `8000` and frontend port
  `3000` stay bound to `127.0.0.1`.
- Runtime data belongs outside the repository, for example under
  `/var/lib/aud-generator`.

See [deployment-oci-vm.md](deployment-oci-vm.md) for the operational runbook.

## Future Design Intent

- SQLite through SQLAlchemy first, with a path to Oracle Autonomous Database later.
- Local filesystem storage first, with a path to OCI Object Storage later.
- Database-backed job status first, processed by a local worker loop during
  development, with a path to OCI Queue workers later.
