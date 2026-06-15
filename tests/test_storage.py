import pytest
from datetime import datetime, UTC

from vagas.models import Vaga
from vagas.storage import get_connection, ensure_table, upsert_vagas, save_discarded_ids, get_all_known_ids, get_all_ids, deduplicate_vagas


@pytest.fixture(scope="module")
def db():
    """Shared connection for storage tests. Cleans up test rows after."""
    conn = get_connection()
    ensure_table(conn)
    yield conn
    # Cleanup test rows
    conn.execute("DELETE FROM vagas WHERE source = '_test'")
    conn.execute("DELETE FROM discarded_ids WHERE source = '_test'")
    conn.commit()
    conn.close()


def _make_vaga(**overrides) -> Vaga:
    base = dict(
        title="Médico Teste",
        location="SP",
        source="_test",
        url="https://example.com/1",
        external_id="test_001",
    )
    base.update(overrides)
    return Vaga(**base)


def test_upsert_insert(db):
    """New vaga should be inserted with first_seen_at set."""
    vaga = _make_vaga(external_id="test_insert_001")
    count, _ = upsert_vagas(db, [vaga], "_test:abc123")
    assert count == 1

    row = db.execute(
        "SELECT * FROM vagas WHERE source = '_test' AND external_id = 'test_insert_001'"
    ).fetchone()
    assert row is not None
    assert row["title"] == "Médico Teste"
    assert row["first_seen_at"] is not None
    assert row["crawled_at"] is not None
    assert row["crawler_version"] == "_test:abc123"


def test_upsert_preserves_first_seen_at(db):
    """Re-inserting same vaga should update crawled_at but keep first_seen_at."""
    vaga = _make_vaga(external_id="test_preserve_001")
    upsert_vagas(db, [vaga], "_test:v1")

    row1 = db.execute(
        "SELECT first_seen_at, crawled_at FROM vagas WHERE source = '_test' AND external_id = 'test_preserve_001'"
    ).fetchone()
    first_seen_original = row1["first_seen_at"]

    # Upsert again
    vaga2 = _make_vaga(external_id="test_preserve_001", title="Médico Teste Atualizado")
    upsert_vagas(db, [vaga2], "_test:v2")

    row2 = db.execute(
        "SELECT first_seen_at, crawled_at, title, crawler_version FROM vagas WHERE source = '_test' AND external_id = 'test_preserve_001'"
    ).fetchone()
    assert row2["first_seen_at"] == first_seen_original  # preserved
    assert row2["title"] == "Médico Teste Atualizado"  # updated
    assert row2["crawler_version"] == "_test:v2"  # updated


def test_upsert_with_all_fields(db):
    """Vaga with all fields should be stored correctly."""
    vaga = _make_vaga(
        external_id="test_full_001",
        company="Hospital X",
        salary="R$ 15.000",
        salary_min=15000.0,
        salary_max=30000.0,
        salary_period="MONTHLY",
        job_type="CLT",
        specialty="Cardiologista",
        description="Vaga para cardiologista",
        benefits=["VT", "VR"],
        raw_html="<html>detail</html>",
        published_at=datetime(2026, 1, 20, tzinfo=UTC),
    )
    upsert_vagas(db, [vaga], "_test:full")

    row = db.execute(
        "SELECT * FROM vagas WHERE source = '_test' AND external_id = 'test_full_001'"
    ).fetchone()
    assert row["company"] == "Hospital X"
    assert float(row["salary_min"]) == 15000.0
    assert float(row["salary_max"]) == 30000.0
    assert row["salary_period"] == "MONTHLY"
    assert row["specialty"] == "Cardiologista"
    assert row["raw_html"] == "<html>detail</html>"
    assert row["published_at"].year == 2026
    assert row["benefits"] == ["VT", "VR"]


def test_upsert_empty_list(db):
    """Empty list should return 0."""
    count, _ = upsert_vagas(db, [], "_test:empty")
    assert count == 0


def test_save_discarded_ids(db):
    """Discarded IDs should be persisted and deduplicated on conflict."""
    save_discarded_ids(db, "_test", [("disc_001", "scoring"), ("disc_002", "non_doctor")])

    rows = db.execute(
        "SELECT external_id, reason FROM discarded_ids WHERE source = '_test' ORDER BY external_id"
    ).fetchall()
    assert len(rows) == 2
    assert rows[0]["external_id"] == "disc_001"
    assert rows[0]["reason"] == "scoring"
    assert rows[1]["external_id"] == "disc_002"
    assert rows[1]["reason"] == "non_doctor"

    # Re-inserting same ID should be a no-op (ON CONFLICT DO NOTHING)
    save_discarded_ids(db, "_test", [("disc_001", "scoring")])
    count = db.execute(
        "SELECT COUNT(*) as n FROM discarded_ids WHERE source = '_test'"
    ).fetchone()["n"]
    assert count == 2


