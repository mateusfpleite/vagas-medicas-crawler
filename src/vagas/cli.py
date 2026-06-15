# src/vagas/cli.py
import argparse
import asyncio
import logging

from vagas.location import normalize_location, fetch_ibge_data
from vagas.normalize import normalize_specialty
from vagas.filters import is_medical_title
from vagas.scoring import medical_score, FULL_THRESHOLD
from vagas.storage import get_connection, ensure_alive, ensure_table, upsert_vagas, crawler_version, load_vagas, update_specialty, get_all_known_ids, save_discarded_ids, delete_vagas, deduplicate_vagas
from vagas.spiders.bne import BNESpider
from vagas.spiders.indeed import IndeedSpider
from vagas.spiders.infojobs import InfoJobsSpider
from vagas.spiders.vagas_com import VagasComSpider
from vagas.spiders.pci import PCISpider
from vagas.spiders.gupy import GupySpider

log = logging.getLogger("vagas.cli")

ALL_SPIDERS = [IndeedSpider, VagasComSpider, BNESpider, InfoJobsSpider, PCISpider, GupySpider]


async def run(
    spider_names: list[str] | None = None,
    dry_run: bool = False,
    enrich: bool = False,
    locations: list[str] | None = None,
):
    spiders = ALL_SPIDERS
    if spider_names:
        spiders = [s for s in ALL_SPIDERS if s.name in spider_names]

    if not spiders:
        log.error("No spiders matched. Available: %s", [s.name for s in ALL_SPIDERS])
        return

    conn = None
    if not dry_run:
        conn = get_connection()
        ensure_table(conn)

    total_inserted = 0
    total_updated = 0
    total_enriched = 0
    total_non_doctor = 0
    proxy_activated = []

    for spider_cls in spiders:
        spider = spider_cls()
        log.info("[%s] Crawling...", spider.name)
        try:
            # Reconnect if DB went stale (e.g. previous spider failed mid-upsert)
            if conn:
                conn = ensure_alive(conn)

            # All known IDs (vagas + discarded) — skip detail fetches AND re-processing
            existing = get_all_known_ids(conn, spider.name) if conn else set()
            vagas = await spider.crawl(known_ids=existing, locations=locations)
            log.info("[%s] Found %d vagas", spider.name, len(vagas))

            # Skip vagas already in DB (immutable — no need to re-process)
            if existing:
                before_skip = len(vagas)
                vagas = [v for v in vagas if (v.external_id or v.dedup_key()[:12]) not in existing]
                if before_skip != len(vagas):
                    log.info("[%s] Skipped %d existing vagas, %d new to process",
                             spider.name, before_skip - len(vagas), len(vagas))

            if not vagas:
                log.info("[%s] No new vagas", spider.name)
                continue

            # Reconnect if DB went stale during long crawl
            if conn:
                conn = ensure_alive(conn)

            # Post-detail scoring filter (uses title + description)
            before_scoring = len(vagas)
            scoring_discarded = [
                v for v in vagas
                if not is_medical_title(v.title)
                or medical_score(v.title, v.description) < FULL_THRESHOLD
            ]
            if scoring_discarded:
                scoring_ids = {id(v) for v in scoring_discarded}
                vagas = [v for v in vagas if id(v) not in scoring_ids]
                log.info(
                    "[%s] Scoring filter: %d -> %d vagas",
                    spider.name, before_scoring, len(vagas),
                )
                if conn:
                    save_discarded_ids(conn, spider.name, [
                        (v.external_id or v.dedup_key()[:12], "scoring")
                        for v in scoring_discarded
                    ])

            # Normalize specialties and locations in-place
            for v in vagas:
                v.specialty = normalize_specialty(v.specialty)
                v.city, v.state = normalize_location(v.location)

            # AI enrichment (optional — only for vagas missing specialty)
            if enrich:
                from vagas.enrich import enrich_vagas

                need_enrich = [v for v in vagas if not v.specialty]
                if need_enrich:
                    enriched, non_doc, non_doctor_vagas = enrich_vagas(need_enrich)
                    total_enriched += enriched
                    total_non_doctor += non_doc
                    # Reconnect if DB went stale during enrichment
                    if conn:
                        conn = ensure_alive(conn)
                    # Remove non-doctors before upsert
                    non_doctor_set = {id(v) for v in non_doctor_vagas}
                    vagas = [v for v in vagas if id(v) not in non_doctor_set]
                    if conn and non_doctor_vagas:
                        save_discarded_ids(conn, spider.name, [
                            (v.external_id or v.dedup_key()[:12], "non_doctor")
                            for v in non_doctor_vagas
                        ])
                    log.info(
                        "[%s] AI enrichment: %d need enrich, %d specialties, %d non-doctor",
                        spider.name, len(need_enrich), enriched, non_doc,
                    )
                else:
                    log.info("[%s] AI enrichment: all %d vagas already have specialty, skipping",
                             spider.name, len(vagas))

            if dry_run:
                for v in vagas[:5]:
                    has_html = "+" if v.raw_html else "-"
                    spec = v.specialty or "?"
                    loc = f"{v.city}/{v.state}" if v.city else v.location or "?"
                    print(f"  [{has_html}] {v.title} | {spec} | {loc} | {v.url}")
                if len(vagas) > 5:
                    print(f"  ... and {len(vagas) - 5} more")
            else:
                version = crawler_version(spider)
                ins, upd = upsert_vagas(conn, vagas, version)
                skipped = len(vagas) - ins - upd
                total_inserted += ins
                total_updated += upd
                log.info("[%s] %d new, %d updated, %d unchanged (version: %s)",
                         spider.name, ins, upd, skipped, version)

        except Exception:
            log.exception("[%s] Failed", spider.name)
        finally:
            if spider._proxy_active and spider.name not in proxy_activated:
                proxy_activated.append(spider.name)

    if proxy_activated:
        log.info("Proxy activated for: %s", ", ".join(proxy_activated))

    if conn:
        conn = ensure_alive(conn)
        if not dry_run:
            deduped = deduplicate_vagas(conn)
            log.info("Done. %d new, %d updated, %d duplicates removed", total_inserted, total_updated, deduped)
            if enrich:
                log.info("AI enrichment: %d specialties added, %d non-doctor flagged",
                         total_enriched, total_non_doctor)
        conn.close()


