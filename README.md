# Local development

## Prerequisites

- Python 3.11+ (see `.python-version`)
- Docker Desktop (for PostgreSQL)

## First-time setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
make db-up          # starts Postgres on localhost:5433
make migrate
make createsuperuser
make run            # http://127.0.0.1:8001/
```

## Day-to-day

```bash
source .venv/bin/activate
make db-up          # if Postgres is not already running
make run
```

## Database

Local/dev uses **PostgreSQL only** (no SQLite). Connection comes from `DATABASE_URL` in `.env`:

```text
postgres://leadcrm:leadcrm@127.0.0.1:5433/leadcrm
```

Docker maps container `5432` → host **`5433`** so it does not clash with a system Postgres on `5432`.
| Make target | What it does |
|-------------|--------------|
| `make db-up` | `docker compose up -d db` |
| `make db-down` | Stop containers |
| `make db-reset` | Wipe Postgres volume and recreate |
| `make migrate` | Apply Django migrations |
| `make run` | Runserver on port 8001 |

Redis is defined in `docker-compose.yml` under the `workers` profile (for later Celery work):

```bash
docker compose --profile workers up -d
```
