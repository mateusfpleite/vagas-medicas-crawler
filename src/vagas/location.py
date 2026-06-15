"""Location normalization using IBGE municipalities data."""

import json
import logging
import re
from pathlib import Path

import httpx

from vagas.utils import strip_accents

log = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).resolve().parents[2] / "data"
_CACHE_PATH = _DATA_DIR / "ibge_municipios.json"

_IBGE_URL = "https://servicodados.ibge.gov.br/api/v1/localidades/municipios"

_VALID_UFS = {
    "AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO",
    "MA", "MG", "MS", "MT", "PA", "PB", "PE", "PI", "PR",
    "RJ", "RN", "RO", "RR", "RS", "SC", "SE", "SP", "TO",
}

_SKIP_VALUES = {"remoto", "brasil", "home office", "a combinar", ""}

# Matches: "City - UF", "City, UF", "City / UF", "City/UF"
_LOCATION_RE = re.compile(r"^(.+?)\s*[-,/]\s*([A-Za-z]{2})\s*$")

# Module-level lookup tables (populated on first use)
_LOOKUP: dict[tuple[str, str], str] | None = None
_LOOKUP_BY_NAME: dict[str, list[tuple[str, str]]] | None = None


def _normalize_key(name: str) -> str:
    """Normalize a city name for lookup: lowercase, no accents."""
    return strip_accents(name).lower().strip()


def parse_location(raw: str | None) -> tuple[str | None, str | None]:
    """Parse a raw location string into (city, state).

    Returns (None, None) for remote/empty/special values.
    Returns (city, None) if no state code is found.
    """
    if not raw or not raw.strip():
        return None, None

    cleaned = raw.strip()
    if cleaned.lower() in _SKIP_VALUES:
        return None, None

    m = _LOCATION_RE.match(cleaned)
    if m:
        city = m.group(1).strip()
        uf = m.group(2).upper()
        if uf in _VALID_UFS:
            return city, uf
        # Invalid UF — treat as city-only
        return cleaned, None

    # No separator found — check if it's a bare UF code
    if cleaned.upper() in _VALID_UFS:
        return None, cleaned.upper()
    return cleaned, None


def fetch_ibge_data() -> list[dict]:
    """Fetch IBGE municipalities and cache to data/ibge_municipios.json."""
    log.info("Fetching IBGE municipalities data...")
    resp = httpx.get(_IBGE_URL, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    _CACHE_PATH.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    log.info("Cached %d municipalities to %s", len(data), _CACHE_PATH)
    return data


def _load_ibge_data() -> list[dict]:
    """Load IBGE data from cache, fetching if needed."""
    if _CACHE_PATH.exists():
        return json.loads(_CACHE_PATH.read_text(encoding="utf-8"))
    return fetch_ibge_data()


def _build_lookup(data: list[dict]) -> tuple[
    dict[tuple[str, str], str],
    dict[str, list[tuple[str, str]]],
]:
    """Build lookup dicts from IBGE municipality data.

    Returns:
        (by_name_uf, by_name) where:
        - by_name_uf: {(normalized_name, uf): official_name}
        - by_name: {normalized_name: [(official_name, uf), ...]}
    """
    by_name_uf: dict[tuple[str, str], str] = {}
    by_name: dict[str, list[tuple[str, str]]] = {}

    for mun in data:
        nome = mun["nome"]
        # Primary path: microrregiao → mesorregiao → UF
        # Fallback: regiao-imediata → regiao-intermediaria → UF
        # (some municipalities have microrregiao: null)
        micro = mun.get("microrregiao")
        if micro:
            uf = micro["mesorregiao"]["UF"]["sigla"]
        else:
            ri = mun.get("regiao-imediata", {}).get("regiao-intermediaria", {})
            uf_obj = ri.get("UF")
            if not uf_obj:
                continue
            uf = uf_obj["sigla"]
        key = _normalize_key(nome)

        by_name_uf[(key, uf)] = nome
        by_name.setdefault(key, []).append((nome, uf))

    return by_name_uf, by_name


def _ensure_lookup() -> None:
    """Ensure lookup tables are populated."""
    global _LOOKUP, _LOOKUP_BY_NAME
    if _LOOKUP is None:
        data = _load_ibge_data()
        _LOOKUP, _LOOKUP_BY_NAME = _build_lookup(data)


def normalize_location(raw: str | None) -> tuple[str | None, str | None]:
    """Normalize a raw location string to (official_city, uf).

    Uses IBGE data to find official city names with correct accents/casing.

    When state is present: returns (official_city or raw_city, uf).
    When city-only and unambiguous in IBGE: returns (official_city, uf).
    When city-only and ambiguous/unknown: returns (None, None) — delegate to AI.
    """
    city, uf = parse_location(raw)
    if city is None:
        return None, uf

    _ensure_lookup()
    assert _LOOKUP is not None and _LOOKUP_BY_NAME is not None

    key = _normalize_key(city)

    # City + state: direct lookup
    if uf:
        official = _LOOKUP.get((key, uf))
        if official:
            return official, uf
        # Not in IBGE — return raw city with UF (AI can refine later)
        return city, uf

    # City-only: lookup by name
    matches = _LOOKUP_BY_NAME.get(key, [])
    if len(matches) == 1:
        return matches[0]  # (official_name, uf)
    # Ambiguous or not found — delegate to AI
    return None, None
