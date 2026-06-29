# Oracle AUD Generator

Internal Oracle Application Understanding Document (AUD) Generator project.

This repository will evolve into a tool that helps generate Application Understanding Documents from source materials such as FDDs, KT presentations, KT transcripts, configuration workbooks, template AUDs, final AUD samples, and supporting documents.

## Current Phase

The current phase is a clean, testable application that still defaults to
local-first operation. It includes the FastAPI/SQLite backend, the Next.js
project workspace with collapsible detail sections, local uploads, optional OCI
adapters for later cloud services, normalized evidence indexing with read-only
frontend review, source summary and section draft workflows, deterministic
extraction, source priority reporting, AUD planning, open point extraction,
AI Open Points refinement, and rule-based editable DOCX draft output with
frontend download controls. When a project includes an Email Id, the backend
also sends an AUD-ready notification after the generated DOCX is available, with
an optional backend download link when `EMAIL_NOTIFICATION_DOWNLOAD_BASE_URL` is
configured.

It intentionally does not include Docker configuration, authentication, Redis, or final LLM-driven DOCX AUD generation.

## Deployment

The recommended first deployment target is a single Ubuntu OCI VM with systemd
services for the backend API, local worker, and Next.js frontend behind Nginx.
Use either the SQLite local-first baseline or the Oracle ADB environment profile
documented in the runbook. Keep local runtime files outside the repository under
`/var/lib/aud-generator`; keep ADB wallet files outside the repository as well.

Use the step-by-step runbook in
[docs/deployment-oci-vm.md](docs/deployment-oci-vm.md).

## Source Priority

When document generation behavior is implemented later, the FDD should be treated as the golden source. If the FDD conflicts with a KT PPT, transcript, configuration workbook, or supporting document, the FDD wins.

## Target Stack

- Frontend: Next.js with TypeScript
- Backend: FastAPI with Python
- Database: local SQLite through SQLAlchemy by default, with optional Oracle Autonomous Database configuration through python-oracledb
- File storage: local filesystem by default, with an optional OCI Object Storage adapter
- Async jobs: database-backed job status with a local worker loop by default and optional OCI Queue publishing/worker support

## Local Development Goals

- Keep the repository structure simple and easy to test.
- Add features iteratively rather than building the full AUD generator at once.
- Preserve clear boundaries between frontend, backend, documentation, and scripts.
- Prefer local-only development defaults until cloud integrations are explicitly introduced.

## Local Worker

Run the backend API and the local worker as separate terminals during local
development. The API creates database-backed jobs, and the worker loop picks
them up automatically:

```powershell
cd backend
python -m app.workers.local_worker --loop
```

The one-shot command remains available for tests and manual debugging:

```powershell
python -m app.workers.local_worker
```

## Database Configuration

SQLite remains the default for local development:

```text
DB_PROVIDER=sqlite
DATABASE_URL=
```

When `DATABASE_URL` is set, it is used directly. Otherwise `DB_PROVIDER`
selects the database backend. For Oracle Autonomous Database, configure:

```text
DB_PROVIDER=oracle
ORACLE_DB_USER=<database-user>
ORACLE_DB_PASSWORD=<database-password>
ORACLE_DB_DSN=<tns-alias-or-connect-descriptor>
ORACLE_DB_WALLET_DIR=<path-outside-repo-to-wallet>
ORACLE_DB_WALLET_PASSWORD=<optional-wallet-password>
ORACLE_DB_ECHO=false
ORACLE_DB_POOL_SIZE=5
ORACLE_DB_MAX_OVERFLOW=10
ORACLE_DB_POOL_PRE_PING=true
```

Wallet files must stay outside the repository. Large uploaded files and
generated documents remain in local storage or Object Storage; the database
stores metadata and storage keys only.

## LLM Safeguards

The backend uses `OCI_GENAI_MAX_INPUT_CHARS=200000` and
`OCI_GENAI_MAX_OUTPUT_TOKENS=16000` as current development defaults. AI prompt
builders reserve room for system and JSON wrapper instructions before applying
the input safeguard, which avoids failing on bounded AUD planning and source
summary prompts after wrapper text is added.

For OCI GPT-style models that only support the default model temperature, keep
`OCI_GENAI_TEMPERATURE=1`.

In classic OCI SDK mode, the wrapper uses `maxTokens` automatically for
`meta.llama-4...` model IDs such as Llama 4 Maverick. For opaque model OCIDs,
it falls back from `maxCompletionTokens` to `maxTokens` if OCI returns the
unsupported-parameter error.

Both OCI LLM provider wrappers retry transient throttling errors such as HTTP
429 with exponential backoff. Tune `OCI_GENAI_RETRY_MAX_ATTEMPTS`,
`OCI_GENAI_RETRY_BASE_SECONDS`, and `OCI_GENAI_RETRY_MAX_SECONDS` when using
Gemini Flash models across many AUD sections.

Section evidence packs use `SECTION_EVIDENCE_MAX_CHARS=30000` by default to keep
future section-drafting prompts bounded and traceable.

DOCX generation now starts from an AUD template before adding generated draft
content. An uploaded file with `source_role=aud_template` or the legacy
`template_aud` role is used first; otherwise the backend validates and uses
`DEFAULT_AUD_TEMPLATE_PATH`, which defaults to
`/backend/template/AUD_Editable_Template.docx`. The generator preserves the
template cover page and styles, removes stale sample body placeholders, and uses
`TemplatePopulationService` to build a clean intermediate document model from
the final AI-enhanced AUD plan, section drafts, selected tables/images, and
LLM-enhanced Open Points. Reviewed AI section drafts are preferred when
available; otherwise deterministic source-backed content is rendered. The
`generate-docx` job accepts options for AI draft usage, draft-status sections,
images, and Open Points while keeping FDD as the golden source and requiring
internal review before customer sharing. Before images are inserted,
`ImageDeduplicationService` removes exact, source-reference, perceptual, and
safe metadata duplicates, excludes template placeholder screenshots, retains the
best-quality candidate, and stores the dedup report in generated document
metadata.

DOCX tables are rendered through `DOCXTableRenderer`. Markdown tables,
pipe-delimited tables, selected draft/evidence tables, extracted DOCX/PPTX
tables, spreadsheet-style row data, and Open Points are normalized into real
Word tables with visible grid borders, bold/repeating headers where supported,
aligned cells, and practical column widths. Multi-line table cells and rows
with intentionally blank leading cells are preserved so process assignment and
orchestration tables do not collapse into paragraph dumps. Malformed or
ambiguous table text is left as paragraph content only when it cannot be
confidently parsed, and the fallback reason is logged. Source content is carried
through as refined readable paragraphs rather than replaced with generic
source-detail or summary notes.

## AI Open Points Refinement

`POST /projects/{project_id}/jobs/refine-open-points-ai` queues
`refine_open_points_ai`. The worker sends existing Open Points plus Open Point
candidates from Source Summaries, AUD Plans, and Section Drafts to the configured
LLM as strict JSON. The refinement keeps only unresolved questions/manual
actions, excludes Closed/Resolved/Aligned/Done items, respects FDD as golden
source, marks duplicate existing Open Points as `Removed`, creates refined
`Open` items, returns readable evidence text for review, and exposes refinement
metadata separately in the Open Points API response.

Final DOCX generation uses only `llm_enhanced` Open Points with status `Open`.
Raw extracted Open Points are treated as refinement candidates and are not
inserted into the final AUD.
