"""Persistência de vagas no PostgreSQL (Supabase)."""

import hashlib
import inspect
import json
import logging
import os
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from vagas.models import Vaga

log = logging.getLogger(__name__)

_ENV_PATH = Path(__file__).resolve().parents[2] / ".env"


def _load_env() -> None:
    """Load .env if DATABASE_URL is not already set."""
    if os.environ.get("DATABASE_URL"):
        return
    if _ENV_PATH.exists():
        for line in _ENV_PATH.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                os.environ.setdefault(key.strip(), val.strip())


def get_connection() -> psycopg.Connection:
    """Return a new psycopg connection from DATABASE_URL."""
    _load_env()
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL not set")
    return psycopg.connect(url, row_factory=dict_row)


def ensure_alive(conn: psycopg.Connection) -> psycopg.Connection:
    """Return conn if alive, otherwise open a fresh connection."""
    try:
        conn.execute("SELECT 1")
        return conn
    except Exception:
        log.warning("DB connection stale, reconnecting")
        try:
            conn.close()
        except Exception:
            pass
        return get_connection()


def ensure_table(conn: psycopg.Connection) -> None:
    """Create the vagas and discarded_ids tables if they don't exist."""
    conn.execute("""
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
            city            TEXT,
            state           TEXT,
            description     TEXT,
            benefits        JSONB,
            url             TEXT,
            raw_html        TEXT,
            published_at    TIMESTAMPTZ,
            first_seen_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
            crawled_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            crawler_version TEXT,
            UNIQUE (source, external_id)
        )
    """)
    # Migration: add city/state columns to existing tables
    conn.execute("""
        DO $$ BEGIN
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='vagas' AND column_name='city')
            THEN ALTER TABLE vagas ADD COLUMN city TEXT;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='vagas' AND column_name='state')
            THEN ALTER TABLE vagas ADD COLUMN state TEXT;
            END IF;
        END $$;
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS discarded_ids (
            source       TEXT NOT NULL,
            external_id  TEXT NOT NULL,
            reason       TEXT,
            discarded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (source, external_id)
        )
    """)
    conn.commit()


def crawler_version(spider) -> str:
    """Compute a version string from the spider's source file."""
    try:
        src = inspect.getfile(type(spider))
        content = Path(src).read_bytes()
        short_hash = hashlib.md5(content).hexdigest()[:8]
    except (TypeError, OSError):
        short_hash = "unknown"
    return f"{spider.name}:{short_hash}"


def load_vagas(
    conn: psycopg.Connection,
    source: str | None = None,
    missing_specialty: bool = False,
) -> list[Vaga]:
    """Load vagas from the database.

    Args:
        source: filter by source (e.g. 'indeed', 'bne')
        missing_specialty: if True, only load vagas without specialty
    """
    clauses = []
    params: dict = {}
    if source:
        clauses.append("source = %(source)s")
        params["source"] = source
    if missing_specialty:
        clauses.append("specialty IS NULL")

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = f"""
        SELECT external_id, source, title, location, company,
               salary, salary_min, salary_max, salary_period,
               job_type, specialty, city, state,
               description, url, published_at
        FROM vagas {where}
        ORDER BY id
    """

    with conn.cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()

    vagas = []
    for r in rows:
        vagas.append(Vaga(
            external_id=r["external_id"],
            source=r["source"],
            title=r["title"],
            location=r["location"],
            company=r["company"],
            salary=r["salary"],
            salary_min=r["salary_min"],
            salary_max=r["salary_max"],
            salary_period=r["salary_period"],
            job_type=r["job_type"],
            specialty=r["specialty"],
            city=r["city"],
            state=r["state"],
            description=r["description"],
            url=r["url"],
            published_at=r["published_at"],
        ))
    return vagas


def load_vagas_with_html(
    conn: psycopg.Connection,
    source: str | None = None,
) -> list[tuple[Vaga, str]]:
    """Load vagas that have raw_html stored, returning (vaga, html) pairs."""
    clauses = ["raw_html IS NOT NULL"]
    params: dict = {}
    if source:
        clauses.append("source = %(source)s")
        params["source"] = source

    where = f"WHERE {' AND '.join(clauses)}"
    sql = f"""
        SELECT external_id, source, title, location, company,
               salary, salary_min, salary_max, salary_period,
               job_type, specialty, city, state,
               description, url, published_at, raw_html
        FROM vagas {where}
        ORDER BY id
    """

    with conn.cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()

    results = []
    for r in rows:
        vaga = Vaga(
            external_id=r["external_id"],
            source=r["source"],
            title=r["title"],
            location=r["location"],
            url=r["url"],
        )
        results.append((vaga, r["raw_html"]))
    return results


