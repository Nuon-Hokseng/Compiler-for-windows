# Instagram Automation Tools — Frontend

Next.js 16 + TypeScript + shadcn/ui dashboard for the Instagram research & automation backend.

## Setup

```bash
cd frontend
npm install
```

### Environment

Create `.env.local` (already included):

```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Change this to your backend URL in production.

## Run

```bash
# Development
npm run dev          # → http://localhost:3000

# Production
npm run build
npm start
```

## Backend

The FastAPI backend must be running and accepting CORS from the frontend origin.

```bash
cd backend
pip install -r requirements.txt
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

The backend allows CORS from `http://localhost:3000` by default.

## Pages

| Route      | Description                                          |
| ---------- | ---------------------------------------------------- |
| `/`        | Dashboard — session status, recent jobs, quick links |
| `/targets` | Browse target customers, hashtags, niches            |
| `/analyze` | Classify / Analyze usernames with AI                 |
| `/scrape`  | Start scraper jobs, poll progress, view results      |

## Tech Stack

- **Next.js 16** (App Router)
- **TypeScript**
- **Tailwind CSS v4**
- **shadcn/ui** (Button, Card, Table, Select, Tabs, Dialog, Badge, Alert, Textarea, Input, Skeleton, Sonner Toast, Sheet)
- **lucide-react** icons
