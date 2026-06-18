# stud

> **VCS · Package Manager · CI/CD · AI tooling — in one CLI + production-ready server**

[![CI](https://github.com/YOUR_ORG/stud/actions/workflows/ci.yml/badge.svg)](https://github.com/YOUR_ORG/stud/actions)
[![Coverage](https://codecov.io/gh/YOUR_ORG/stud/branch/main/graph/badge.svg)](https://codecov.io/gh/YOUR_ORG/stud)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](https://python.org)
[![Docker](https://img.shields.io/badge/docker-ready-blue)](./Dockerfile)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [CLI Quick Start](#cli-quick-start)
4. [CLI Commands Reference](#cli-commands-reference)
5. [Backend Server](#backend-server)
6. [Configuration (.env)](#configuration-env)
7. [Docker](#docker)
8. [Kubernetes](#kubernetes)
9. [Database Migrations (Alembic)](#database-migrations-alembic)
10. [GraphQL API](#graphql-api)
11. [Kafka Event Streaming](#kafka-event-streaming)
12. [Redis Caching & Rate Limiting](#redis-caching--rate-limiting)
13. [OpenTelemetry Observability](#opentelemetry-observability)
14. [AI Features](#ai-features)
15. [Testing](#testing)
16. [GitHub Actions CI/CD](#github-actions-cicd)
17. [Production Checklist](#production-checklist)
18. [Module Reference](#module-reference)

---

## Overview

`stud` is a developer platform combining:

| Layer | What it does |
|---|---|
| **CLI** (`stud`) | Git-like VCS, semver package manager, YAML CI/CD, AI-powered commit messages / code review |
| **Backend** (FastAPI) | REST + GraphQL API for remote repo hosting, auth, collaborators, and event streaming |
| **Infrastructure** | Docker, Kubernetes (HPA + rolling deploys), Alembic migrations, Redis, Kafka, OpenTelemetry |

---

## Architecture

```
┌─────────────────────────────────────────────────┐
│  stud CLI (Python)                              │
│  vcs · packages · workflows · ai · security     │
└───────────────┬─────────────────────────────────┘
                │ HTTP / stud-remote protocol
┌───────────────▼─────────────────────────────────┐
│  FastAPI Backend                                │
│  REST /auth /repos /git                        │
│  GraphQL /graphql  (Strawberry)                │
│  Middleware: CORS · rate-limit · request log    │
└────┬───────────┬───────────────┬────────────────┘
     │           │               │
  Postgres    Redis           Kafka
  (SQLAlchemy  (cache +       (event
  + Alembic)   rate limit)    streaming)
                                │
                         OpenTelemetry
                         (Jaeger / Tempo)
```

---

## CLI Quick Start

```bash
# install
pip install -e ".[rich]"

# init a project
stud init my-project
cd my-project

# VCS workflow
stud add .
stud commit -m "feat: initial commit"
stud branch feature
stud checkout feature
stud add .
stud ai commit          # AI-generated commit message
stud merge feature

# packages
stud pkg add requests@^2.31
stud pkg install
stud pkg publish

# CI/CD
stud run ci             # run .stud/workflows/ci.yml

# security
stud audit              # CVE scan + secret scan

# remotes
stud remote add origin https://stud.example.com/alice/myrepo
stud push
stud pull
```

---

## CLI Commands Reference

### VCS

| Command | Description |
|---|---|
| `stud init [dir]` | Initialise a new repository |
| `stud add [paths]` | Stage files |
| `stud commit -m MSG` | Create a commit |
| `stud log` | Show commit history |
| `stud diff` | Show unstaged changes |
| `stud branch NAME` | Create a branch |
| `stud checkout NAME` | Switch branch |
| `stud merge NAME` | Merge branch into HEAD |
| `stud rebase TARGET` | Rebase current branch |
| `stud cherry-pick OID` | Cherry-pick a commit |
| `stud tag NAME` | Create a tag |
| `stud stash` | Stash working changes |
| `stud remote add NAME URL` | Add a remote |
| `stud push [remote] [branch]` | Push to remote |
| `stud pull [remote] [branch]` | Pull from remote |
| `stud clone URL DIR` | Clone a remote repo |

### Packages

| Command | Description |
|---|---|
| `stud pkg add PKG@VER` | Add dependency |
| `stud pkg remove PKG` | Remove dependency |
| `stud pkg install` | Install all dependencies |
| `stud pkg update` | Update to latest semver-compatible |
| `stud pkg publish` | Publish to registry |
| `stud pkg search QUERY` | Search registry |

### Workflows (CI/CD)

| Command | Description |
|---|---|
| `stud run WORKFLOW` | Run a workflow file |
| `stud workflow list` | List available workflows |
| `stud workflow generate` | AI-generate a workflow YAML |

### AI

| Command | Description |
|---|---|
| `stud ai commit` | Generate commit message from staged diff |
| `stud ai review [FILE]` | AI code review |
| `stud ai release` | Generate release notes from git log |
| `stud ai workflow` | Generate CI workflow YAML |
| `stud ai deps` | AI dependency advice |

### Security

| Command | Description |
|---|---|
| `stud audit` | Full security audit (CVE + secrets) |
| `stud scan secrets` | Entropy-based secret scanner |
| `stud scan vulns` | CVE scanner via OSV |

### Extras (50+ commands)

```
stud config set KEY VALUE   # set global config
stud config get KEY
stud repl                   # interactive REPL
stud completion bash        # shell completion
stud plugin install NAME    # install plugin
stud plugin list
stud cloud deploy           # deploy to cloud target
stud cloud targets          # list build targets
```

---

## Backend Server

### Local development

```bash
cd backend
cp .env.example .env          # fill in secrets
uvicorn app.main:app --reload
# → http://localhost:8000
# → http://localhost:8000/docs    (Swagger UI, dev only)
# → http://localhost:8000/graphql (GraphiQL)
```

### REST API endpoints

| Method | Path | Description |
|---|---|---|
| POST | `/auth/register` | Register a new user |
| POST | `/auth/login` | Login, get bearer token |
| GET | `/auth/me` | Current user info |
| GET | `/repos` | List repositories |
| POST | `/repos` | Create a repository |
| GET | `/repos/{owner}/{repo}` | Get repo info |
| PATCH | `/repos/{owner}/{repo}` | Update repo settings |
| DELETE | `/repos/{owner}/{repo}` | Delete a repo |
| GET | `/repos/{owner}/{repo}/collaborators` | List collaborators |
| POST | `/repos/{owner}/{repo}/collaborators` | Add collaborator |
| DELETE | `/repos/{owner}/{repo}/collaborators/{user}` | Remove collaborator |
| POST | `/repos/{owner}/{repo}/objects` | Push a git object |
| GET | `/repos/{owner}/{repo}/objects/{oid}` | Fetch a git object |
| GET | `/repos/{owner}/{repo}/refs` | List refs |
| PUT | `/repos/{owner}/{repo}/refs/{ref}` | Update a ref |
| GET | `/health` | Liveness probe |
| GET | `/ready` | Readiness probe (checks DB + Redis) |

---

## Configuration (.env)

Copy `backend/.env.example` to `backend/.env` and fill in the values:

```env
# Core
APP_ENV=development
SECRET_KEY=<64-char random string>

# Database (SQLite for dev, Postgres for production)
STUD_SERVER_DB_URL=sqlite:///./data/stud_server.db

# Redis
REDIS_URL=redis://localhost:6379/0

# Kafka (set KAFKA_ENABLED=true to activate)
KAFKA_ENABLED=false
KAFKA_BOOTSTRAP_SERVERS=localhost:9092

# AI
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...

# Observability
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
LOG_LEVEL=INFO

# Auth
JWT_SECRET_KEY=<random>
JWT_EXPIRE_MINUTES=60
```

All settings are read from environment variables. The app uses `python-dotenv` to
auto-load `backend/.env` when present — no file is required in production (inject
secrets via Kubernetes Secrets or Vault).

---

## Docker

```bash
# build
docker build -t stud-backend .

# run (single container)
docker run -p 8000:8000 \
  -e STUD_SERVER_DB_URL=sqlite:///./data/stud_server.db \
  stud-backend

# full stack (Postgres + Redis + Kafka + Jaeger)
docker compose up
```

The `Dockerfile` uses a **multi-stage build** (builder → runtime) and runs as a
non-root user. A `HEALTHCHECK` pings `/health` every 30 s.

---

## Kubernetes

### Deploy

```bash
# create namespace + secrets + PVC
kubectl apply -f k8s/infra.yaml

# fill in the secret values
kubectl edit secret stud-secrets -n stud

# deploy app + service + HPA
kubectl apply -f k8s/deployment.yaml

# ingress with TLS (requires cert-manager)
kubectl apply -f k8s/ingress.yaml
```

### Key features

- **Rolling updates** – zero downtime (`maxUnavailable: 0`)
- **HPA** – scales 2→10 pods on CPU (70%) / memory (80%)
- **Liveness** → `/health`  |  **Readiness** → `/ready`
- **Non-root** security context
- **PVC** for repo object storage (`ReadWriteMany`)

---

## Database Migrations (Alembic)

```bash
cd backend

# apply all pending migrations
alembic upgrade head

# create a new migration after changing models.py
alembic revision --autogenerate -m "add_webhook_table"

# rollback one step
alembic downgrade -1

# show current state
alembic current
alembic history
```

Migrations live in `backend/alembic/versions/`. The `env.py` reads `DATABASE_URL`
from the app config so it works with SQLite (dev) and Postgres (production).

---

## GraphQL API

Available at `/graphql` (GraphiQL explorer in dev).

### Example queries

```graphql
# list all public repos
query {
  repos { id owner name defaultBranch }
}

# get a specific repo
query {
  repo(owner: "alice", name: "myrepo") { id private }
}

# list collaborators
query {
  collaborators(owner: "alice", repo: "myrepo") {
    username role
  }
}
```

GraphQL is implemented with **Strawberry** and mounted on the FastAPI app.
It shares the same SQLAlchemy session pool as the REST API.

---

## Kafka Event Streaming

Set `KAFKA_ENABLED=true` to activate. Events are published to `stud.events`:

```python
# in a router handler
from app.kafka_client import emit_event

emit_event("repo.push", {"owner": "alice", "repo": "myrepo", "branch": "main"})
```

Event schema:
```json
{ "event": "repo.push", "owner": "alice", "repo": "myrepo", "branch": "main" }
```

When Kafka is disabled (default) all `emit_event` calls are no-ops — the rest of
the app is unaffected.

---

## Redis Caching & Rate Limiting

Redis is used for:

1. **Per-IP rate limiting** – 120 req/min by default (`RATE_LIMIT_PER_MINUTE`).
   Returns `429 Too Many Requests` when exceeded.
2. **Cache helpers** – `cache_get / cache_set / cache_delete` with TTL.
3. **Pub/Sub** – `publish_event` for lightweight real-time fanout.

When Redis is unavailable the app degrades gracefully:
- Rate limiting **fails open** (requests are allowed through).
- Cache misses return `None`.

---

## OpenTelemetry Observability

The app auto-instruments FastAPI and SQLAlchemy when the OTel SDK is installed.
Traces are exported to the OTLP endpoint (`OTEL_EXPORTER_OTLP_ENDPOINT`).

```bash
# run Jaeger locally (includes OTLP receiver)
docker run -p 16686:16686 -p 4317:4317 jaegertracing/all-in-one

# open the UI
open http://localhost:16686
```

All HTTP requests produce structured **JSON logs** with `ts`, `level`, `logger`,
`msg`, `method`, `path`, `status`, `duration_ms`, `ip` fields — ready for
Loki / Elasticsearch ingestion.

---

## AI Features

`stud` ships with a **provider-agnostic LLM client** (`stud.ai.client.LLMClient`)
supporting Anthropic (Claude) and OpenAI (GPT-4o).

| Feature | Command | Description |
|---|---|---|
| Commit messages | `stud ai commit` | Reads staged diff, generates conventional commit |
| Code review | `stud ai review FILE` | Reviews a file or diff for issues |
| Release notes | `stud ai release` | Summarises commits since last tag |
| Workflow gen | `stud ai workflow` | Generates CI YAML from project context |
| Dep advisor | `stud ai deps` | Advises on dependency versions/alternatives |

Set `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` in your environment or `.env` file.
Switch provider with `--provider openai`.

---

## Testing

```bash
# all tests
pytest tests/ -v

# with coverage (must be ≥ 80%)
pytest tests/ --cov=stud --cov=backend/app --cov-report=term-missing --cov-fail-under=80

# unit tests only (fast, no server needed)
pytest tests/unit/ -v

# integration tests only
pytest tests/integration/ -v
```

### Test structure

```
tests/
├── unit/
│   ├── test_core.py          # ObjectStore, IgnoreFilter, EventBus, Config
│   ├── test_semver.py        # semver parsing and resolution
│   ├── test_vcs.py           # VCS commit/branch/merge/rebase
│   └── test_infra.py         # Redis, Kafka, logging, config (NEW)
└── integration/
    ├── test_packages.py      # package resolver
    └── test_backend_api.py   # full REST API via TestClient (NEW)
```

---

## GitHub Actions CI/CD

The `.github/workflows/ci.yml` pipeline runs on every push / PR:

| Job | Triggers | Does |
|---|---|---|
| **lint** | all pushes | Ruff lint + format check, Mypy type check |
| **test** | all pushes | pytest on Python 3.11 & 3.12, coverage ≥ 80% |
| **docker** | `main` merge | Build multi-platform image, push to GHCR |
| **deploy** | `main` merge | `kubectl set image` → rolling deploy to K8s |

Secrets needed in GitHub repo settings:
- `KUBECONFIG` – base64-encoded kubeconfig for the production cluster

---

## Production Checklist

| # | Item | Status |
|---|---|---|
| 1 | ✅ `.env.example` with all variables documented | done |
| 2 | ✅ Postgres via `STUD_SERVER_DB_URL` | done |
| 3 | ✅ Alembic migrations (`alembic upgrade head`) | done |
| 4 | ✅ Redis rate limiting + caching | done |
| 5 | ✅ Kafka event streaming (opt-in) | done |
| 6 | ✅ Structured JSON logging | done |
| 7 | ✅ OpenTelemetry tracing | done |
| 8 | ✅ GraphQL API (`/graphql`) | done |
| 9 | ✅ Docker multi-stage build, non-root user | done |
| 10 | ✅ Kubernetes: rolling deploy, HPA, liveness/readiness probes | done |
| 11 | ✅ GitHub Actions: lint → test → build → deploy | done |
| 12 | ✅ Test coverage ≥ 80% | done |
| 13 | ✅ AI features (commit, review, release notes) | done |
| 14 | ✅ CORS middleware | done |
| 15 | ⚠️ TLS / cert-manager (configure in `k8s/ingress.yaml`) | configure |
| 16 | ⚠️ Kubernetes Secrets via Vault / Sealed Secrets | configure |

---

## Module Reference

| Module | Key files | Purpose |
|---|---|---|
| `stud.core` | `config`, `object_store`, `hashing`, `events`, `lockmanager` | Foundations |
| `stud.vcs` | `service`, `objects`, `refs`, `diff`, `merge`, `rebase`, `remote` | Git-like VCS |
| `stud.packages` | `semver`, `manifest`, `lockfile`, `resolver`, `publisher` | Package manager |
| `stud.workflows` | `schema`, `runner`, `scheduler`, `triggers`, `secrets` | CI/CD engine |
| `stud.plugins` | `sdk`, `loader`, `registry`, `marketplace_client` | Plugin system |
| `stud.cloud` | `deploy`, targets: `python/node/react/angular/flutter` | Cloud deploy |
| `stud.security` | `vuln_scanner`, `secret_scanner`, `signatures`, `audit` | Security |
| `stud.ai` | `client`, `commit_messages`, `code_review`, `release_notes` | AI features |
| `stud.cli` | `main`, `ui`, `repl`, `completion`, `wizards`, commands/ | CLI |
| `backend.app` | `main`, `config`, `models`, `routers/`, `redis_client`, `kafka_client`, `telemetry`, `graphql_schema` | Server |

---

## Requirements

- Python 3.11+
- `pyyaml` (CLI core)
- `rich` (optional, coloured output)
- `python-dotenv` (optional, local .env loading)
- See `backend/requirements.txt` for the full server stack
