# Backend

FastAPI backend skeleton for the Oracle AUD Generator.

This phase includes a minimal application structure, local settings, a health endpoint, a SQLite-backed SQLAlchemy database foundation, project/job APIs, local file upload metadata, local filesystem storage by default, an optional OCI Object Storage adapter, optional OCI Queue publishing and worker support, optional OCI Speech media transcription, optional OCI Document Understanding enrichment, normalized evidence indexing, an optional OCI Generative AI LLM wrapper, AI source summary generation, AI section draft generation, transcript extraction, DOCX extraction, PPTX extraction, spreadsheet extraction, deterministic AUD planning, open point extraction, AI Open Points refinement, rule-based DOCX draft generation, and pytest coverage. It does not include Redis, authentication, final LLM-driven DOCX AUD generation, template-perfect AUD generation, or Alembic migrations.

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

## File Storage

The backend uses a storage abstraction with two implementations:

- `LocalStorageService`
- `OCIObjectStorageService`

Local filesystem storage is the default for development and tests:

```text
STORAGE_BACKEND=local
```

Uploaded files are stored with keys under:

```text
projects/{project_id}/uploads/{file_id}_{filename}
```

When `STORAGE_BACKEND=local`, those keys map under:

```text
backend/storage/
```

Extracted PPT images use:

```text
projects/{project_id}/extracted_images/{uploaded_file_id}/{image_name}
```

Generated DOCX drafts use:

```text
projects/{project_id}/outputs/{filename}
```

Default local storage root:

```text
LOCAL_STORAGE_ROOT=storage
```

To override it:

```powershell
$env:LOCAL_STORAGE_ROOT = "storage"
uvicorn app.main:app --reload
```

### OCI Object Storage

OCI Object Storage is optional. Local storage remains the default and tests do
not require OCI credentials.

Install requirements after pulling the OCI adapter changes:

```powershell
python -m pip install -r requirements.txt
```

Configure the OCI Python SDK config file first, typically at:

```text
%USERPROFILE%\.oci\config
```

Then set:

```powershell
$env:STORAGE_BACKEND = "oci"
$env:OCI_BUCKET_NAME = "<bucket-name>"
$env:OCI_NAMESPACE = "<object-storage-namespace>"
$env:OCI_REGION = "us-ashburn-1"
$env:OCI_CONFIG_FILE = "$env:USERPROFILE\.oci\config"
$env:OCI_PROFILE = "DEFAULT"
uvicorn app.main:app --reload
```

`OCI_COMPARTMENT_OCID` is available as optional configuration for future bucket
management flows, but the current adapter expects the bucket to already exist.
The app uses SDK config-file authentication first; instance principals and
resource principals are not wired in this phase.

Large OCI uploads use multipart parallel upload by default once the file is at
least 50 MiB. Tune these values if the network or tenancy behaves better with
larger parts or fewer workers:

```powershell
$env:OCI_MULTIPART_UPLOAD_THRESHOLD_BYTES = "52428800"
$env:OCI_MULTIPART_UPLOAD_PART_SIZE_BYTES = "10485760"
$env:OCI_MULTIPART_UPLOAD_PARALLEL_WORKERS = "4"
```

The database stores storage keys, not OCI URLs. Upload, extraction image writes,
DOCX output writes, and generated-document downloads go through the active
storage implementation.

Spreadsheet extraction reads only the first configured number of meaningful rows per visible sheet.

Default row cap:

```text
MAX_SPREADSHEET_ROWS_PER_SHEET=200
```

To override it:

```powershell
$env:MAX_SPREADSHEET_ROWS_PER_SHEET = "100"
uvicorn app.main:app --reload
```

## Current API Endpoints

```text
GET  /health
POST /projects
GET  /projects
GET  /projects/{project_id}
POST /projects/{project_id}/files
GET  /projects/{project_id}/files
POST /projects/{project_id}/jobs/classify-files
POST /projects/{project_id}/jobs/extract-transcripts
POST /projects/{project_id}/jobs/extract-docx
POST /projects/{project_id}/jobs/transcribe-media
POST /projects/{project_id}/jobs/extract-pptx
POST /projects/{project_id}/jobs/extract-spreadsheets
POST /projects/{project_id}/jobs/extract-all
POST /projects/{project_id}/jobs/generate-aud-plan
POST /projects/{project_id}/jobs/build-evidence-index
POST /projects/{project_id}/jobs/generate-source-summaries-ai
POST /projects/{project_id}/jobs/enhance-aud-plan-ai
POST /projects/{project_id}/jobs/build-section-evidence-packs
POST /projects/{project_id}/jobs/generate-section-drafts-ai
POST /projects/{project_id}/jobs/enrich-document-understanding
POST /projects/{project_id}/jobs/extract-open-points
POST /projects/{project_id}/jobs/refine-open-points-ai
POST /projects/{project_id}/jobs/generate-docx
POST /projects/{project_id}/generate-aud
GET  /projects/{project_id}/generate-aud/status
POST /projects/{project_id}/jobs
GET  /projects/{project_id}/jobs
GET  /projects/{project_id}/extracted-content
GET  /projects/{project_id}/evidence-items
GET  /projects/{project_id}/source-summaries
GET  /projects/{project_id}/section-evidence-packs
GET  /projects/{project_id}/section-drafts
GET  /projects/{project_id}/source-priority-report
GET  /projects/{project_id}/aud-plan
GET  /projects/{project_id}/open-points
GET  /projects/{project_id}/generated-documents
GET  /projects/{project_id}/generated-documents/{document_id}/download
```

## File Upload Examples

Upload an FDD file:

```powershell
curl.exe -X POST "http://127.0.0.1:8000/projects/{project_id}/files" `
  -F "source_role=fdd" `
  -F "file=@C:\path\to\document.docx"
```

Upload a supporting PDF:

```powershell
curl.exe -X POST "http://127.0.0.1:8000/projects/{project_id}/files" `
  -F "source_role=supporting_doc" `
  -F "file=@C:\path\to\supporting.pdf"
```

List uploaded files for a project:

```powershell
curl.exe "http://127.0.0.1:8000/projects/{project_id}/files"
```

Allowed file extensions:

```text
.docx, .pptx, .xlsx, .xlsm, .txt, .pdf, .jpg, .jpeg, .png, .tif, .tiff, .mp3, .m4a, .mp4
```

Allowed `source_role` values:

```text
aud_template, template_aud, final_aud_sample, fdd, kt_ppt, kt_session, kt_transcript, config_workbook, supporting_doc, unknown
```

`aud_template` is the preferred explicit AUD template role. `template_aud`
remains accepted for older uploads.

## Async Jobs