def get_known_ids(conn: psycopg.Connection, source: str) -> set[str]:
    """Return external_ids that already have detail data (description)."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT external_id FROM vagas WHERE source = %(src)s AND description IS NOT NULL",
            {"src": source},
        )
        return {r["external_id"] for r in cur.fetchall()}


def get_all_ids(conn: psycopg.Connection, source: str) -> set[str]:
    """Return all external_ids for a source."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT external_id FROM vagas WHERE source = %(src)s AND external_id IS NOT NULL",
            {"src": source},
        )
        return {r["external_id"] for r in cur.fetchall()}


def save_discarded_ids(
    conn: psycopg.Connection,
    source: str,
    ids: list[tuple[str, str]],
) -> None:
    """Batch-insert discarded external_ids. Each tuple is (external_id, reason).

    Uses ON CONFLICT DO NOTHING so re-discarding the same ID is a no-op.
    """
    if not ids:
        return
    with conn.cursor() as cur:
        cur.executemany(
            """INSERT INTO discarded_ids (source, external_id, reason)
               VALUES (%(src)s, %(eid)s, %(reason)s)
               ON CONFLICT DO NOTHING""",
            [{"src": source, "eid": eid, "reason": reason} for eid, reason in ids],
        )
    conn.commit()


def get_all_known_ids(conn: psycopg.Connection, source: str) -> set[str]:
    """Return external_ids from both vagas and discarded_ids for a source."""
    with conn.cursor() as cur:
        cur.execute(
            """SELECT external_id FROM vagas
               WHERE source = %(src)s AND external_id IS NOT NULL
                 AND raw_html IS NOT NULL
               UNION
               SELECT external_id FROM discarded_ids
               WHERE source = %(src)s""",
            {"src": source},
        )
        return {r["external_id"] for r in cur.fetchall()}



def update_specialty(
    conn: psycopg.Connection,
    source: str,
    external_id: str,
    specialty: str,
) -> None:
    """Update the specialty of a single vaga."""
    conn.execute(
        "UPDATE vagas SET specialty = %(spec)s WHERE source = %(src)s AND external_id = %(eid)s",
        {"spec": specialty, "src": source, "eid": external_id},
    )


def delete_vagas(
    conn: psycopg.Connection,
    source: str,
    external_ids: list[str],
) -> int:
    """Delete vagas by source and external_id. Returns count deleted."""
    if not external_ids:
        return 0
    # Filter out None ids
    ids = [eid for eid in external_ids if eid is not None]
    if not ids:
        return 0
    with conn.cursor() as cur:
        cur.execute(
            "DELETE FROM vagas WHERE source = %(src)s AND external_id = ANY(%(ids)s)",
            {"src": source, "ids": ids},
        )
        return cur.rowcount


def deduplicate_vagas(conn: psycopg.Connection) -> int:
    """Remove duplicate vagas keeping the most recent (highest id) per group.

    Duplicates are identified by matching (source, external_id). The UNIQUE
    constraint already prevents these, so this is a safety net only.
    """
    with conn.cursor() as cur:
        cur.execute("""
            DELETE FROM vagas
            WHERE id NOT IN (
                SELECT MAX(id)
                FROM vagas
                GROUP BY source, external_id
            )
        """)
        count = cur.rowcount
    if count:
        conn.commit()
        log.info("Deduplicated: removed %d duplicate vagas", count)
    return count