def enrich_only(source: str | None = None):
    """Enrich vagas already in the database (no crawling)."""
    from vagas.enrich import enrich_vagas

    conn = get_connection()
    ensure_table(conn)

    vagas = load_vagas(conn, source=source, missing_specialty=True)
    log.info("Loaded %d vagas without specialty%s",
             len(vagas), f" (source={source})" if source else "")

    if not vagas:
        log.info("Nothing to enrich")
        conn.close()
        return

    enriched, non_doc, non_doctor_vagas = enrich_vagas(vagas)
    log.info("AI enrichment: %d specialties, %d non-doctor flagged", enriched, non_doc)

    # Write back specialties (normalize AI output)
    updated = 0
    for v in vagas:
        if v.specialty:
            v.specialty = normalize_specialty(v.specialty) or v.specialty
            update_specialty(conn, v.source, v.external_id, v.specialty)
            updated += 1

    # Persist discarded IDs, then delete non-doctor vagas
    by_source: dict[str, list[tuple[str, str]]] = {}
    for v in non_doctor_vagas:
        eid = v.external_id or v.dedup_key()[:12]
        by_source.setdefault(v.source, []).append((eid, "non_doctor"))
    for src, discard_ids in by_source.items():
        save_discarded_ids(conn, src, discard_ids)

    deleted = 0
    delete_by_source: dict[str, list[str]] = {}
    for v in non_doctor_vagas:
        if v.external_id:
            delete_by_source.setdefault(v.source, []).append(v.external_id)
    for src, ids in delete_by_source.items():
        deleted += delete_vagas(conn, src, ids)

    conn.commit()
    log.info("Updated %d, deleted %d non-doctor vagas", updated, deleted)
    conn.close()


