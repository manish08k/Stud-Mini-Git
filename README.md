# Stud

A self-hosted Git hosting platform with a built-in package manager, workflow runner, and AI tooling — all in one CLI and backend server.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                          CLI (stud/)                            │
│  vcs  │  packages  │  workflows  │  ai  │  cloud  │  plugins   │
└───────────────────────────┬─────────────────────────────────────┘
                            │ HTTP
┌───────────────────────────▼─────────────────────────────────────┐
│                    FastAPI Backend (backend/)                    │
│                                                                 │
│   /auth   /repos   /repos/../refs   /repos/../objects   /graphql│
│                                                                 │
│   AsyncSession (SQLAlchemy 2)   JWT + opaque PAT auth           │
│   Per-user rate limiting        Alembic migrations (auto)       │
└────┬──────────────┬──────────────┬──────────────┬──────────────┘
     │              │              │              │
┌────▼────┐  ┌──────▼──────┐  ┌───▼───┐  ┌──────▼──────┐
│Postgres │  │    Redis     │  │ Kafka │  │  Jaeger      │
│   16    │  │  rate limit  │  │events │  │  traces      │
│         │  │  cache/pubsub│  │       │  │  OTLP:4317   │
└─────────┘  └─────────────┘  └───────┘  └─────────────┘
                                                │
                              ┌─────────────────▼──────────────┐
                              │   Object Storage                │
                              │   Local disk (dev)              │
                              │   S3 / GCS (prod, set S3_BUCKET)│
                              └────────────────────────────────┘
```

### Key Design Decisions

| Concern | Choice |
|---|---|
| DB driver | `asyncpg` (async, zero GIL blocking) |
| Auth | JWT access token (15 min) + rotating refresh token (7 days) |
| Migrations | Alembic — runs `upgrade head` automatically on startup |
| Object storage | Local disk by default; S3-compatible when `S3_BUCKET` is set |
| Events | Kafka (optional) — set `KAFKA_ENABLED=true` to activate |
| Tracing | OpenTelemetry → Jaeger (optional) |
| Rate limiting | Per-user key in Redis; IP fallback for unauthenticated requests |

---

## Prerequisites

| Tool | Version |
|---|---|
| Python | **3.12** (3.13+ not yet supported by pydantic/fastapi) |
| Docker + Docker Compose | any recent version |
| Homebrew (macOS) | optional, for local postgres/redis |

---

## Quickstart — Docker (recommended)

```bash
# 1. unzip and enter the project
unzip stud_production.zip
cd stud

# 2. start everything (postgres, redis, kafka, jaeger, api)
docker compose up --build

# 3. verify
curl http://localhost:8000/health
```

API docs available at `http://localhost:8000/docs`

---

## Quickstart — Local Dev (no Docker)

### 1. Python 3.12 environment

```bash
brew install python@3.12          # macOS
python3.12 -m venv venv
source venv/bin/activate
```

### 2. Install dependencies

```bash
# from the project root (stud/)
pip install -r backend/requirements.txt
pip install -e .
```

### 3. Start infrastructure (postgres + redis minimum)

```bash
brew install postgresql@16 redis
brew services start postgresql@16
brew services start redis

createdb stud
```

### 4. Configure environment

```bash
cp backend/.env.example backend/.env   # edit as needed
```

Minimum required vars in `backend/.env`:

```env
STUD_SERVER_DB_URL=postgresql+asyncpg://localhost/stud
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=change-me-in-production
```

### 5. Run the server

```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

Alembic migrations run automatically on startup. No manual migration step needed.

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `STUD_SERVER_DB_URL` | `sqlite:///./data/stud_server.db` | Database URL |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis URL |
| `SECRET_KEY` | `dev-secret-change-me` | JWT signing key — **change in prod** |
| `JWT_ACCESS_EXPIRE_MINUTES` | `15` | Access token lifetime |
| `JWT_REFRESH_EXPIRE_DAYS` | `7` | Refresh token lifetime |
| `APP_ENV` | `development` | Set to `production` to disable `/docs` |
| `KAFKA_ENABLED` | `false` | Enable Kafka event streaming |
| `KAFKA_BOOTSTRAP_SERVERS` | `localhost:9092` | Kafka broker |
| `S3_BUCKET` | _(empty)_ | S3 bucket name — enables S3 object storage |
| `S3_ACCESS_KEY` | _(empty)_ | S3 access key |
| `S3_SECRET_KEY` | _(empty)_ | S3 secret key |
| `S3_ENDPOINT_URL` | _(empty)_ | Custom S3 endpoint (for MinIO, R2, etc.) |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `http://localhost:4317` | Jaeger/Tempo OTLP endpoint |
| `LOG_LEVEL` | `INFO` | Logging level |
| `CORS_ORIGINS` | `http://localhost:3000,...` | Comma-separated allowed origins |

