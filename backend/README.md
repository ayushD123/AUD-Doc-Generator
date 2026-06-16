# Backend

FastAPI backend skeleton for the Oracle AUD Generator.

This phase includes a minimal application structure, local settings, a health endpoint, a SQLite-backed SQLAlchemy database foundation, project/job APIs, local file upload metadata, transcript extraction, DOCX extraction, PPTX extraction, spreadsheet extraction, and pytest coverage. It does not include OCI integration, authentication, LLM calls, AUD generation, or Alembic migrations.

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

## Local File Storage

Uploaded files are stored on the local filesystem for development:

```text
backend/storage/projects/{project_id}/uploads/
```

The database stores a relative storage key such as:

```text
projects/{project_id}/uploads/{generated_filename}.pdf
```

This keeps local storage behind a service class so it can later be replaced with OCI Object Storage without changing route behavior.

Default storage root:

```text
storage
```

To override it:

```powershell
$env:LOCAL_STORAGE_ROOT = "storage"
uvicorn app.main:app --reload
```

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
POST /projects/{project_id}/jobs
GET  /projects/{project_id}/jobs
GET  /projects/{project_id}/extracted-content
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

Jobs start as:

```json
{
  "job_type": "classify_files | extract_transcripts | extract_docx | extract_pptx | extract_spreadsheets | extract_all",
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
- Images are copied to:

```text
backend/storage/projects/{project_id}/extracted_images/{uploaded_file_id}/
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
json_content = slide_count, slides, image_paths, table_count, total_image_count, and source_role
```

Extracted spreadsheet records include:

```text
content_type = spreadsheet
title = original filename
text_content = readable workbook and sheet summaries with selected rows
json_content = workbook metadata, visible sheets, extracted rows, and source_role
```

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
- Extracted image files exist under `backend/storage/projects/{project_id}/extracted_images/{uploaded_file_id}/`.

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

## Run Tests

From the `backend/` directory:

```powershell
python -m pytest
```

If your terminal is opened at the repository root, either run `cd backend` first or use:

```powershell
.\backend\.venv\Scripts\python.exe -m pytest
```
