# Frontend

Next.js TypeScript frontend skeleton for the Oracle AUD Generator.

This phase includes a minimal App Router setup and a health-check UI that calls the backend using `NEXT_PUBLIC_API_BASE_URL`. It does not include authentication, upload functionality, complex styling, or a component library.

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

## Check Backend Health

Start the backend first, then open the frontend and click **Check Backend Health**.

The button calls:

```text
GET {NEXT_PUBLIC_API_BASE_URL}/health
```
