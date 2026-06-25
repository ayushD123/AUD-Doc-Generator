# Frontend

Next.js TypeScript frontend for the Oracle AUD Generator.

This phase includes a minimal App Router setup, project creation, project listing, project detail workspace, collapsible project detail sections, local file upload UI, one-click AUD generation, generation progress polling, extracted content review, read-only evidence index review, read-only source summary review, read-only AI section draft review, and final DOCX download controls that call the backend using `NEXT_PUBLIC_API_BASE_URL`. It does not include authentication, document parsing in the frontend, complex styling, review workflow UI, quality reports, or editing generated AUD content in the browser.

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

## Ubuntu VM Production Run

On the OCI Ubuntu VM, build the frontend and run it behind Nginx instead of
using `npm run dev`:

```bash
cd /opt/aud-generator/frontend
npm ci
npm run build
npm run start -- -H 127.0.0.1 -p 3000
```

Set `NEXT_PUBLIC_API_BASE_URL` in `.env.production` before building. When Nginx
routes `/api/` to the backend, use:

```text
NEXT_PUBLIC_API_BASE_URL=https://<domain>/api
```

For an HTTP-only first smoke test, use `http://<vm-public-ip-or-domain>/api`.
Rebuild the frontend after changing this value. The complete VM deployment
runbook is in [`../docs/deployment-oci-vm.md`](../docs/deployment-oci-vm.md).

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

In a third terminal, start the local backend worker loop and leave it running:

```powershell
cd ..\backend
.\.venv\Scripts\Activate.ps1
python -m app.workers.local_worker --loop
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
- Near the top of the project detail page, click Generate AUD.
- Confirm the Generate AUD button is disabled and shows a generating state.
- Confirm the AUD Generation panel shows current status, current stage, completed stages, warnings, and any backend error.
- Confirm the frontend polls `GET /projects/{projectId}/generate-aud/status` every few seconds while the run is not terminal.
- Confirm the already-running local worker loop processes the queued AUD generation job automatically.
- Expected result for one-click generation: the run reaches `completed` or `completed_with_warnings`, or shows `failed` with the failed stage and backend error.
- Confirm polling stops when the status is `completed`, `completed_with_warnings`, or `failed`.
- When completed or completed with warnings, confirm the page shows `Final AUD is ready`.
- Confirm the Final Generated AUD DOCX card appears at the top of the project detail page with a Download DOCX link.
- Confirm generated documents refresh automatically after completion.
- Expand Jobs / Debug Information and then Developer / Debug Actions.
- Confirm intermediate buttons such as Extract All Files, Generate AUD Plan, Build Evidence Index, Generate AI Source Summaries, Generate AI Section Drafts, and Generate DOCX are available only inside Developer / Debug Actions.
- Confirm existing debug and partial-output sections remain available below the one-click flow.
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
- Confirm the Section Drafts card appears on the project detail page.
- Click Refresh Section Drafts.
- Expected result before draft generation: the card shows `No section drafts generated yet.`
- After backend section draft generation has run, expected result: drafts are grouped by AUD order and show title, confidence, review status, draft preview, unsupported details, placeholders, and open point candidates.
- Expand and collapse full draft text for a section draft.
- Confirm the note appears: `AI draft requires senior consultant review before customer sharing.`
- Confirm the Extracted Content card appears on the project detail page.
- Click Refresh Extracted Content.
- Expected result before extraction: the card shows `No extracted content yet.`
- After backend DOCX or transcript extraction has run, expected result: the card lists extracted records with title, content type, created date, source role when present, golden source status, and available counts.
- Open Preview on an extracted record.
- Expected result: extracted text appears only inside the collapsed Preview area and stays within a scrollable max-height region.
- Confirm the Generated Documents card appears on the project detail page.
- Click Refresh Documents.
- Expected result before DOCX generation: the card shows `No generated documents yet.`
- After backend AUD generation has run, expected result: the card lists each generated document filename, created date, and a Download DOCX link, with the final AUD sorted first.
- Click Download DOCX.
- Expected result: the browser downloads the file from the backend generated document download endpoint.
- Confirm no review workflow UI or quality/evidence report UI has been added.

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
POST {NEXT_PUBLIC_API_BASE_URL}/projects/{projectId}/jobs/generate-section-drafts-ai
POST {NEXT_PUBLIC_API_BASE_URL}/projects/{projectId}/jobs/generate-docx
POST {NEXT_PUBLIC_API_BASE_URL}/projects/{projectId}/generate-aud
GET  {NEXT_PUBLIC_API_BASE_URL}/projects/{projectId}/generate-aud/status
GET  {NEXT_PUBLIC_API_BASE_URL}/projects/{projectId}/jobs
GET  {NEXT_PUBLIC_API_BASE_URL}/projects/{projectId}/extracted-content
GET  {NEXT_PUBLIC_API_BASE_URL}/projects/{projectId}/evidence-items
GET  {NEXT_PUBLIC_API_BASE_URL}/projects/{projectId}/source-summaries
GET  {NEXT_PUBLIC_API_BASE_URL}/projects/{projectId}/section-drafts
GET  {NEXT_PUBLIC_API_BASE_URL}/projects/{projectId}/source-priority-report
GET  {NEXT_PUBLIC_API_BASE_URL}/projects/{projectId}/aud-plan
GET  {NEXT_PUBLIC_API_BASE_URL}/projects/{projectId}/open-points
GET  {NEXT_PUBLIC_API_BASE_URL}/projects/{projectId}/generated-documents
GET  {NEXT_PUBLIC_API_BASE_URL}/projects/{projectId}/generated-documents/{documentId}/download
```
