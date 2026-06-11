# Architecture Notes

Initial architecture notes for the Oracle AUD Generator.

## Phase 1 Scope

Create a local repository skeleton only. No app code, dependencies, Docker files, OCI integrations, LLM calls, Redis, authentication, or document extraction are included.

## Planned Boundaries

- `frontend/`: Next.js and TypeScript user interface.
- `backend/`: FastAPI service layer and local APIs.
- `docs/`: Architecture notes, decisions, and workflow documentation.
- `scripts/`: Utility scripts for development and maintenance once needed.

## Future Design Intent

- SQLite through SQLAlchemy first, with a path to Oracle Autonomous Database later.
- Local filesystem storage first, with a path to OCI Object Storage later.
- Database-backed job status first, with a path to OCI Queue workers later.