def normalize_locations_only(source: str | None = None):
    """Backfill city/state for existing vagas in the database."""
    conn = get_connection()
    ensure_table(conn)

    clauses = ["location IS NOT NULL", "city IS NULL"]
    params: dict = {}
    if source:
        clauses.append("source = %(source)s")
        params["source"] = source

    where = " AND ".join(clauses)
    with conn.cursor() as cur:
        cur.execute(f"SELECT id, location FROM vagas WHERE {where}", params)
        rows = cur.fetchall()

    log.info("Found %d vagas to normalize%s", len(rows), f" (source={source})" if source else "")

    updated = 0
    for row in rows:
        city, state = normalize_location(row["location"])
        if city:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE vagas SET city = %(city)s, state = %(state)s WHERE id = %(id)s",
                    {"city": city, "state": state, "id": row["id"]},
                )
            updated += 1

    conn.commit()
    log.info("Updated %d vagas with city/state", updated)
    conn.close()


def deduplicate_only():
    """Remove duplicate vagas from the database."""
    conn = get_connection()
    ensure_table(conn)
    removed = deduplicate_vagas(conn)
    log.info("Deduplication complete: %d duplicates removed", removed)
    conn.close()


def show_stats():
    """Show database statistics."""
    conn = get_connection()
    ensure_table(conn)

    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) as total FROM vagas")
        total = cur.fetchone()["total"]

        if total == 0:
            print("Nenhuma vaga no banco.")
            conn.close()
            return

        # By source
        cur.execute("SELECT source, COUNT(*) as n FROM vagas GROUP BY source ORDER BY n DESC")
        by_source = cur.fetchall()

        # Missing data
        cur.execute("""
            SELECT
                COUNT(*) FILTER (WHERE description IS NULL) as sem_descricao,
                COUNT(*) FILTER (WHERE company IS NULL) as sem_empresa,
                COUNT(*) FILTER (WHERE specialty IS NULL) as sem_especialidade,
                COUNT(*) FILTER (WHERE city IS NULL) as sem_cidade,
                COUNT(*) FILTER (WHERE salary IS NULL AND salary_min IS NULL) as sem_salario,
                COUNT(*) FILTER (WHERE published_at IS NULL) as sem_data_pub
            FROM vagas
        """)
        missing = cur.fetchone()

        # Top specialties
        cur.execute("""
            SELECT specialty, COUNT(*) as n
            FROM vagas WHERE specialty IS NOT NULL
            GROUP BY specialty ORDER BY n DESC LIMIT 10
        """)
        top_specialties = cur.fetchall()

        # Top cities
        cur.execute("""
            SELECT city, state, COUNT(*) as n
            FROM vagas WHERE city IS NOT NULL
            GROUP BY city, state ORDER BY n DESC LIMIT 10
        """)
        top_cities = cur.fetchall()

        # Recent activity
        cur.execute("""
            SELECT
                COUNT(*) FILTER (WHERE crawled_at >= NOW() - INTERVAL '24 hours') as last_24h,
                COUNT(*) FILTER (WHERE crawled_at >= NOW() - INTERVAL '7 days') as last_7d
            FROM vagas
        """)
        activity = cur.fetchone()

        # Age distribution (based on published_at)
        cur.execute("""
            SELECT
                COUNT(*) FILTER (WHERE published_at >= NOW() - INTERVAL '7 days') as last_7d,
                COUNT(*) FILTER (WHERE published_at >= NOW() - INTERVAL '30 days'
                                   AND published_at < NOW() - INTERVAL '7 days') as last_30d,
                COUNT(*) FILTER (WHERE published_at >= NOW() - INTERVAL '90 days'
                                   AND published_at < NOW() - INTERVAL '30 days') as last_90d,
                COUNT(*) FILTER (WHERE published_at < NOW() - INTERVAL '90 days') as older,
                COUNT(*) FILTER (WHERE published_at IS NULL) as sem_data
            FROM vagas
        """)
        age = cur.fetchone()

    conn.close()

    # --- Output ---
    print(f"\n  Total de vagas: {total}")
    print()

    print("  Por fonte:")
    for r in by_source:
        pct = r["n"] / total * 100
        print(f"    {r['source']:12s} {r['n']:>5d}  ({pct:.1f}%)")
    print()

    print("  Dados faltantes:")
    labels = {
        "sem_descricao": "Descrição",
        "sem_empresa": "Empresa",
        "sem_especialidade": "Especialidade",
        "sem_cidade": "Cidade",
        "sem_salario": "Salário",
        "sem_data_pub": "Data publicação",
    }
    for key, label in labels.items():
        v = missing[key]
        pct = v / total * 100
        print(f"    {label:17s} {v:>5d}  ({pct:.1f}%)")
    print()

    if top_specialties:
        print("  Top especialidades:")
        for r in top_specialties:
            print(f"    {r['specialty']:30s} {r['n']:>4d}")
        print()

    if top_cities:
        print("  Top cidades:")
        for r in top_cities:
            loc = f"{r['city']}/{r['state']}" if r["state"] else r["city"]
            print(f"    {loc:30s} {r['n']:>4d}")
        print()

    print("  Idade das vagas (por data de publicação):")
    age_labels = [
        ("last_7d", "Última semana"),
        ("last_30d", "1-4 semanas"),
        ("last_90d", "1-3 meses"),
        ("older", "> 3 meses"),
        ("sem_data", "Sem data"),
    ]
    for key, label in age_labels:
        v = age[key]
        pct = v / total * 100
        print(f"    {label:17s} {v:>5d}  ({pct:.1f}%)")
    print()

    print(f"  Atividade: {activity['last_24h']} vagas nas últimas 24h, {activity['last_7d']} nos últimos 7 dias")
    print()


