# InfoEdge Backend (FastAPI)

## Quick Start

1. Install dependencies

```bash
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

2. Configure environment variables

```bash
copy .env.example .env
```

Edit `.env` for your local services. Do not commit real database, Redis, Apify, or GLM credentials.

Required database settings:

- `PG_HOST`
- `PG_PORT`
- `PG_USER`
- `PG_PASSWORD`
- `PG_DB`

Optional Redis settings:

- `REDIS_HOST`
- `REDIS_PORT`
- `REDIS_PASSWORD`
- `REDIS_DB`

3. Start the API

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## Core Endpoints

- `GET /api/health`
- `GET /api/dashboard/stats`
- `GET /api/signals`
- `GET /api/signals/{id}`
- `POST /api/signals/{id}/feedback`
- `GET /api/settings/models/registry`
- `PUT /api/settings/models/allocation`
- `PATCH /api/settings/models/registry`
