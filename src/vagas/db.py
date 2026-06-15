import psycopg
import psycopg.rows
from vagas.models import Vaga

CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS vagas (
    id SERIAL PRIMARY KEY,
    dedup_key TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    company TEXT,
    location TEXT NOT NULL,
    salary TEXT,
    job_type TEXT,
    specialty TEXT,
    source TEXT NOT NULL,
    url TEXT NOT NULL,
    external_id TEXT,
    description TEXT,
    crawled_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""

CREATE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_vagas_source ON vagas(source);",
    "CREATE INDEX IF NOT EXISTS idx_vagas_location ON vagas(location);",
]


class VagaDB:
    def __init__(self, dsn: str):
        self.dsn = dsn
        self.conn: psycopg.AsyncConnection | None = None

    async def connect(self):
        self.conn = await psycopg.AsyncConnection.connect(self.dsn)

    async def close(self):
        if self.conn:
            await self.conn.close()

    async def setup_tables(self):
        async with self.conn.cursor() as cur:
            await cur.execute(CREATE_TABLE)
            for idx_sql in CREATE_INDEXES:
                await cur.execute(idx_sql)
        await self.conn.commit()

    async def execute(self, query: str):
        async with self.conn.cursor() as cur:
            await cur.execute(query)
        await self.conn.commit()

    async def upsert_vaga(self, vaga: Vaga) -> bool:
        async with self.conn.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO vagas (dedup_key, title, company, location, salary,
                    job_type, specialty, source, url, external_id, description, crawled_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (dedup_key) DO NOTHING
                RETURNING id
                """,
                (
                    vaga.dedup_key(), vaga.title, vaga.company, vaga.location,
                    vaga.salary, vaga.job_type, vaga.specialty, vaga.source,
                    vaga.url, vaga.external_id, vaga.description, vaga.crawled_at,
                ),
            )
            result = await cur.fetchone()
        await self.conn.commit()
        return result is not None

    async def list_vagas(self, source: str | None = None) -> list[dict]:
        query = "SELECT * FROM vagas"
        params: list = []
        if source:
            query += " WHERE source = %s"
            params.append(source)
        async with self.conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            await cur.execute(query, params)
            return await cur.fetchall()