def upsert_vagas(
    conn: psycopg.Connection,
    vagas: list[Vaga],
    version: str,
) -> tuple[int, int]:
    """Batch upsert vagas. Returns (inserted, updated) counts.

    Only performs an UPDATE when at least one data field actually changed
    (new value differs or fills a previously NULL field). Unchanged rows
    are skipped — crawled_at is NOT bumped for no-op rows.
    """
    if not vagas:
        return 0, 0

    sql = """
        INSERT INTO vagas (
            external_id, source, title, location, company,
            salary, salary_min, salary_max, salary_period,
            job_type, specialty, city, state,
            description, benefits,
            url, raw_html, published_at,
            first_seen_at, crawled_at, crawler_version
        ) VALUES (
            %(external_id)s, %(source)s, %(title)s, %(location)s, %(company)s,
            %(salary)s, %(salary_min)s, %(salary_max)s, %(salary_period)s,
            %(job_type)s, %(specialty)s, %(city)s, %(state)s,
            %(description)s, %(benefits)s,
            %(url)s, %(raw_html)s, %(published_at)s,
            now(), now(), %(crawler_version)s
        )
        ON CONFLICT (source, external_id) DO UPDATE SET
            title           = EXCLUDED.title,
            location        = EXCLUDED.location,
            company         = COALESCE(EXCLUDED.company, vagas.company),
            salary          = COALESCE(EXCLUDED.salary, vagas.salary),
            salary_min      = COALESCE(EXCLUDED.salary_min, vagas.salary_min),
            salary_max      = COALESCE(EXCLUDED.salary_max, vagas.salary_max),
            salary_period   = COALESCE(EXCLUDED.salary_period, vagas.salary_period),
            job_type        = COALESCE(EXCLUDED.job_type, vagas.job_type),
            specialty       = COALESCE(EXCLUDED.specialty, vagas.specialty),
            city            = COALESCE(EXCLUDED.city, vagas.city),
            state           = COALESCE(EXCLUDED.state, vagas.state),
            description     = COALESCE(EXCLUDED.description, vagas.description),
            benefits        = COALESCE(EXCLUDED.benefits, vagas.benefits),
            url             = EXCLUDED.url,
            raw_html        = COALESCE(EXCLUDED.raw_html, vagas.raw_html),
            published_at    = COALESCE(EXCLUDED.published_at, vagas.published_at),
            crawled_at      = now(),
            crawler_version = EXCLUDED.crawler_version
        WHERE
            vagas.title           IS DISTINCT FROM EXCLUDED.title
            OR vagas.location     IS DISTINCT FROM EXCLUDED.location
            OR vagas.company      IS DISTINCT FROM COALESCE(EXCLUDED.company, vagas.company)
            OR vagas.salary       IS DISTINCT FROM COALESCE(EXCLUDED.salary, vagas.salary)
            OR vagas.salary_min   IS DISTINCT FROM COALESCE(EXCLUDED.salary_min, vagas.salary_min)
            OR vagas.salary_max   IS DISTINCT FROM COALESCE(EXCLUDED.salary_max, vagas.salary_max)
            OR vagas.salary_period IS DISTINCT FROM COALESCE(EXCLUDED.salary_period, vagas.salary_period)
            OR vagas.job_type     IS DISTINCT FROM COALESCE(EXCLUDED.job_type, vagas.job_type)
            OR vagas.specialty    IS DISTINCT FROM COALESCE(EXCLUDED.specialty, vagas.specialty)
            OR vagas.city         IS DISTINCT FROM COALESCE(EXCLUDED.city, vagas.city)
            OR vagas.state        IS DISTINCT FROM COALESCE(EXCLUDED.state, vagas.state)
            OR vagas.description  IS DISTINCT FROM COALESCE(EXCLUDED.description, vagas.description)
            OR vagas.benefits     IS DISTINCT FROM COALESCE(EXCLUDED.benefits, vagas.benefits)
            OR vagas.url          IS DISTINCT FROM EXCLUDED.url
            OR vagas.raw_html     IS DISTINCT FROM COALESCE(EXCLUDED.raw_html, vagas.raw_html)
            OR vagas.published_at IS DISTINCT FROM COALESCE(EXCLUDED.published_at, vagas.published_at)
        RETURNING (xmax = 0) AS is_insert
    """

    inserted = 0
    updated = 0

    with conn.cursor() as cur:
        for vaga in vagas:
            params = {
                "external_id": vaga.external_id or vaga.dedup_key()[:12],
                "source": vaga.source,
                "title": vaga.title,
                "location": vaga.location,
                "company": vaga.company,
                "salary": vaga.salary,
                "salary_min": vaga.salary_min,
                "salary_max": vaga.salary_max,
                "salary_period": vaga.salary_period,
                "job_type": vaga.job_type,
                "specialty": vaga.specialty,
                "city": vaga.city,
                "state": vaga.state,
                "description": vaga.description,
                "benefits": json.dumps(vaga.benefits) if vaga.benefits else None,
                "url": vaga.url,
                "raw_html": vaga.raw_html,
                "published_at": vaga.published_at,
                "crawler_version": version,
            }
            cur.execute(sql, params)
            row = cur.fetchone()
            if row is None:
                pass  # skip — row exists, nothing changed
            elif row["is_insert"]:
                inserted += 1
            else:
                updated += 1

        conn.commit()

    return inserted, updated