Jobs are always stored in the database first. `JOB_QUEUE_BACKEND=local` keeps
the existing local polling flow, and `JOB_QUEUE_BACKEND=oci` additionally
publishes a message to OCI Queue after the `Job` row is created. Redis and
Celery are not used.

Local mode is the default:

```text
JOB_QUEUE_BACKEND=local
```

Create a file classification job:

```powershell
curl.exe -X POST "http://127.0.0.1:8000/projects/{project_id}/jobs/classify-files"
```

Create a plain text transcript extraction job:

```powershell
curl.exe -X POST "http://127.0.0.1:8000/projects/{project_id}/jobs/extract-transcripts"
```

Create a DOCX extraction job:

```powershell
curl.exe -X POST "http://127.0.0.1:8000/projects/{project_id}/jobs/extract-docx"
```

Create an OCI Speech media transcription job:

```powershell
curl.exe -X POST "http://127.0.0.1:8000/projects/{project_id}/jobs/transcribe-media"
```

Create a PPTX extraction job:

```powershell
curl.exe -X POST "http://127.0.0.1:8000/projects/{project_id}/jobs/extract-pptx"
```

Create a spreadsheet extraction job:

```powershell
curl.exe -X POST "http://127.0.0.1:8000/projects/{project_id}/jobs/extract-spreadsheets"
```

Create one job to extract all supported uploaded files:

```powershell
curl.exe -X POST "http://127.0.0.1:8000/projects/{project_id}/jobs/extract-all"
```

Create an AUD plan generation job:

```powershell
curl.exe -X POST "http://127.0.0.1:8000/projects/{project_id}/jobs/generate-aud-plan"
```

Create a normalized evidence index job:

```powershell
curl.exe -X POST "http://127.0.0.1:8000/projects/{project_id}/jobs/build-evidence-index"
```

Create AI source summaries from evidence:

```powershell
curl.exe -X POST "http://127.0.0.1:8000/projects/{project_id}/jobs/generate-source-summaries-ai"
```

Create an AI-enhanced AUD plan:

```powershell
curl.exe -X POST "http://127.0.0.1:8000/projects/{project_id}/jobs/enhance-aud-plan-ai"
```

Create deterministic section evidence packs:

```powershell
curl.exe -X POST "http://127.0.0.1:8000/projects/{project_id}/jobs/build-section-evidence-packs"
```

Create AI section drafts from section evidence packs:

```powershell
curl.exe -X POST "http://127.0.0.1:8000/projects/{project_id}/jobs/generate-section-drafts-ai"
```

Create an OCI Document Understanding enrichment job:

```powershell
curl.exe -X POST "http://127.0.0.1:8000/projects/{project_id}/jobs/enrich-document-understanding"
```

Create an open points extraction job:

```powershell
curl.exe -X POST "http://127.0.0.1:8000/projects/{project_id}/jobs/extract-open-points"
```

Create an AI Open Points refinement job:

```powershell
curl.exe -X POST "http://127.0.0.1:8000/projects/{project_id}/jobs/refine-open-points-ai"
```

Create a local editable DOCX generation job:

```powershell
curl.exe -X POST "http://127.0.0.1:8000/projects/{project_id}/jobs/generate-docx"
```

Create a DOCX generation job with AI draft rendering options:

```powershell
curl.exe -X POST "http://127.0.0.1:8000/projects/{project_id}/jobs/generate-docx" `
  -H "Content-Type: application/json" `
  -d "{\"use_ai_drafts\":true,\"include_draft_sections\":true,\"include_images\":true,\"include_open_points\":true}"
```

Create a one-click AUD generation run:

```powershell
curl.exe -X POST "http://127.0.0.1:8000/projects/{project_id}/generate-aud"
```

Expected response:

```json
{
  "job_id": "...",
  "status": "queued",
  "message": "AUD generation started"
}
```

Check one-click AUD generation status:

```powershell
curl.exe "http://127.0.0.1:8000/projects/{project_id}/generate-aud/status"
```

Expected response:

```json
{
  "job_id": "...",
  "status": "queued|running|completed|failed|completed_with_warnings",
  "current_stage": null,
  "completed_stages": [],
  "failed_stage": null,
  "warnings": [],
  "final_document_id": null,
  "final_document_url": null,
  "error": null
}
```

Jobs start as:

```json
{
  "job_type": "classify_files | extract_transcripts | transcribe_media | extract_docx | extract_pptx | extract_spreadsheets | extract_all | generate_aud_plan | build_evidence_index | generate_source_summaries_ai | enhance_aud_plan_ai | build_section_evidence_packs | generate_section_drafts_ai | enrich_with_document_understanding | extract_open_points | refine_open_points_ai | generate_docx | generate_aud",
  "status": "pending",
  "progress": 0
}
```

Run the local worker manually from the `backend/` directory:

```powershell
python -m app.workers.local_worker
```

The local worker picks pending jobs from the database and processes:

- `classify_files`: assigns uploaded file types from extensions.
- `extract_transcripts`: reads `.txt` uploads only and stores extracted transcript text.
- `transcribe_media`: submits `.mp3`, `.m4a`, and `.mp4` media to OCI Speech when `STORAGE_BACKEND=oci`, then stores the returned transcript as extracted content.
- `extract_docx`: reads `.docx` uploads and stores extracted paragraphs, heading-like paragraphs, tables, comments when present, and basic metadata.
- `extract_pptx`: reads `.pptx` uploads, stores slide text/tables/notes metadata, and writes extracted images to local project storage.
- `extract_spreadsheets`: reads `.xlsx` and `.xlsm` uploads and stores visible sheet structure, selected meaningful rows, formulas, and basic workbook metadata.
- `extract_all`: runs transcript, DOCX, PPTX, and spreadsheet extraction in one job.
- `generate_aud_plan`: creates a deterministic draft AUD plan JSON from extracted content and source-priority rules.
- `build_evidence_index`: converts extracted content into normalized, prioritized evidence items for future AUD planning and drafting.
- `generate_source_summaries_ai`: groups evidence by source file and source role, asks the configured LLM for strict JSON summaries, and stores source summaries for later AUD enhancement.
- `enhance_aud_plan_ai`: asks the configured LLM to improve section selection, naming, ordering, and source mapping while preserving deterministic source-priority authority. If the LLM returns strategy-only JSON without sections after retry, the backend carries forward deterministic plan sections and records an AI plan warning instead of failing the pipeline.
- `build_section_evidence_packs`: deterministically curates bounded evidence packets per AUD section from the latest plan, evidence index, source summaries, and source-priority rules. It does not call an LLM.
- `generate_section_drafts_ai`: asks the configured LLM for one strict JSON section draft per evidence pack, stores reviewable drafts, and inserts deduped open point candidates.
- `enrich_with_document_understanding`: optionally enriches eligible uploaded files with OCI Document Understanding OCR/table/classification output without replacing local extraction.
- `extract_open_points`: scans extracted content for unresolved questions and stores deduplicated open points.
- `refine_open_points_ai`: asks the configured LLM to clean, deduplicate, and classify existing Open Points plus candidates from source summaries, AUD plans, and section drafts, then marks duplicate existing rows as `Removed` and creates `llm_enhanced` refined `Open` rows with readable evidence text plus separate API metadata.
- `generate_docx`: creates a simple editable Word draft from project metadata, latest AUD plan, supported mapped source content, LLM-enhanced unresolved open points, and writes it through the configured storage backend.
- `generate_aud`: runs the one-click AUD pipeline as an orchestration job, creating internal stage jobs in order and tracking run status in `aud_generation_runs`.

