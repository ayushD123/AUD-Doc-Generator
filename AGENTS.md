# AGENTS.md

Guidance for future Codex work in this repository.

## Project Direction

- Build iteratively. Do not attempt full AUD generation in one pass.
- Keep the first milestones focused on a clean, testable application skeleton.
- Treat FDD as the golden source once AUD generation logic exists. If FDD conflicts with PPT, transcript, configuration workbook, or supporting material, FDD wins.
- After making any change,  review the code you just created.
Check for:
1. unnecessary complexity
2. missing tests
3. hardcoded paths
4. poor error handling
5. inconsistent naming
6. anything that will make future OCI migration difficult
Re-run and check health everytime, if there's any error in terminal, fix it automatically

## Current Boundaries

Do not add these until explicitly requested:

- OCI integration
- LLM calls
- Redis
- Authentication
- Document extraction
- Docker files
- Dependency installation

## Target Architecture

- Frontend: Next.js and TypeScript under `frontend/`.
- Backend: FastAPI and Python under `backend/`.
- Database: SQLAlchemy with local SQLite first, designed to allow a later Oracle Autonomous Database adapter.
- File storage: local filesystem first, designed to allow a later OCI Object Storage adapter.
- Jobs: database-backed job status first, designed to allow later OCI Queue workers.

## Coding Rules

- Prefer small, reviewable changes.
- Match existing project patterns before introducing new abstractions.
- Keep frontend and backend concerns separated.
- Add tests when behavior is introduced.
- Avoid committing generated artifacts, local environment files, caches, or dependency directories.
- Update documentation when architectural decisions change.
- After automatic tests or health checks, provide manual test steps with expected results for every change.
