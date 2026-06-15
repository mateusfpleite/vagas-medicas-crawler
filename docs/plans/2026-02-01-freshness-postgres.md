# Freshness + Postgres Storage Design

**Goal:** Migrate from filesystem JSON to Postgres (Supabase) and implement vacancy freshness tracking via `published_at` + `first_seen_at` diff heuristic.

**Architecture:** Single `vagas` table with `ON CONFLICT` upsert. Freshness uses `COALESCE(published_at, first_seen_at)` as effective date. Crawler version hash detects when spider code changes, reducing confidence in `first_seen_at` for new captures.

---

## Schema

```sql
CREATE TABLE IF NOT EXISTS vagas (
    id              SERIAL PRIMARY KEY,
    external_id     TEXT,
    source          TEXT NOT NULL,
    title           TEXT NOT NULL,
    location        TEXT,
    company         TEXT,
    salary          TEXT,
    salary_min      NUMERIC,
    salary_max      NUMERIC,
    salary_period   TEXT,
    job_type        TEXT,
    specialty       TEXT,
    description     TEXT,
    benefits        JSONB,
    url             TEXT,
    raw_html        TEXT,
    published_at    TIMESTAMPTZ,
    first_seen_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    crawled_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    crawler_version TEXT,
    UNIQUE (source, external_id)
);
```

## Upsert logic

```sql
INSERT INTO vagas (external_id, source, title, ..., first_seen_at, crawled_at, crawler_version)
VALUES (%s, %s, %s, ..., now(), now(), %s)
ON CONFLICT (source, external_id) DO UPDATE SET
    title = EXCLUDED.title,
    location = EXCLUDED.location,
    ...,
    crawled_at = now(),
    crawler_version = EXCLUDED.crawler_version
    -- first_seen_at is NOT updated (preserved from original INSERT)
;
```

## Freshness model

Two sources of truth, in priority order:

1. **`published_at`** -- date from the source (Indeed epoch ms, Vagas.com HTML). When available, this is ground truth.
2. **`first_seen_at`** -- first time our crawler saw this `external_id`. Reliable proxy when source doesn't provide date, under the assumption that crawler code hasn't changed.

Effective date for filtering/sorting:
```sql
COALESCE(published_at, first_seen_at)
```

## Crawler versioning

Each spider has a `crawler_version` computed as `{spider.name}:{hash}` where hash is derived from the spider's source file. Saved on every upsert.

If `first_seen_at` was recorded with a different `crawler_version` than the current one, it has lower confidence -- the vacancy may be old but newly captured due to spider changes.

## CLI flow

```
crawl -> normalize specialties -> batch upsert (postgres)
```

Connection string from `DATABASE_URL` environment variable.

## Migration

Script reads existing `data/{source}/*.json` and `*.html` files, sets `first_seen_at = crawled_at`, and inserts into Postgres. Filesystem becomes obsolete after migration.

## What's excluded

- No ORM (psycopg direct)
- No migrations framework (single table, CREATE TABLE in code)
- No extra indices beyond UNIQUE constraint (volume is small)
- No API/frontend (queries via psql or scripts)