`extract_all` progress moves across extraction stages. If some files fail and at least one file succeeds, the job ends as `completed_with_warnings`. If all attempted files fail, the job ends as `failed`.

## One-Click AUD Generation Pipeline

`POST /projects/{project_id}/generate-aud` creates a queued `generate_aud` job and
an `AUDGenerationRun` status row. The existing local worker or OCI queue worker
then runs the full backend pipeline in order:

```text
validate_project_inputs
extract_content
enrich_document_understanding
transcribe_media
generate_initial_aud_plan
build_evidence_index
generate_source_summaries_ai
enhance_aud_plan_ai
build_section_evidence_packs
generate_open_points_ai
generate_section_drafts_ai
generate_final_docx
finalize_artifact
```

The orchestrator reuses the existing job processors instead of duplicating stage
logic. It classifies uploads first, runs deterministic extraction, automatically
runs Document Understanding when PDF or image uploads are present, automatically
runs OCI Speech when media uploads are present, builds evidence and AI artifacts,
generates the DOCX, and stores the final generated document id on completion.

If a critical stage fails, the run is marked `failed`, `failed_stage` and
`error` are stored, and any partial artifacts created before the failure remain
available. If a stage finishes as `completed_with_warnings`, such as a
file-level Document Understanding failure where existing extraction is still
usable, the pipeline continues and the final run status becomes
`completed_with_warnings`.

Check job status:

```powershell
curl.exe "http://127.0.0.1:8000/projects/{project_id}/jobs"
```

### OCI Queue Mode

OCI Queue is optional. In this mode the API still saves the `Job` row locally,
then publishes a queue message containing `job_id`, `project_id`, and
`job_type`.

Required queue settings:

```powershell
$env:JOB_QUEUE_BACKEND = "oci"
$env:OCI_QUEUE_OCID = "<queue-ocid>"
$env:OCI_QUEUE_ENDPOINT = "https://cell-1.queue.messaging.<region>.oci.oraclecloud.com"
```

Use the same OCI SDK config-file authentication settings described for Object
Storage when running outside OCI:

```powershell
$env:OCI_CONFIG_FILE = "$env:USERPROFILE\.oci\config"
$env:OCI_PROFILE = "DEFAULT"
$env:OCI_REGION = "us-ashburn-1"
```

Run the OCI worker from the `backend/` directory:

```powershell
python -m app.workers.oci_queue_worker
```

The OCI worker consumes queue messages, processes the referenced job through
the existing job processors, deletes the message after successful processing,
and marks the database job as `failed` when processing raises an error.

Current simulated classification mapping:

```text
.docx       -> docx
.pptx       -> pptx
.xlsx/.xlsm -> spreadsheet
.txt        -> transcript_text
.jpg/.jpeg/.png/.tif/.tiff -> image
.mp3/.m4a/.mp4 -> media
.pdf        -> pdf
```

Current transcript extraction scope:

- Only `.txt` files are read.
- Plain text transcript extraction does not call OCI Speech.
- Files are selected when `file_type` is `transcript_text` or the original filename ends in `.txt`.

### OCI Speech Media Transcription

Media transcription is optional and does not run in local filesystem storage
mode. OCI Speech requires input media in Object Storage, so set
`STORAGE_BACKEND=oci` before running `transcribe_media`.

Required Speech settings:

```powershell
$env:STORAGE_BACKEND = "oci"
$env:OCI_SPEECH_COMPARTMENT_OCID = "<compartment-ocid>"
$env:OCI_SPEECH_OUTPUT_BUCKET = "<speech-output-bucket>"
$env:OCI_SPEECH_OUTPUT_PREFIX = "projects/{project_id}/speech/"
$env:OCI_SPEECH_MODEL_TYPE = "WHISPER_MEDIUM"
$env:OCI_SPEECH_LANGUAGE_CODE = "en"
$env:OCI_SPEECH_TIMEOUT_SECONDS = "1800"
$env:OCI_SPEECH_POLL_INTERVAL_SECONDS = "10"
```

`WHISPER_MEDIUM` is the default model for this app. The installed OCI SDK
also documents `ORACLE` and `WHISPER_LARGE_V2`; `WHISPER_LARGE_V2` is marked
as available upon service request and may improve accuracy at the cost of
latency/availability.

The same Object Storage settings are also required because uploaded media is
read from the configured input bucket:

```powershell
$env:OCI_BUCKET_NAME = "<input-upload-bucket>"
$env:OCI_NAMESPACE = "<object-storage-namespace>"
$env:OCI_REGION = "us-ashburn-1"
$env:OCI_CONFIG_FILE = "$env:USERPROFILE\.oci\config"
$env:OCI_PROFILE = "DEFAULT"
```

Run the job:

```powershell
curl.exe -X POST "http://127.0.0.1:8000/projects/{project_id}/jobs/transcribe-media"
python -m app.workers.local_worker
```

When `JOB_QUEUE_BACKEND=oci`, the same job can be processed by:

```powershell
python -m app.workers.oci_queue_worker
```

Expected results:

- The worker submits one OCI Speech job per uploaded `.mp3`, `.m4a`, or `.mp4` file.
- The job message includes submitted Speech job OCIDs while processing.
- After Speech succeeds, transcript JSON is read from the configured output bucket/prefix.
- An `ExtractedContent` row is created with `content_type=transcript`, title `<media filename> transcript`, transcript text, Speech job OCID, source media file id, output object name, and timestamps when present.
- If `STORAGE_BACKEND` is not `oci` or Speech settings are missing, the job fails with a clear message.

### OCI Document Understanding Enrichment

Document Understanding is optional enrichment. It does not replace local DOCX,
PPTX, spreadsheet, transcript, or Speech extraction. FDD remains the golden
source, and local workbook extraction remains primary for `.xlsx` and `.xlsm`.

