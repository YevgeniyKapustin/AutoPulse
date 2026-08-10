# Backup & restore runbook

Hybrid storage means **two** sources of truth you must back up together:

| Store | Owns | Compose volume / service |
|-------|------|--------------------------|
| MongoDB | Listing enrichment state, enrichment inbox/outbox | `mongodb_data` / `mongodb` |
| MySQL | `pricing_results`, pricer inbox/outbox | `mysql_data` / `mysql` |

RabbitMQ holds in-flight messages only. Do **not** treat `rabbitmq_data` as
application restore. After a DB restore, empty or rebuild queues if messages
would replay against older documents.

Defaults below match local `.env.example`. In production substitute real
credentials and never pipe passwords on shared shells when you can use
env files / secrets.

## Prerequisites

- Stack healthy: `docker compose ps`
- Enough disk for dump files
- Quiet window preferred (pause crawler / dealers posting) so dumps are
  roughly consistent across Mongo + MySQL

Project root from these commands:

```bash
cd /path/to/AutoPulse
mkdir -p backups
STAMP=$(date -u +%Y%m%dT%H%M%SZ)   # Git Bash / Linux / macOS
```

PowerShell stamp:

```powershell
$STAMP = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
New-Item -ItemType Directory -Force backups | Out-Null
```

## Backup

### MongoDB (logical dump)

Database name defaults to `autopulse` (`MONGODB_DB`).

```bash
docker compose exec -T mongodb \
  mongodump --db=autopulse --archive --gzip \
  > "backups/mongo-autopulse-${STAMP}.archive.gz"
```

Verify non-empty:

```bash
ls -lh "backups/mongo-autopulse-${STAMP}.archive.gz"
```

### MySQL (logical dump)

Database defaults to `autopulse_pricing`. Prefer the app user or root from
your env (`MYSQL_USER` / `MYSQL_PASSWORD` / `MYSQL_ROOT_PASSWORD`).

```bash
docker compose exec -T mysql \
  mysqldump \
    -u"${MYSQL_USER:-autopulse}" \
    -p"${MYSQL_PASSWORD:-autopulse}" \
    --single-transaction \
    --routines \
    --triggers \
    "${MYSQL_DATABASE:-autopulse_pricing}" \
  | gzip > "backups/mysql-autopulse_pricing-${STAMP}.sql.gz"
```

On Windows PowerShell, avoid broken stdin piping into gzip by writing SQL
then compressing:

```powershell
docker compose exec -T mysql `
  mysqldump -uautopulse -pautopulse --single-transaction `
  --routines --triggers autopulse_pricing `
  | Set-Content -Encoding utf8 "backups/mysql-autopulse_pricing-$STAMP.sql"
# Then gzip/Compress-Archive as you prefer.
```

### What about Alembic?

Dumps include the `alembic_version` table when present. Restore the dump
**before** running new migrations against an empty DB. If schema and dump
disagree, prefer dump schema + stamp, or restore then `alembic upgrade head`
only if the dump is an older revision.

### Retention (suggested)

| Environment | Keep |
|-------------|------|
| Local DX | Last 2–3 dumps is enough |
| Shared / prod | Daily dump ≥ 7 days; weekly ≥ 4 weeks off-host |

Store prod dumps off the compose host (object storage / encrypted volume).

## Restore

Stop writers first so apps do not race the import:

```bash
docker compose stop enrichment enrichment-worker pricer pricer-worker crawler
# local `all` mode may only have enrichment + pricer (+ crawler)
```

Keep `mongodb`, `mysql`, and `rabbitmq` up.

### MongoDB restore

```bash
# Destructive for the target DB — confirm the archive path.
docker compose exec -T mongodb \
  mongorestore --db=autopulse --drop --archive --gzip \
  < "backups/mongo-autopulse-YYYYMMDDTHHMMSSZ.archive.gz"
```

### MySQL restore

```bash
gunzip -c "backups/mysql-autopulse_pricing-YYYYMMDDTHHMMSSZ.sql.gz" \
  | docker compose exec -T mysql \
      mysql \
        -u"${MYSQL_USER:-autopulse}" \
        -p"${MYSQL_PASSWORD:-autopulse}" \
        "${MYSQL_DATABASE:-autopulse_pricing}"
```

If the database is missing, create it as root first:

```bash
docker compose exec -T mysql \
  mysql -uroot -p"${MYSQL_ROOT_PASSWORD:-autopulse}" \
  -e "CREATE DATABASE IF NOT EXISTS autopulse_pricing;"
```

### After restore

1. Optionally purge stuck queues (Management UI or `rabbitmqctl purge_queue`)
   if in-flight messages reference pre-restore state.
2. Start apps again:

```bash
docker compose start enrichment pricer crawler
# prod: include enrichment-worker pricer-worker as deployed
```

3. Smoke checks:

```bash
curl -sf http://127.0.0.1:8001/health/ready
curl -sf http://127.0.0.1:8002/health/ready
# Ops: http://127.0.0.1:8001/admin — listing counts / queue cards
```

4. Spot-check one known `external_id` in Mongo and its row in
   `pricing_results`.

## Consistency notes

- Snapshot Mongo and MySQL within the same maintenance window. A car can
  exist enriched without a price (or vice versa) if dumps diverge; that is
  recoverable via re-enrich / natural reprice on new events.
- Outbox rows restored as `pending` may republish after drain starts —
  expected idempotency on consumers should absorb duplicates.
- Volume-level copies (`docker run --volumes-from` / filesystem snapshots)
  are valid DR options but not documented here; prefer logical dumps for
  portable restores across MySQL/Mongo patch levels.

## Production checklist

- [ ] Credentials from secrets, not compose defaults
- [ ] Dumps encrypted at rest / in transit off-host
- [ ] Restore drilled at least once on a non-prod stack
- [ ] Runbook owner + on-call know where latest dump lives
- [ ] Apps stopped (or traffic drained) during restore