---

## API Reference

### Auth

```
POST /auth/register       → { access_token, refresh_token, expires_in }
POST /auth/login          → { access_token, refresh_token, expires_in }
POST /auth/refresh        → { access_token, refresh_token, expires_in }
POST /auth/logout         → { revoked: true }
GET  /auth/me             → { id, username, created_at }
```

### Repos

```
POST   /repos                              create repo
GET    /repos?owner=&page=&per_page=       list repos
GET    /repos/{owner}/{repo}               get repo info
PATCH  /repos/{owner}/{repo}               update repo
DELETE /repos/{owner}/{repo}               delete repo

GET    /repos/{owner}/{repo}/collaborators
POST   /repos/{owner}/{repo}/collaborators
DELETE /repos/{owner}/{repo}/collaborators/{username}
```

### Git protocol

```
GET  /repos/{owner}/{repo}/refs
GET  /repos/{owner}/{repo}/objects/{oid}
POST /repos/{owner}/{repo}/objects/{oid}
POST /repos/{owner}/{repo}/refs/{category}/{name}
```

### Health

```
GET /health    → { status: "ok" }
GET /ready     → { status: "ready"|"degraded", db, redis }
```

### GraphQL

```
POST /graphql   (GraphiQL UI available in development)
```

---

## CLI Usage

```bash
# initialise a repo
stud init

# stage and commit
stud add .
stud commit -m "initial commit"

# push to server
stud remote add origin http://localhost:8000
stud push origin main

# clone
stud clone http://localhost:8000/manish/myrepo

# package management
stud install
stud add requests@^2.31.0
stud remove requests

# workflows
stud workflow run build

# AI tools
stud ai commit          # generate commit message
stud ai review          # code review current diff
stud ai release-notes   # generate release notes
```

---

## Project Structure

```
stud/
├── backend/                  FastAPI server
│   ├── alembic/              DB migrations
│   │   └── versions/
│   │       ├── 0001_initial.py
│   │       └── 0002_async_datetime_tokens.py
│   ├── app/
│   │   ├── main.py           app factory + lifespan
│   │   ├── config.py         all env vars
│   │   ├── database.py       async SQLAlchemy engine
│   │   ├── models.py         ORM models
│   │   ├── schemas.py        Pydantic request/response schemas
│   │   ├── deps.py           auth + rate limit dependencies
│   │   ├── security.py       JWT + password hashing
│   │   ├── repo_storage.py   local disk / S3 object store
│   │   ├── redis_client.py   cache + rate limiting
│   │   ├── kafka_client.py   event streaming
│   │   ├── telemetry.py      OpenTelemetry setup
│   │   ├── graphql_schema.py Strawberry GraphQL
│   │   └── routers/
│   │       ├── auth.py
│   │       ├── repos.py
│   │       └── git.py
│   ├── alembic.ini
│   └── requirements.txt
├── stud/                     CLI + core library
│   ├── vcs/                  version control (commit, merge, rebase, cherry-pick)
│   ├── packages/             package manager (semver, resolver, lockfile)
│   ├── workflows/            CI/CD runner (triggers, secrets, scheduler)
│   ├── ai/                   AI integrations (commit msg, code review, release notes)
│   ├── cloud/                deploy targets (python, node, react, flutter, angular)
│   ├── security/             vuln scanner, secret scanner, signatures
│   ├── plugins/              plugin SDK + marketplace
│   └── cli/                  commands + REPL + autocomplete
├── tests/
│   ├── unit/
│   └── integration/
├── Dockerfile
├── docker-compose.yml
└── pyproject.toml
```

---

## Running Tests

```bash
# from project root
pytest tests/unit -v
pytest tests/integration -v    # requires running backend
pytest --cov=stud --cov=backend/app tests/
```

---

## Production Checklist

- [ ] Set `SECRET_KEY` to a random 32+ char string
- [ ] Set `APP_ENV=production` (disables `/docs` and `/redoc`)
- [ ] Use PostgreSQL — set `STUD_SERVER_DB_URL=postgresql+asyncpg://...`
- [ ] Set `S3_BUCKET` + credentials (prevents data loss on pod restarts)
- [ ] Point `OTEL_EXPORTER_OTLP_ENDPOINT` to your Grafana Tempo / Jaeger
- [ ] Set `CORS_ORIGINS` to your actual frontend domain
- [ ] Run behind a reverse proxy (nginx / Caddy) with TLS