By default the provider is disabled:

```text
DOCUMENT_AI_PROVIDER=none
```

Enable OCI Document Understanding only when uploaded files are stored in Object
Storage:

```powershell
$env:STORAGE_BACKEND = "oci"
$env:DOCUMENT_AI_PROVIDER = "oci_document_understanding"
$env:OCI_DOCUMENT_COMPARTMENT_OCID = "<compartment-ocid>"
$env:OCI_DOCUMENT_OUTPUT_BUCKET = "<document-output-bucket>"
$env:OCI_DOCUMENT_OUTPUT_PREFIX = "projects/{project_id}/document_understanding/output/"
$env:OCI_DOCUMENT_TIMEOUT_SECONDS = "900"
$env:OCI_DOCUMENT_POLL_INTERVAL_SECONDS = "10"
```

Optional region override:

```powershell
$env:OCI_DOCUMENT_REGION = "us-ashburn-1"
```

Eligibility flags:

```powershell
$env:OCI_DOCUMENT_ENABLE_PDF = "true"
$env:OCI_DOCUMENT_ENABLE_IMAGES = "true"
$env:OCI_DOCUMENT_ENABLE_DOCX = "false"
$env:OCI_DOCUMENT_ENABLE_PPTX = "false"
$env:OCI_DOCUMENT_ENABLE_XLSX = "false"
```

Run the enrichment:

```powershell
curl.exe -X POST "http://127.0.0.1:8000/projects/{project_id}/jobs/enrich-document-understanding"
python -m app.workers.local_worker
```

When `JOB_QUEUE_BACKEND=oci`, process it with:

```powershell
python -m app.workers.oci_queue_worker
```

Expected results:

- Eligible PDFs and image files are submitted to OCI Document Understanding by default.
- DOCX, PPTX, and XLSX/XLSM are skipped unless explicitly enabled.
- Existing successful DU extraction for the same uploaded file is skipped.
- DU output is stored as `ExtractedContent` with `content_type=oci_document_understanding`.
- `json_content` includes provider, processor job id, document metadata, pages, detected document types, tables, raw result object path, and source uploaded file id.
- If some files fail, the job ends as `completed_with_warnings` and existing local extraction remains usable.

## Evidence Index

The evidence index is the normalized layer between raw extraction and future
LLM-based AUD drafting. LLM stages should consume `EvidenceItem` rows rather
than raw `ExtractedContent` directly.

Build evidence after extraction and optional enrichment:

```powershell
curl.exe -X POST "http://127.0.0.1:8000/projects/{project_id}/jobs/build-evidence-index"
python -m app.workers.local_worker
```

With OCI Queue mode:

```powershell
python -m app.workers.oci_queue_worker
```

List evidence:

```powershell
curl.exe "http://127.0.0.1:8000/projects/{project_id}/evidence-items"
```

Evidence priority rules:

- FDD headings, paragraphs, tables, and open items: priority `100`.
- OCI Document Understanding from FDD sources: priority `95`.
- KT transcript/session segments: priority `80`.
- KT PPT slides and image references: priority `70`.
- Configuration workbook sheets/tables: priority `60`.
- OCI Document Understanding from supporting documents: priority `65`.
- Unknown OCI Document Understanding output: priority `50`.
- Final AUD samples: priority `30` with `style_reference=true`.

The evidence build job is idempotent. Reruns use a deterministic key based on
project id, source extracted content id, evidence type, title, and text hash to
avoid duplicates.

## AI Source Summaries

Source summaries are concise LLM-generated summaries of normalized
`EvidenceItem` rows, grouped by source file and source role. They prepare the
project for later AUD plan enhancement and section drafting, but they do not
generate or modify the AUD yet.

Build evidence first, then generate summaries:

```powershell
curl.exe -X POST "http://127.0.0.1:8000/projects/{project_id}/jobs/build-evidence-index"
python -m app.workers.local_worker

curl.exe -X POST "http://127.0.0.1:8000/projects/{project_id}/jobs/generate-source-summaries-ai"
python -m app.workers.local_worker
```

List summaries:

```powershell
curl.exe "http://127.0.0.1:8000/projects/{project_id}/source-summaries"
```

Each summary asks the LLM for strict JSON:

```json
{
  "source_role": "...",
  "summary": "...",
  "important_topics": [],
  "tables_or_configurations": [],
  "processes": [],
  "screenshots_or_images_to_consider": [],
  "open_or_unresolved_items": [],
  "source_confidence": "high|medium|low",
  "aud_usage_guidance": "..."
}
```

Prompt rules:

- Use only provided evidence.
- Do not invent missing details.
- Mark missing or unclear information explicitly.
- FDD summaries identify FDD as the golden source.
- Configuration workbook summaries describe setup facts and validation details; they should not be copied blindly as primary narrative.
- Transcript summaries focus on presenter emphasis, corrections, Q&A, deferred items, and screenshot relevance.
- PPT summaries focus on slide topics, tables, screenshots/images, and process/configuration topics.
- Final AUD sample summaries describe style and structure only.

If one source fails LLM JSON validation or provider execution, the worker
continues summarizing other sources. If at least one source succeeds, the job
ends as `completed_with_warnings`; if all source groups fail, the job is marked
`failed`.

## AI-Enhanced AUD Plan

The AI-enhanced AUD plan is a refinement layer on top of the deterministic AUD
plan. It uses the existing deterministic plan, source priority report, source
summaries, and top-priority evidence items to improve section selection, naming,
ordering, and source mapping. It does not overwrite the deterministic plan
sections.

Recommended order:

```powershell
curl.exe -X POST "http://127.0.0.1:8000/projects/{project_id}/jobs/generate-aud-plan"
python -m app.workers.local_worker

curl.exe -X POST "http://127.0.0.1:8000/projects/{project_id}/jobs/build-evidence-index"
python -m app.workers.local_worker

curl.exe -X POST "http://127.0.0.1:8000/projects/{project_id}/jobs/generate-source-summaries-ai"
python -m app.workers.local_worker

curl.exe -X POST "http://127.0.0.1:8000/projects/{project_id}/jobs/enhance-aud-plan-ai"
python -m app.workers.local_worker
```

If no deterministic plan exists, the worker creates one first. The AI response
is stored inside the latest `AUDPlan.plan_json` under:

```json
{
  "ai_enhanced_plan": {
    "document_strategy": {},
    "sections": [],
    "image_strategy": [],
    "table_strategy": [],
    "open_point_candidates": [],
    "warnings": []
  }
}
```

The prompt reinforces these rules:

