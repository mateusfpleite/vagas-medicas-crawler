import os
import pytest
from vagas.models import Vaga
from vagas.db import VagaDB

pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"),
    reason="DATABASE_URL not set",
)


@pytest.fixture
async def db():
    database = VagaDB(os.environ["DATABASE_URL"])
    await database.connect()
    await database.setup_tables()
    yield database
    await database.execute("DELETE FROM vagas WHERE source = 'test'")
    await database.close()


async def test_insert_and_fetch(db):
    vaga = Vaga(
        title="Médico Teste",
        location="Test City - TS",
        source="test",
        url="https://test.com/1",
    )
    inserted = await db.upsert_vaga(vaga)
    assert inserted is True

    vagas = await db.list_vagas(source="test")
    assert len(vagas) == 1
    assert vagas[0]["title"] == "Médico Teste"


async def test_upsert_dedup(db):
    vaga = Vaga(
        title="Médico Teste",
        location="Test City - TS",
        source="test",
        url="https://test.com/1",
    )
    first = await db.upsert_vaga(vaga)
    second = await db.upsert_vaga(vaga)
    assert first is True
    assert second is False

    vagas = await db.list_vagas(source="test")
    assert len(vagas) == 1