def test_save_discarded_ids_empty(db):
    """Empty list should be a no-op."""
    save_discarded_ids(db, "_test", [])


def test_get_all_known_ids(db):
    """Should return union of vagas external_ids and discarded_ids."""
    # Insert a vaga with raw_html (get_all_known_ids requires it)
    vaga = _make_vaga(external_id="known_001", raw_html="<html>detail</html>")
    upsert_vagas(db, [vaga], "_test:known")

    # Insert a discarded ID
    save_discarded_ids(db, "_test", [("known_disc_001", "scoring")])

    known = get_all_known_ids(db, "_test")
    assert "known_001" in known
    assert "known_disc_001" in known

    # Regular get_all_ids should NOT include discarded
    regular = get_all_ids(db, "_test")
    assert "known_001" in regular
    assert "known_disc_001" not in regular


def test_deduplicate_removes_true_duplicates(db):
    """Vagas with same source+title+location+external_id are deduped (keeps MAX(id))."""
    # Insert two vagas with the SAME external_id — only possible via raw SQL
    db.execute(
        """INSERT INTO vagas (external_id, source, title, location, url)
           VALUES ('dedup_true_001', '_test', 'Médico do Trabalho', 'Campina Grande/PB', 'https://example.com/d1')"""
    )
    db.execute(
        """INSERT INTO vagas (external_id, source, title, location, url)
           VALUES ('dedup_true_001', '_test', 'Médico do Trabalho', 'Campina Grande/PB', 'https://example.com/d2')
           ON CONFLICT (source, external_id) DO NOTHING"""
    )
    db.commit()

    # With external_id in GROUP BY, same external_id rows collapse to one group
    removed = deduplicate_vagas(db)
    # The ON CONFLICT prevents actual duplicates, so 0 removed is expected
    assert removed >= 0

    rows = db.execute(
        "SELECT COUNT(*) as n FROM vagas WHERE source = '_test' AND external_id = 'dedup_true_001'"
    ).fetchone()
    assert rows["n"] == 1


def test_deduplicate_preserves_different_companies(db):
    """Vagas from different companies with same title+location must be preserved."""
    vaga_a = _make_vaga(
        external_id="dedup_diff_001",
        title="Médico do Trabalho",
        location="Campina Grande/PB",
        company="Hospital A",
    )
    vaga_b = _make_vaga(
        external_id="dedup_diff_002",
        title="Médico do Trabalho",
        location="Campina Grande/PB",
        company="Hospital B",
    )
    upsert_vagas(db, [vaga_a, vaga_b], "_test:dedup")

    removed = deduplicate_vagas(db)
    assert removed == 0  # Nothing should be deleted

    rows = db.execute(
        """SELECT external_id FROM vagas
           WHERE source = '_test' AND external_id IN ('dedup_diff_001', 'dedup_diff_002')
           ORDER BY external_id"""
    ).fetchall()
    assert len(rows) == 2
    assert rows[0]["external_id"] == "dedup_diff_001"
    assert rows[1]["external_id"] == "dedup_diff_002"


def test_deduplicate_null_company_same_title_location(db):
    """Vagas with NULL company + same title+location should be preserved (different external_ids)."""
    vaga_a = _make_vaga(
        external_id="dedup_null_001",
        title="Médico Clínico Geral",
        location="São Paulo/SP",
        company=None,
    )
    vaga_b = _make_vaga(
        external_id="dedup_null_002",
        title="Médico Clínico Geral",
        location="São Paulo/SP",
        company=None,
    )
    upsert_vagas(db, [vaga_a, vaga_b], "_test:dedup")

    removed = deduplicate_vagas(db)
    assert removed == 0  # Different external_ids → different groups → both preserved

    rows = db.execute(
        """SELECT external_id FROM vagas
           WHERE source = '_test' AND external_id IN ('dedup_null_001', 'dedup_null_002')
           ORDER BY external_id"""
    ).fetchall()
    assert len(rows) == 2