- FDD remains the golden source when present.
- FDD wins over transcript, PPT, and configuration workbook conflicts.
- Explicit template controls structure; the default SCM template is used only when no explicit template is uploaded.
- Empty or unsupported sections are omitted.
- `Documents Referred` is not included for now.
- Reporting/RICEW sections are included only if mentioned or provided.
- Open Points are unresolved items only.
- Configuration workbook validates and enriches; it is not primary narrative when FDD exists.
- Final AUD samples are style/reference only unless explicitly uploaded as a template.

## Section Evidence Packs

Section evidence packs are deterministic, bounded evidence packets for future
AI section drafting. They do not call an LLM and do not generate AUD prose.

Build them after an AUD plan and evidence index exist. Source summaries and the
AI-enhanced AUD plan are optional but improve mapping quality:

```powershell
curl.exe -X POST "http://127.0.0.1:8000/projects/{project_id}/jobs/build-section-evidence-packs"
python -m app.workers.local_worker
```

With OCI Queue mode:

```powershell
python -m app.workers.oci_queue_worker
```

List packs:

```powershell
curl.exe "http://127.0.0.1:8000/projects/{project_id}/section-evidence-packs"
```

Each `SectionEvidencePack.pack_json` has this shape:

```json
{
  "section_id": "...",
  "section_title": "...",
  "source_priority_rules": [],
  "golden_source_present": true,
  "primary_evidence": [],
  "supporting_evidence": [],
  "configuration_evidence": [],
  "transcript_context": [],
  "image_candidates": [],
  "table_candidates": [],
  "open_point_candidates": [],
  "excluded_evidence": [],
  "missing_information": []
}
```

Pack rules:

- FDD evidence mapped to a section goes into `primary_evidence`.
- If FDD evidence exists for the section, lower-priority evidence is retained as supporting/configuration/context/image/table evidence rather than promoted over FDD.
- Configuration workbook evidence goes into `configuration_evidence`, unless no FDD, PPT, or transcript evidence matches that section; in that case it may become `primary_evidence` with a traceable reason.
- KT transcript/session evidence goes into `transcript_context`.
- PPT slide/image evidence goes into `image_candidates`, `table_candidates`, or `supporting_evidence` depending on evidence type.
- Evidence item IDs are preserved for traceability.
- Rerunning the job replaces prior packs for the project.
- Pack size is bounded by `SECTION_EVIDENCE_MAX_CHARS`, default `30000`.

## AI Section Drafts

AI section drafts use `SectionEvidencePack` rows as their only source material.
This stage prepares reviewable section prose but does not yet feed the final
DOCX generator.

Generate drafts:

```powershell
curl.exe -X POST "http://127.0.0.1:8000/projects/{project_id}/jobs/generate-section-drafts-ai"
python -m app.workers.local_worker
```

With OCI Queue mode:

```powershell
python -m app.workers.oci_queue_worker
```

List drafts:

```powershell
curl.exe "http://127.0.0.1:8000/projects/{project_id}/section-drafts"
```

The worker ensures section evidence packs exist first. For each pack, it asks
the configured LLM for strict JSON:

```json
{
  "section_id": "...",
  "title": "...",
  "draft_text": "...",
  "confidence": "high|medium|low",
  "used_evidence_item_ids": [],
  "included_tables": [],
  "included_images": [],
  "unsupported_details": [],
  "open_point_candidates": [],
  "placeholders": []
}
```

Drafting rules:

- Use only evidence in the evidence pack.
- FDD remains the golden source.
- Do not invent customer, process, or configuration details.
- Do not include generic Oracle SCM facts unless supported by inputs.
- If information is unclear, use placeholders or propose open points.
- If no supported evidence exists, the stored draft is forced to a placeholder with low confidence.
- `draft_text` should be Word-document-ready prose without inline citations.
- Evidence traceability is stored in `used_evidence_item_ids`.
- Open point candidates are inserted into `OpenPoint` with simple question-level dedupe.
- If one section fails LLM JSON validation or provider execution, the worker continues with other sections and marks the job `completed_with_warnings` when at least one draft succeeds.

Current DOCX extraction scope:

- Files are selected when `file_type` is `docx` or the original filename ends in `.docx`.
- Paragraph and table text is extracted with `python-docx`.
- Heading-like paragraphs are detected from paragraph style names such as `Heading 1`.
- DOCX package comments are extracted from `word/comments.xml` when that part exists.
- Extracted FDD files include `is_golden_source = true` in `json_content`.
- This phase does not generate an AUD and does not call an LLM.

Current PPTX extraction scope:

- Files are selected when `file_type` is `pptx` or the original filename ends in `.pptx`.
- Slide titles, text-frame text, table rows, notes text when accessible, and image counts are extracted with `python-pptx`.
- Images are written through the configured storage backend using keys under:

```text
projects/{project_id}/extracted_images/{uploaded_file_id}/
```

- No OCR is performed.
- This phase does not generate an AUD and does not call an LLM.

Current spreadsheet extraction scope:

- Files are selected when `file_type` is `spreadsheet` or the original filename ends in `.xlsx` or `.xlsm`.
- Workbook metadata includes sheet count and sheet names.
- Only visible sheets are extracted.
- Used ranges are extracted rather than huge blank areas.
- Formulas are preserved as formula strings such as `=B3*2`; formulas are not evaluated.
- Extracted rows are capped by `MAX_SPREADSHEET_ROWS_PER_SHEET`, default `200`.
- Likely configuration sheets are detected from sheet names and non-empty content.
- This phase does not generate an AUD and does not call an LLM.

Check extracted content:

```powershell
curl.exe "http://127.0.0.1:8000/projects/{project_id}/extracted-content"
```

Extracted transcript records include:

```text
content_type = transcript
title = original filename
text_content = full text
json_content = character_count and word_count
```

Extracted DOCX records include:

```text
content_type = docx
title = original filename
text_content = extracted headings, paragraphs, and table rows
json_content = headings, tables, comments, metadata, source_role, and optional is_golden_source
```

Extracted PPTX records include:

```text
content_type = pptx
title = original filename
text_content = readable slide-by-slide text
json_content = slide_count, slides, slide-level image_paths, presentation-level image_paths, table_count, total_image_count, and source_role
```

PPTX extraction reads the PowerPoint title placeholder when available. If a deck
uses regular text boxes for visible slide titles, extraction infers the title
from top-of-slide text and filters common footer/page-number noise from slide
body text. PPTX records with `unknown` source role are treated as KT PPT input
for deterministic AUD planning and DOCX rendering in this local v1 flow.

Extracted spreadsheet records include:

```text
content_type = spreadsheet
title = original filename
text_content = readable workbook and sheet summaries with selected rows
json_content = workbook metadata, visible sheets, extracted rows, and source_role
```

