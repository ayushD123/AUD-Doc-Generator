# Oracle AUD Generator

Internal Oracle Application Understanding Document (AUD) Generator project.

This repository will evolve into a tool that helps generate Application Understanding Documents from source materials such as FDDs, KT presentations, KT transcripts, configuration workbooks, template AUDs, final AUD samples, and supporting documents.

## Current Phase

The current phase is a clean, testable local development application skeleton. It includes the FastAPI/SQLite backend, the Next.js project workspace with collapsible detail sections, local uploads, an optional OCI Object Storage adapter, optional OCI Queue publishing/worker support, optional OCI Speech media transcription, optional OCI Document Understanding enrichment, normalized evidence indexing with read-only frontend review, an optional OCI Generative AI LLM wrapper, AI source summary generation with read-only frontend review, AI-enhanced AUD plan refinement for later drafting, deterministic section evidence packs, AI section draft generation for review, deterministic extraction, source priority reporting, AUD planning, open point extraction, and rule-based editable DOCX draft output with frontend download controls.

It intentionally does not include Docker configuration, authentication, Redis, or final LLM-driven DOCX AUD generation.

## Source Priority

When document generation behavior is implemented later, the FDD should be treated as the golden source. If the FDD conflicts with a KT PPT, transcript, configuration workbook, or supporting document, the FDD wins.

## Target Stack

- Frontend: Next.js with TypeScript
- Backend: FastAPI with Python
- Database: local SQLite through SQLAlchemy, designed for a later move to Oracle Autonomous Database
- File storage: local filesystem by default, with an optional OCI Object Storage adapter
- Async jobs: database-backed job status with local polling by default and optional OCI Queue publishing/worker support

## Local Development Goals

- Keep the repository structure simple and easy to test.
- Add features iteratively rather than building the full AUD generator at once.
- Preserve clear boundaries between frontend, backend, documentation, and scripts.
- Prefer local-only development defaults until cloud integrations are explicitly introduced.

## LLM Safeguards

The backend uses `OCI_GENAI_MAX_INPUT_CHARS=200000` and
`OCI_GENAI_MAX_OUTPUT_TOKENS=16000` as current development defaults. AI prompt
builders reserve room for system and JSON wrapper instructions before applying
the input safeguard, which avoids failing on bounded AUD planning and source
summary prompts after wrapper text is added.

For OCI GPT-style models that only support the default model temperature, keep
`OCI_GENAI_TEMPERATURE=1`.

Section evidence packs use `SECTION_EVIDENCE_MAX_CHARS=30000` by default to keep
future section-drafting prompts bounded and traceable.
