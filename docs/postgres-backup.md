# PostgreSQL backup and restore

Lead CRM uses PostgreSQL via `DATABASE_URL`. These steps assume Docker Compose from ticket 02 (`postgres` service on host port **5433**).

## Backup (logical dump)

```bash
# From project root — adjust user/db if your .env differs
export DATABASE_URL=postgres://leadcrm:leadcrm@127.0.0.1:5433/leadcrm

pg_dump "$DATABASE_URL" --format=custom --file=leadcrm-$(date +%Y%m%d).dump
```

For plain SQL (human-readable):

```bash
pg_dump "$DATABASE_URL" --file=leadcrm-$(date +%Y%m%d).sql
```

**Production:** run `pg_dump` from a bastion or scheduled job with credentials from your secrets store. Store dumps off-server (S3, etc.) with encryption.

## Restore

```bash
# Custom format
pg_restore --clean --if-exists --dbname="$DATABASE_URL" leadcrm-YYYYMMDD.dump

# Plain SQL
psql "$DATABASE_URL" < leadcrm-YYYYMMDD.sql
```

`--clean` drops existing objects before restore — use only when you intend to replace the database contents.

## Docker Compose one-liner

If Postgres runs in Compose service `db`:

```bash
docker compose exec -T db pg_dump -U leadcrm leadcrm > leadcrm-$(date +%Y%m%d).sql
```

## Verify after restore

```bash
python manage.py migrate --check
python manage.py check
```

## Retention (recommended)

- Daily automated backups, keep 7–30 days
- Test restore quarterly on a staging database
- Never commit dumps or `.env` to git
