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
# Edit .env — set a real SECRET_KEY for anything beyond local tinkering

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

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `SECRET_KEY` | yes | Django secret key |
| `DATABASE_URL` | yes | Postgres URL, e.g. `postgres://leadcrm:leadcrm@127.0.0.1:5433/leadcrm` |
| `DEBUG` | no | `True`/`False` (local defaults toward True) |
| `READ_DOT_ENV_FILE` | no | Load project-root `.env` (default: load if file exists) |
| `DJANGO_ENV` | no | `local` (default) or `prod` |
| `ALLOWED_HOSTS` | prod | Comma-separated hosts (required in prod) |
| `SECURE_SSL_REDIRECT` | prod | Default `True` in prod |
| `EMAIL_BACKEND` | no | Override email backend (prod defaults to SMTP) |

Copy from `.env.example`. Never commit `.env`.

## Settings modules

| Module | When |
|--------|------|
| `djcrm.settings` | Default entry (`DJANGO_SETTINGS_MODULE`). Loads local or prod via `DJANGO_ENV`. |
| `djcrm.settings.local` | Local/dev (console email, relaxed hosts) |
| `djcrm.settings.prod` | Production (`DJANGO_ENV=prod`) |
| `djcrm.settings.base` | Shared settings — do not point `DJANGO_SETTINGS_MODULE` here alone |

```bash
# Production-style check locally
DJANGO_ENV=prod ALLOWED_HOSTS=example.com DEBUG=False python manage.py check --deploy
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
