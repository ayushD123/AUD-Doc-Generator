# Oracle AUD Generator

Internal Oracle Application Understanding Document (AUD) Generator project.

This repository will evolve into a tool that helps generate Application Understanding Documents from source materials such as FDDs, KT presentations, KT transcripts, configuration workbooks, template AUDs, final AUD samples, and supporting documents.

## Current Phase

The current phase is a clean, testable local development application skeleton. It includes the FastAPI/SQLite backend, the Next.js project workspace, local uploads, an optional OCI Object Storage adapter, deterministic extraction, source priority reporting, AUD planning, open point extraction, and rule-based editable DOCX draft output with frontend download controls.

It intentionally does not include Docker configuration, authentication, Redis, OCI Queue workers, speech transcription, or LLM calls.

## Source Priority

When document generation behavior is implemented later, the FDD should be treated as the golden source. If the FDD conflicts with a KT PPT, transcript, configuration workbook, or supporting document, the FDD wins.

## Target Stack

- Frontend: Next.js with TypeScript
- Backend: FastAPI with Python
- Database: local SQLite through SQLAlchemy, designed for a later move to Oracle Autonomous Database
- File storage: local filesystem by default, with an optional OCI Object Storage adapter
- Async jobs: simple database-backed job status, designed for a later move to OCI Queue workers

## Local Development Goals

- Keep the repository structure simple and easy to test.
- Add features iteratively rather than building the full AUD generator at once.
- Preserve clear boundaries between frontend, backend, documentation, and scripts.
- Prefer local-only development defaults until cloud integrations are explicitly introduced.
