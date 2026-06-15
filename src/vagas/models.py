import hashlib
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import UTC, datetime


def _normalize(text: str) -> str:
    """Remove acentos, pontuação e espaços extras para comparação."""
    nfkd = unicodedata.normalize("NFKD", text)
    ascii_text = nfkd.encode("ascii", "ignore").decode("ascii")
    cleaned = re.sub(r"[^\w\s]", " ", ascii_text)
    return re.sub(r"\s+", " ", cleaned).strip().lower()


@dataclass
class Vaga:
    title: str
    location: str
    source: str
    url: str
    company: str | None = None
    salary: str | None = None
    job_type: str | None = None
    specialty: str | None = None
    city: str | None = None
    state: str | None = None
    external_id: str | None = None
    description: str | None = None
    salary_min: float | None = None
    salary_max: float | None = None
    salary_period: str | None = None  # "MONTHLY", "YEARLY", "HOURLY", etc.
    benefits: list[str] | None = None
    published_at: datetime | None = None
    crawled_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    raw_html: str | None = None

    def dedup_key(self) -> str:
        """Hash baseado em título + empresa + localização normalizados."""
        parts = [
            _normalize(self.title),
            _normalize(self.company or ""),
            _normalize(self.location),
        ]
        raw = "|".join(parts)
        return hashlib.sha256(raw.encode()).hexdigest()