Current DOCX generation scope:

- Uses `TemplateResolver` before rendering. Uploaded files with
  `source_role=aud_template` or legacy `template_aud` are selected first; when
  no explicit template upload exists, the configured
  `DEFAULT_AUD_TEMPLATE_PATH` is used.
- `DEFAULT_AUD_TEMPLATE_PATH` defaults to
  `/backend/template/AUD_Editable_Template.docx`. The path is resolved safely for
  local checkout paths and container paths.
- The template cover page and styles are preserved, then stale sample body
  placeholders are removed before rendering a fresh TOC and generated AUD
  content.
- `TemplatePopulationService` builds a clean intermediate document model from
  the selected template path, project metadata, final AI-enhanced AUD plan,
  section drafts, selected tables/images, and LLM-enhanced Open Points before
  DOCX writing.
- Generation fails before DOCX rendering with a clear error if neither an
  uploaded template nor the default template file exists.
- Logs either `Using uploaded AUD template: <file>` or
  `Using default AUD template: /backend/template/AUD_Editable_Template.docx`
  when selecting the template.
- Uses the final AI-enhanced AUD plan when present, otherwise the latest
  deterministic AUD plan and mapped extracted content.
- When `use_ai_drafts=true`, accepted/reviewed/approved section drafts are preferred over rule-based content.
- Section drafts with `review_status=draft` are used only when `include_draft_sections=true`.
- Section drafts with `review_status=omitted`, `excluded`, or `removed` exclude that section.
- If an AI draft is unavailable or gated off, DOCX generation falls back to rule-based source content.
- Selected draft tables from `draft_json.included_tables` are inserted when resolvable from direct rows or evidence item IDs.
- Structured tables are rendered through `DOCXTableRenderer`, which normalizes
  markdown tables, pipe-delimited tables, selected draft/evidence tables,
  extracted DOCX/PPTX table rows, spreadsheet-style rows, and Open Points into
  real Word tables with visible borders, bold/repeating headers where possible,
  aligned cells, and practical column widths. Multi-line cells and intentionally
  blank leading cells are preserved for process assignment/orchestration tables.
  Ambiguous or malformed table text falls back to paragraph rendering only with
  a logged reason.
- Selected draft images from `draft_json.included_images` are deduplicated and
  inserted when `include_images=true`; otherwise image insertion is skipped.
- Image candidates from draft selections, DOCX extraction, PPT extraction,
  Document Understanding style references, rendered pages, or manual uploads
  pass through `ImageDeduplicationService` before DOCX rendering. Exact content
  hash matches, same source/page/bounding-box references, close perceptual
  hashes when Pillow/imagehash support is available, and safe caption/dimension
  metadata matches are treated as duplicates. Template placeholder images such
  as `<Insert diagram / screenshot here>` are excluded, and generated document
  `metadata_json.image_deduplication` records candidate counts, retained image
  IDs, removed duplicate IDs, and removal reasons.
- Open Points are included only when `include_open_points=true`. By default, only rows with `source_type=llm_enhanced` and status `Open` are rendered.
- If the latest AUD plan is missing, contains only standard sections, or predates extracted FDD content, DOCX generation refreshes the deterministic AUD plan before rendering.
- Enterprise Structure is a carry-forward section when detected in FDD, PPT, or other extracted source content, and is inserted with source text, tables, and supported associated images. If not detected, it is omitted instead of inventing BU/LE content.
- Does not call an LLM.
- Gives mapped FDD content priority over PPT content.
- For projects with both FDD and PPT, AUD planning keeps FDD headings first and adds non-duplicate PPT sections as supporting material; FDD remains the golden source when titles overlap.
- For PPT-only projects, AUD planning uses meaningful slide titles and skips low-value title/session/agenda slides.
- For planned sections based on FDD headings, includes text under the matching heading until the next heading.
- For planned sections based on PPT slide titles, includes text, table rows, and notes from the matching slide.
- Inserts local PPT images when the slide title matches or strongly resembles a planned section title, or when a mapped PPT slide has images and meaningful text.
- Excludes obvious low-value PPT slides such as Welcome, Thank You, Agenda, and blank divider slides.
- Resizes inserted PPT images to the usable DOCX page width and adds captions such as `Source image from slide X: <slide title>`.
- Includes up to 3 PPT images per section for now.
- Skips PPT images in formats `python-docx` cannot embed directly, such as WMF vector images.
- Section source content is carried through as refined readable paragraphs
  instead of being replaced with generic source-detail or summary notes.
- If no supported mapped content is available, the unsupported section is omitted
  instead of rendering raw template placeholder text.
- Open Points includes only rows with `source_type=llm_enhanced` and status `Open`.
  Raw extracted Open Points remain refinement candidates and are not inserted
  directly into the final AUD.
- Documents Referred is excluded.
- Source Conflict Summary is appended only when `INTERNAL_DEBUG_OUTPUT=true`.
- Unsupported source mappings are omitted rather than inferred.
- PPT image placement uses only local extracted image paths; no OCR or image understanding is performed.

## Manual DOCX Extraction Test

Start the API and upload an FDD DOCX:

```powershell
curl.exe -X POST "http://127.0.0.1:8000/projects" `
  -H "Content-Type: application/json" `
  -d "{\"customer_name\":\"Vision Operations\",\"module_name\":\"Order Management\"}"
```

Copy the returned `id`, then run:

```powershell
curl.exe -X POST "http://127.0.0.1:8000/projects/{project_id}/files" `
  -F "source_role=fdd" `
  -F "file=@C:\path\to\fdd.docx"

curl.exe -X POST "http://127.0.0.1:8000/projects/{project_id}/jobs/extract-docx"

python -m app.workers.local_worker

curl.exe "http://127.0.0.1:8000/projects/{project_id}/extracted-content"
```

Confirm the extracted DOCX row has `content_type` set to `docx`, includes heading/table metadata, and has `is_golden_source` set to `true` for an FDD upload.

## Manual PPTX Extraction Test

Start the API and upload a KT presentation:

```powershell
curl.exe -X POST "http://127.0.0.1:8000/projects" `
  -H "Content-Type: application/json" `
  -d "{\"customer_name\":\"Vision Operations\",\"module_name\":\"Order Management\"}"
```

Copy the returned `id`, then run:

```powershell
curl.exe -X POST "http://127.0.0.1:8000/projects/{project_id}/files" `
  -F "source_role=kt_ppt" `
  -F "file=@C:\path\to\presentation.pptx"

curl.exe -X POST "http://127.0.0.1:8000/projects/{project_id}/jobs/extract-pptx"

python -m app.workers.local_worker

curl.exe "http://127.0.0.1:8000/projects/{project_id}/extracted-content"
```

