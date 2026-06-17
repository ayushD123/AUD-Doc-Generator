# Backend

FastAPI backend skeleton for the Oracle AUD Generator.

This phase includes a minimal application structure, local settings, a health endpoint, a SQLite-backed SQLAlchemy database foundation, project/job APIs, local file upload metadata, local filesystem storage by default, an optional OCI Object Storage adapter, transcript extraction, DOCX extraction, PPTX extraction, spreadsheet extraction, deterministic AUD planning, open point extraction, rule-based DOCX draft generation, and pytest coverage. It does not include OCI Queue, speech transcription, authentication, LLM calls, template-perfect AUD generation, or Alembic migrations.

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
POST /projects/{project_id}/jobs/extract-pptx
POST /projects/{project_id}/jobs/extract-spreadsheets
POST /projects/{project_id}/jobs/extract-all
POST /projects/{project_id}/jobs/generate-aud-plan
POST /projects/{project_id}/jobs/extract-open-points
POST /projects/{project_id}/jobs/generate-docx
POST /projects/{project_id}/jobs
GET  /projects/{project_id}/jobs
GET  /projects/{project_id}/extracted-content
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
.docx, .pptx, .xlsx, .xlsm, .txt, .pdf, .m4a, .mp4
```

Allowed `source_role` values:

```text
template_aud, final_aud_sample, fdd, kt_ppt, kt_session, kt_transcript, config_workbook, supporting_doc, unknown
```

## Local Async Jobs

Jobs are stored in the local database. No Redis, Celery, or OCI Queue is used yet.

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

Create an open points extraction job:

```powershell
curl.exe -X POST "http://127.0.0.1:8000/projects/{project_id}/jobs/extract-open-points"
```

Create a local editable DOCX generation job:

```powershell
curl.exe -X POST "http://127.0.0.1:8000/projects/{project_id}/jobs/generate-docx"
```

Jobs start as:

```json
{
  "job_type": "classify_files | extract_transcripts | extract_docx | extract_pptx | extract_spreadsheets | extract_all | generate_aud_plan | extract_open_points | generate_docx",
  "status": "pending",
  "progress": 0
}
```

Run the local worker manually from the `backend/` directory:

```powershell
python -m app.workers.local_worker
```

The worker picks pending local jobs and simulates processing:

- `classify_files`: assigns uploaded file types from extensions.
- `extract_transcripts`: reads `.txt` uploads only and stores extracted transcript text.
- `extract_docx`: reads `.docx` uploads and stores extracted paragraphs, heading-like paragraphs, tables, comments when present, and basic metadata.
- `extract_pptx`: reads `.pptx` uploads, stores slide text/tables/notes metadata, and writes extracted images to local project storage.
- `extract_spreadsheets`: reads `.xlsx` and `.xlsm` uploads and stores visible sheet structure, selected meaningful rows, formulas, and basic workbook metadata.
- `extract_all`: runs transcript, DOCX, PPTX, and spreadsheet extraction in one job.
- `generate_aud_plan`: creates a deterministic draft AUD plan JSON from extracted content and source-priority rules.
- `extract_open_points`: scans extracted content for unresolved questions and stores deduplicated open points.
- `generate_docx`: creates a simple editable Word draft from project metadata, latest AUD plan, supported mapped source content, unresolved open points, and writes it through the configured storage backend.

`extract_all` progress moves across extraction stages. If some files fail and at least one file succeeds, the job ends as `completed_with_warnings`. If all attempted files fail, the job ends as `failed`.

Check job status:

```powershell
curl.exe "http://127.0.0.1:8000/projects/{project_id}/jobs"
```

Current simulated classification mapping:

```text
.docx       -> docx
.pptx       -> pptx
.xlsx/.xlsm -> spreadsheet
.txt        -> transcript_text
.m4a/.mp4   -> media
.pdf        -> pdf
```

Current transcript extraction scope:

- Only `.txt` files are read.
- PDF, media transcription, LLM calls, and AUD generation are not included yet.
- Files are selected when `file_type` is `transcript_text` or the original filename ends in `.txt`.

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

- Uses the latest AUD plan and mapped extracted content only.
- If the latest AUD plan is missing, contains only standard sections, or predates extracted FDD content, DOCX generation refreshes the deterministic AUD plan before rendering.
- Enterprise Structure is a required carry-forward section. If detected in FDD, PPT, or other extracted source content, it is inserted after Introduction with source text, tables, and supported associated images. If not detected, a clear placeholder is inserted after Introduction.
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
- If section content is too long, includes the first meaningful paragraphs and adds `Additional details available in source document.`
- If no supported mapped content is available, writes `<Content not available in provided source material>`.
- Open Points includes unresolved items only.
- Unsupported source mappings are left as placeholders rather than inferred.
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
`config_workbook`, and optionally `template_aud`, then run:

```powershell
curl.exe "http://127.0.0.1:8000/projects/{project_id}/source-priority-report"
```

Expected results:

- `has_explicit_template` is `true` only when a `template_aud` file is uploaded.
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
- The document contains a title page, version history table, Purpose and Scope placeholder, planned section headings, supported rule-based section content or clear placeholders, unresolved open points table, and internal review note.
- Matching PPT images appear below relevant planned sections with source slide captions when extracted image files exist locally.
- If an earlier AUD plan was generated before extraction or before FDD content was available, the DOCX job refreshes the plan so extracted FDD/PPT sections can appear and FDD can win.
- No LLM call, OCI Queue, OCR, image interpretation, or template-perfect formatting is used.

## Run Tests

From the `backend/` directory:

```powershell
python -m pytest
```

If your terminal is opened at the repository root, either run `cd backend` first or use:

```powershell
.\backend\.venv\Scripts\python.exe -m pytest
```