def reparse_vagas():
    """Re-run BNE parse_detail on vagas that have stored raw_html."""
    from vagas.spiders.bne import BNESpider
    from vagas.storage import load_vagas_with_html

    conn = get_connection()
    ensure_table(conn)

    # Only BNE has parse_detail; hardcode source to avoid misuse
    pairs = load_vagas_with_html(conn, source="bne")
    log.info("Loaded %d BNE vagas with raw_html to reparse", len(pairs))

    if not pairs:
        conn.close()
        return

    spider = BNESpider()
    reparsed = []
    for vaga, html in pairs:
        spider.parse_detail(html, vaga)
        vaga.specialty = normalize_specialty(vaga.specialty)
        vaga.city, vaga.state = normalize_location(vaga.location)
        reparsed.append(vaga)

    version = crawler_version(spider)
    ins, upd = upsert_vagas(conn, reparsed, version)
    log.info("Reparse done: %d inserted, %d updated, %d unchanged",
             ins, upd, len(reparsed) - ins - upd)
    conn.close()


def main():
    parser = argparse.ArgumentParser(description="Crawler de vagas médicas")
    parser.add_argument("spiders", nargs="*", help="Spiders to run (default: all)")
    parser.add_argument("--dry-run", action="store_true", help="Print vagas without saving")
    parser.add_argument("--enrich", action="store_true", help="Use AI to enrich vagas (requires GEMINI_API_KEY)")
    parser.add_argument("--enrich-only", action="store_true", help="Enrich existing vagas in DB (no crawling)")
    parser.add_argument("--deduplicate", action="store_true", help="Remove duplicate vagas from DB")
    parser.add_argument("--fetch-ibge", action="store_true", help="Refresh IBGE municipalities cache")
    parser.add_argument("--normalize-locations", action="store_true", help="Backfill city/state for existing vagas")
    parser.add_argument("--stats", action="store_true", help="Show database statistics")
    parser.add_argument("--location", action="append", dest="locations",
                        help="Target specific locations (can be repeated, e.g. --location 'Rio de Janeiro, RJ')")
    parser.add_argument("--reparse", action="store_true",
                        help="Re-parse BNE vagas from stored raw_html (improves extraction)")
    parser.add_argument("--source", help="Filter source for --enrich-only/--normalize-locations")
    parser.add_argument("--debug", action="store_true", help="Enable DEBUG logging")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    if args.stats:
        show_stats()
    elif args.fetch_ibge:
        fetch_ibge_data()
    elif args.normalize_locations:
        normalize_locations_only(source=args.source)
    elif args.deduplicate:
        deduplicate_only()
    elif args.enrich_only:
        enrich_only(source=args.source)
    elif args.reparse:
        reparse_vagas()
    else:
        asyncio.run(run(args.spiders or None, args.dry_run, args.enrich, args.locations))


if __name__ == "__main__":
    main()
