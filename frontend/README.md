# Frontend

Next.js TypeScript frontend skeleton for the Oracle AUD Generator.

This phase includes a minimal App Router setup, project creation, project listing, project detail workspace, local file upload UI, job controls, and extracted content review that calls the backend using `NEXT_PUBLIC_API_BASE_URL`. It does not include authentication, document parsing in the frontend, complex styling, editing extracted content, or AUD generation.

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
- In Uploaded Files, select a source role such as KT Session (MP4) and choose an allowed file type.
- Click Upload File.
- Confirm the uploaded file list refreshes and shows filename, source role, file type, and created date.
- In Jobs, click Extract All Files.
- Confirm the jobs list refreshes with a pending `extract_all` job.
- In Jobs, click Generate AUD Plan.
- Confirm the jobs list refreshes with a pending `generate_aud_plan` job.
- In Jobs, click Classify Files.
- Confirm the jobs list refreshes with a pending `classify_files` job.
- In a backend terminal, run `python -m app.workers.local_worker`.
- Click Refresh Jobs and confirm the job status/progress updates.
- Expected result for Extract All Files: the job reaches `completed` at `100%`, or `completed_with_warnings` if some files extracted and some failed.
- Confirm the AUD Plan card appears on the project detail page.
- Click Refresh AUD Plan.
- Expected result before plan generation: the card shows `No AUD plan generated yet.`
- After backend AUD plan generation has run, expected result: the card shows whether the default template is required and lists planned sections in order with title, confidence, include flag, source role basis, and notes.
- Confirm the Source Priority card appears on the project detail page.
- Click Refresh Source Priority.
- Expected result: the card shows explicit template status, FDD golden source status, source roles present, priority order, warnings, and whether the default SCM template will be needed later.
- Confirm the Extracted Content card appears on the project detail page.
- Click Refresh Extracted Content.
- Expected result before extraction: the card shows `No extracted content yet.`
- After backend DOCX or transcript extraction has run, expected result: the card lists extracted records with title, content type, created date, source role when present, golden source status, and available counts.
- Open Preview on an extracted record.
- Expected result: extracted text appears only inside the collapsed Preview area and stays within a scrollable max-height region.
- Confirm the detail page still shows the placeholder section for Generated Documents.

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
GET  {NEXT_PUBLIC_API_BASE_URL}/projects/{projectId}/jobs
GET  {NEXT_PUBLIC_API_BASE_URL}/projects/{projectId}/extracted-content
GET  {NEXT_PUBLIC_API_BASE_URL}/projects/{projectId}/source-priority-report
GET  {NEXT_PUBLIC_API_BASE_URL}/projects/{projectId}/aud-plan
```
