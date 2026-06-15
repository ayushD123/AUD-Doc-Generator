# Frontend

Next.js TypeScript frontend skeleton for the Oracle AUD Generator.

This phase includes a minimal App Router setup, project creation, project listing, and a project detail workspace that calls the backend using `NEXT_PUBLIC_API_BASE_URL`. It does not include authentication, upload functionality, complex styling, or a component library.

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
- Confirm the detail page shows placeholder sections for Uploaded Files, Jobs, AUD Plan, and Generated Documents.

The frontend calls:

```text
POST {NEXT_PUBLIC_API_BASE_URL}/projects
GET  {NEXT_PUBLIC_API_BASE_URL}/projects
GET  {NEXT_PUBLIC_API_BASE_URL}/projects/{projectId}
```
