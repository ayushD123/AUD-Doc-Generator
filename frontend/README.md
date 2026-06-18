# Frontend

Next.js TypeScript frontend skeleton for the Oracle AUD Generator.

This phase includes a minimal App Router setup, project creation, project listing, project detail workspace, collapsible project detail sections, local file upload UI, job controls, extracted content review, read-only evidence index review, read-only source summary review, and generated document download controls that call the backend using `NEXT_PUBLIC_API_BASE_URL`. It does not include authentication, document parsing in the frontend, complex styling, or editing generated AUD content in the browser.

## Prerequisites

- Node.js 20 LTS or newer
- npm

## Configure Environment

Copy the example file:

```powershell
Copy-Item .env.example .env.local
```

Default backend URL:

```text
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
```

Restart `npm run dev` after creating or changing `.env.local`; Next.js reads public environment variables when the dev server starts.

## Install Dependencies

From the `frontend/` directory:

```powershell
npm install
```

## Run the Frontend

```powershell
npm run dev
```

The frontend will be available at:

```text
http://localhost:3000
```

## Manual Test

Start the backend first:

```powershell
cd ..\backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload
```

Then start the frontend:

```powershell
cd ..\frontend
npm run dev
```

Open:

```text
http://localhost:3000
```

Manual checks:

- Create a project with Customer Name, Module Name, Author Name, and Email Id.
- Confirm the project appears in the project list.
- Click the project row.
- Confirm `/projects/{projectId}` opens and shows project metadata.
- Confirm project detail sections are collapsed by default.
- Click Expand and Collapse on each section and confirm only that section changes state.
- In Uploaded Files, select a source role such as KT Session (MP4) and choose an allowed file type.
- Click Upload File.
- Confirm the uploaded file list refreshes and shows filename, source role, file type, and created date.
- In Jobs, click Extract All Files.
- Confirm the jobs list refreshes with a pending `extract_all` job.
- In Jobs, click Generate AUD Plan.
- Confirm the jobs list refreshes with a pending `generate_aud_plan` job.
- In Jobs, click Extract Open Points.
- Confirm the jobs list refreshes with a pending `extract_open_points` job.
- In Jobs, click Classify Files.
- Confirm the jobs list refreshes with a pending `classify_files` job.
- In Evidence Index, click Build Evidence Index.
- Confirm the jobs list refreshes with a pending `build_evidence_index` job.
- In Source Summaries, click Generate AI Source Summaries.
- Confirm the jobs list refreshes with a pending `generate_source_summaries_ai` job.
- In Generated Documents, click Generate DOCX.
- Confirm the jobs list refreshes with a pending `generate_docx` job.
- In a backend terminal, run `python -m app.workers.local_worker`.
- Click Refresh Jobs and confirm the job status/progress updates.
- Expected result for Extract All Files: the job reaches `completed` at `100%`, or `completed_with_warnings` if some files extracted and some failed.
- Confirm the AUD Plan card appears on the project detail page.
- Click Refresh AUD Plan.
- Expected result before plan generation: the card shows `No AUD plan generated yet.`
- After backend AUD plan generation has run, expected result: the card shows whether the default template is required and lists planned sections in order with title, confidence, include flag, source role basis, and notes.
- Confirm the Open Points card appears on the project detail page.
- Click Refresh Open Points.
- Expected result before extraction: the card shows `No open points extracted yet.`
- After backend Open Points extraction has run, expected result: the card shows a read-only table with index, topic, question, status, and evidence preview.
- Confirm the Source Priority card appears on the project detail page.
- Click Refresh Source Priority.
- Expected result: the card shows explicit template status, FDD golden source status, source roles present, priority order, warnings, and whether the default SCM template will be needed later.
- Confirm the Evidence Index card appears on the project detail page.
- Click Refresh Evidence.
- Expected result before building the index: the card shows `No evidence items built yet.`
- After backend evidence indexing has run, expected result: the card shows grouped counts by evidence type and source role, plus top evidence items with title, type, source role, priority, confidence, and a short text preview.
- Confirm the Source Summaries card appears on the project detail page.
- Click Refresh Source Summaries.
- Expected result before summary generation: the card shows `No source summaries generated yet.`
- After backend source summary generation has run, expected result: summaries are grouped by source role and show source role, summary type, confidence, important topics, usage guidance, and open/unresolved items.
- Confirm the Extracted Content card appears on the project detail page.
- Click Refresh Extracted Content.
- Expected result before extraction: the card shows `No extracted content yet.`
- After backend DOCX or transcript extraction has run, expected result: the card lists extracted records with title, content type, created date, source role when present, golden source status, and available counts.
- Open Preview on an extracted record.
- Expected result: extracted text appears only inside the collapsed Preview area and stays within a scrollable max-height region.
- Confirm the Generated Documents card appears on the project detail page.
- Click Refresh Documents.
- Expected result before DOCX generation: the card shows `No generated documents yet.`
- After backend DOCX generation has run, expected result: the card lists each generated document filename, created date, and a Download DOCX link.
- Click Download DOCX.
- Expected result: the browser downloads the file from the backend generated document download endpoint.

The frontend calls:

```text
POST {NEXT_PUBLIC_API_BASE_URL}/projects
GET  {NEXT_PUBLIC_API_BASE_URL}/projects
GET  {NEXT_PUBLIC_API_BASE_URL}/projects/{projectId}
POST {NEXT_PUBLIC_API_BASE_URL}/projects/{projectId}/files
GET  {NEXT_PUBLIC_API_BASE_URL}/projects/{projectId}/files
POST {NEXT_PUBLIC_API_BASE_URL}/projects/{projectId}/jobs/classify-files
POST {NEXT_PUBLIC_API_BASE_URL}/projects/{projectId}/jobs/extract-all
POST {NEXT_PUBLIC_API_BASE_URL}/projects/{projectId}/jobs/generate-aud-plan
POST {NEXT_PUBLIC_API_BASE_URL}/projects/{projectId}/jobs/extract-open-points
POST {NEXT_PUBLIC_API_BASE_URL}/projects/{projectId}/jobs/build-evidence-index
POST {NEXT_PUBLIC_API_BASE_URL}/projects/{projectId}/jobs/generate-source-summaries-ai
POST {NEXT_PUBLIC_API_BASE_URL}/projects/{projectId}/jobs/generate-docx
GET  {NEXT_PUBLIC_API_BASE_URL}/projects/{projectId}/jobs
GET  {NEXT_PUBLIC_API_BASE_URL}/projects/{projectId}/extracted-content
GET  {NEXT_PUBLIC_API_BASE_URL}/projects/{projectId}/evidence-items
GET  {NEXT_PUBLIC_API_BASE_URL}/projects/{projectId}/source-summaries
GET  {NEXT_PUBLIC_API_BASE_URL}/projects/{projectId}/source-priority-report
GET  {NEXT_PUBLIC_API_BASE_URL}/projects/{projectId}/aud-plan
GET  {NEXT_PUBLIC_API_BASE_URL}/projects/{projectId}/open-points
GET  {NEXT_PUBLIC_API_BASE_URL}/projects/{projectId}/generated-documents
GET  {NEXT_PUBLIC_API_BASE_URL}/projects/{projectId}/generated-documents/{documentId}/download
```