Expected results:

- The extracted row has `content_type` set to `pptx`.
- `text_content` shows readable slide-by-slide content.
- `json_content.slide_count` matches the number of slides.
- `json_content.slides` includes slide numbers, titles, text, tables, notes when available, and per-slide image counts.
- `json_content.image_paths` lists extracted image storage paths.
- With local storage, extracted image files exist under `backend/storage/projects/{project_id}/extracted_images/{uploaded_file_id}/`. With OCI storage, the same keys exist in the configured bucket.

## Manual Spreadsheet Extraction Test

Start the API and upload a configuration workbook:

```powershell
curl.exe -X POST "http://127.0.0.1:8000/projects" `
  -H "Content-Type: application/json" `
  -d "{\"customer_name\":\"Vision Operations\",\"module_name\":\"Order Management\"}"
```

Copy the returned `id`, then run:

```powershell
curl.exe -X POST "http://127.0.0.1:8000/projects/{project_id}/files" `
  -F "source_role=config_workbook" `
  -F "file=@C:\path\to\configuration.xlsx"

curl.exe -X POST "http://127.0.0.1:8000/projects/{project_id}/jobs/extract-spreadsheets"

python -m app.workers.local_worker

curl.exe "http://127.0.0.1:8000/projects/{project_id}/extracted-content"
```

Expected results:

- The extracted row has `content_type` set to `spreadsheet`.
- `text_content` shows readable sheet summaries and selected rows.
- `json_content.workbook.sheet_count` and `json_content.workbook.sheet_names` describe the workbook.
- `json_content.sheets` includes visible sheets only.
- Formulas appear as formula strings and are not evaluated.
- Extracted rows stop at the configured `MAX_SPREADSHEET_ROWS_PER_SHEET` cap.

## Manual Extract All Test

Upload any mix of supported extraction files, then run:

```powershell
curl.exe -X POST "http://127.0.0.1:8000/projects/{project_id}/jobs/extract-all"

python -m app.workers.local_worker

curl.exe "http://127.0.0.1:8000/projects/{project_id}/jobs"

curl.exe "http://127.0.0.1:8000/projects/{project_id}/extracted-content"
```

Expected results:

- The `extract_all` job reaches `100` progress.
- If all files extract successfully, status is `completed`.
- If at least one file extracts and another fails, status is `completed_with_warnings` and the message lists failed filenames.
- If every attempted file fails, status is `failed`.
- Extracted content rows are created for each successful supported file.

## Manual Source Priority Report Test

Upload project files with source roles such as `fdd`, `kt_ppt`, `kt_transcript`,
`config_workbook`, and optionally `aud_template` or legacy `template_aud`, then run:

```powershell
curl.exe "http://127.0.0.1:8000/projects/{project_id}/source-priority-report"
```

Expected results:

- `has_explicit_template` is `true` when an `aud_template` or legacy `template_aud` file is uploaded.
- `recommended_default_template_needed` is `true` when no explicit template AUD is uploaded.
- FDD uploads appear in `golden_source_files`.
- `priority_order` lists the template decision first, then FDD when present, then supporting source roles.
- `notes` explain that configuration workbooks validate/enrich only and that KT transcript overrides documents only for explicit presenter corrections.
- No AUD is generated by this endpoint.

## Manual AUD Plan Test

Run extraction first so the project has DOCX, PPTX, or transcript extracted content,
then run:

```powershell
curl.exe -X POST "http://127.0.0.1:8000/projects/{project_id}/jobs/generate-aud-plan"

python -m app.workers.local_worker

curl.exe "http://127.0.0.1:8000/projects/{project_id}/aud-plan"
```

Expected results:

- The `generate_aud_plan` job reaches `completed` with `100` progress.
- `GET /aud-plan` returns the latest draft plan row.
- `plan_json.default_template_required` is `true` when no explicit template AUD is uploaded.
- If FDD extracted headings exist, plan sections start from those headings.
- If FDD and PPT extracted content both exist, non-duplicate PPT slide-title sections are added after FDD headings while overlapping topics remain FDD-led.
- If no FDD exists but PPT extracted content exists, plan sections use meaningful slide titles and omit low-value slides such as Welcome, Agenda, and Thank You.
- If only transcript content exists, plan sections use the generic default set.
- `plan_json.sections` includes Cover Page, Document Version History, Table of Contents, and Open Points.
- No DOCX is generated by this phase.

## Manual Open Points Test

Run extraction first so the project has DOCX, PPTX, transcript, or spreadsheet
extracted content, then run:

```powershell
curl.exe -X POST "http://127.0.0.1:8000/projects/{project_id}/jobs/extract-open-points"

python -m app.workers.local_worker

curl.exe "http://127.0.0.1:8000/projects/{project_id}/open-points"
```

Expected results:

- The `extract_open_points` job reaches `completed` with `100` progress.
- Only unresolved questions/items are returned.
- Items marked `Closed`, `Resolved`, `Aligned`, or `Done` are excluded.
- FDD comments or rows containing indicators like `needs more discussion`, `to be confirmed`, `TBD`, `pending`, or `awaiting confirmation` create Open Points.
- Transcript statements that another session is needed or confirmation is required create Open Points.
- If FDD is clear, non-FDD conflicts do not create Open Points.
- If FDD is absent, non-FDD conflicts can create Open Points.

## Manual AI Open Points Refinement Test

Run Open Points extraction and any AI summary/plan/draft jobs that should
contribute candidates, configure an LLM provider, then run:

```powershell
curl.exe -X POST "http://127.0.0.1:8000/projects/{project_id}/jobs/refine-open-points-ai"

python -m app.workers.local_worker

curl.exe "http://127.0.0.1:8000/projects/{project_id}/open-points"
```

Expected results:

- The `refine_open_points_ai` job reaches `completed` with `100` progress.
- Refined Open Points have status `Open`.
- Existing duplicate Open Points are retained but marked `Removed`.
- Closed, Resolved, Aligned, and Done items are excluded.
- Lower-priority conflicts answered by FDD are excluded.
- FDD items that say `needs more discussion`, `to be confirmed`, `TBD`, `pending`, or `awaiting confirmation` remain Open Points.
- Refined rows return readable evidence text in `evidence`; source Open Point IDs, evidence item IDs, exclusions, and refinement counts are exposed in `refinement_metadata`.

## Manual DOCX Generation Test

Run extraction, AUD plan generation, and open point extraction first when source material is available, then run:

