# Deployment Guide

InfoEdge can be deployed as a static frontend demo and as a full local or self-hosted stack with the FastAPI backend.

## Static Frontend Demo

The public demo is published with GitHub Pages:

```text
https://gaoyu666.github.io/infoedge/
```

The demo intentionally does not bundle private API keys, cookies, paid-source credentials, or backend secrets. Without a backend URL, the app shows empty states and explains how to configure the API.

The Pages workflow lives at:

```text
.github/workflows/pages.yml
```

It builds the Vite app with:

```bash
VITE_BASE_PATH=/infoedge/ npm run build
```

## Full Local Stack

Run the backend locally:

```bash
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Then run the frontend:

```bash
npm install
npm run dev
```

The frontend automatically tries local backend URLs. To force a specific backend:

```bash
echo VITE_API_BASE_URL=http://127.0.0.1:8000 > .env.local
```

## Production Notes

- Serve the frontend from any static host that supports Vite output.
- Serve the backend behind HTTPS.
- Provide `VITE_API_BASE_URL` at build time for hosted frontend deployments.
- Keep database, Redis, Apify, GLM, and other provider credentials in server-side environment variables only.
- Enable only data sources you are authorized to use.
