# Local Backend Setup

This guide covers the minimal backend services needed for local InfoEdge development.

## Requirements

- Python 3.12
- PostgreSQL 14 or newer
- Redis 7 or newer

## Environment

Copy the backend environment template:

```bash
cd backend
copy .env.example .env
```

Common local values:

```text
PG_USER=postgres
PG_PASSWORD=change_me
PG_HOST=localhost
PG_PORT=5432
PG_DB=postgres

REDIS_HOST=localhost
REDIS_PORT=6370
REDIS_PASSWORD=
REDIS_DB=0
```

Do not commit `.env`.

## Start the API

```bash
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Verify the service:

```text
GET http://127.0.0.1:8000/api/health
```

## Frontend Connection

The frontend checks local backend URLs automatically when running on `localhost` or `127.0.0.1`.

To pin a backend:

```bash
echo VITE_API_BASE_URL=http://127.0.0.1:8000 > .env.local
```

## Source Credentials

Public sources can be cataloged without credentials. Gated sources need authorized configuration such as:

```text
APIFY_TOKEN
GLM_API_KEY
```

Only enable connectors you are allowed to access.