```powershell
curl.exe -X POST "http://127.0.0.1:8000/projects/{project_id}/jobs/generate-docx"

python -m app.workers.local_worker

curl.exe "http://127.0.0.1:8000/projects/{project_id}/generated-documents"
```

Copy the returned generated document `id`, then download:

```powershell
curl.exe -L "http://127.0.0.1:8000/projects/{project_id}/generated-documents/{document_id}/download" `
  -o ".\aud-draft.docx"
```

Expected results:

- The `generate_docx` job reaches `completed` with `100` progress.
- A generated document row is returned with `document_type` set to `aud_docx`.
- With local storage, the `.docx` file exists under `backend/storage/projects/{project_id}/outputs/`. With OCI storage, the same key exists in the configured bucket.
- The document contains the template title page, generated TOC, version history
  table, Purpose and Scope, planned section headings, supported rule-based or
  reviewed draft content, unresolved LLM-enhanced open points table, and internal
  review note.
- When no explicit AUD template is uploaded, the title page starts from
  `backend/template/AUD_Editable_Template.docx`; cover metadata placeholders for
  customer, module, author, version, and date are filled from project metadata.
- Unused template placeholders and repeated sample process sections are removed
  from the final AUD.
- Unsupported sections such as Documents Referred, Roles and Functions, Legend,
  Glossary, and Reporting/RICEW are omitted unless the final plan/source content
  provides supported evidence for them.
- Matching PPT images appear below relevant planned sections with source slide captions when extracted image files exist locally.
- If an earlier AUD plan was generated before extraction or before FDD content was available, the DOCX job refreshes the plan so extracted FDD/PPT sections can appear and FDD can win.
- No LLM call, OCR, image interpretation, or template-perfect formatting is used during DOCX generation.

## OCI Generative AI LLM Wrapper

The backend has an optional LLM service wrapper for later AUD planning,
summaries, conflict detection, and section drafting. AUD generation does not use
this wrapper yet.

Default local and test behavior:

```text
LLM_PROVIDER=none
```

Supported provider values:

```text
none
oci_responses
oci_genai_classic
```

For the OCI Python SDK chat flow you can call the model directly with
`LLM_PROVIDER=oci_genai_classic`. That mode does not require
`OCI_GENAI_PROJECT_OCID` or `OCI_GENAI_API_KEY`; it uses your OCI config file
and the compartment/model values, matching the standalone SDK sample.

Shared safeguards:

```text
OCI_GENAI_MODEL_ID=<model-ocid-or-provider-model-id>
OCI_GENAI_MAX_INPUT_CHARS=200000
OCI_GENAI_TIMEOUT_SECONDS=120
OCI_GENAI_TEMPERATURE=1
OCI_GENAI_MAX_OUTPUT_TOKENS=16000
OCI_GENAI_RETRY_MAX_ATTEMPTS=4
OCI_GENAI_RETRY_BASE_SECONDS=2
OCI_GENAI_RETRY_MAX_SECONDS=20
REQUIRE_LLM_ENHANCED_OPEN_POINTS=true
ALLOW_RAW_OPEN_POINTS_FALLBACK=true
```

The wrapper validates prompt length before calling a provider and does not log
full prompts or source content by default. Prompt builders reserve room for
system/JSON instructions before applying `OCI_GENAI_MAX_INPUT_CHARS`, so bounded
AI jobs do not fail just because wrapper text was added after trimming. JSON
calls strip simple markdown JSON fences, parse strictly, and fail with a
controlled error if the model returns invalid JSON.

OCI 429 throttling is treated as transient by both OCI LLM providers. The
wrapper retries with exponential backoff using `OCI_GENAI_RETRY_MAX_ATTEMPTS`,
`OCI_GENAI_RETRY_BASE_SECONDS`, and `OCI_GENAI_RETRY_MAX_SECONDS`. For Gemini
Flash models with many AUD sections, increase the base/max retry seconds if
section drafting still reports throttling warnings near the end of a run.

Some OCI Generative AI models, including newer GPT-style models, only accept the
default temperature value. Keep `OCI_GENAI_TEMPERATURE=1` for those models. The
classic SDK wrapper retries once with the default temperature if OCI rejects a
custom temperature value.

AI-enhanced AUD plan output is larger than source-summary output because it
returns section mapping JSON. If OCI returns `finish_reason=length`, increase
`OCI_GENAI_MAX_OUTPUT_TOKENS` or reduce the project evidence included in the AI
plan job.

### OCI Responses API Mode

Use this mode when your tenancy exposes the OpenAI-compatible OCI Responses API:

```powershell
$env:ENVIRONMENT = "development"
$env:LLM_PROVIDER = "oci_responses"
$env:OCI_GENAI_REGION = "us-chicago-1"
$env:OCI_GENAI_MODEL_ID = "<model-id>"
$env:OCI_GENAI_PROJECT_OCID = "<optional-genai-project-ocid>"
$env:OCI_GENAI_API_KEY = "<optional-dev-api-key-if-your-responses-setup-needs-it>"
uvicorn app.main:app --reload
```

The service uses:

```text
https://inference.generativeai.{region}.oci.oraclecloud.com/openai/v1
```

### OCI Generative AI Classic SDK Mode

Use this mode for the OCI Python SDK `GenerativeAiInferenceClient` flow:

```powershell
$env:ENVIRONMENT = "development"
$env:LLM_PROVIDER = "oci_genai_classic"
$env:OCI_GENAI_REGION = "us-chicago-1"
$env:OCI_GENAI_COMPARTMENT_OCID = "<compartment-ocid>"
$env:OCI_GENAI_MODEL_ID = "<model-ocid>"
$env:OCI_CONFIG_FILE = "$env:USERPROFILE\.oci\config"
$env:OCI_PROFILE = "DEFAULT"
uvicorn app.main:app --reload
```

This is the mode that matches the direct `GenerativeAiInferenceClient.chat`
sample. Required values are region, compartment OCID, model ID, and OCI config
authentication. `OCI_GENAI_PROJECT_OCID` and `OCI_GENAI_API_KEY` can be left
blank.

### Development LLM Test Endpoint

This endpoint is intentionally available only when:

```text
ENVIRONMENT=development
```

Test with a JSON-only prompt:

```powershell
curl.exe -X POST "http://127.0.0.1:8000/dev/llm-test" `
  -H "Content-Type: application/json" `
  -d "{\"prompt\":\"Reply with JSON only: {\\\"status\\\":\\\"ok\\\"}\"}"
```

Outside development, the endpoint returns `404`.

## Run Tests

From the `backend/` directory:

```powershell
python -m pytest
```

If your terminal is opened at the repository root, either run `cd backend` first or use:

```powershell
.\backend\.venv\Scripts\python.exe -m pytest
```
