import logging
import os

from vagas.models import Vaga

log = logging.getLogger(__name__)


class BaseSpider:
    name: str = "base"

    PROXY_THRESHOLD = 3

    def __init__(self):
        self._consecutive_failures = 0
        self._proxy_active = False
        self._proxy_url: str | None = os.environ.get("PROXY_URL")

    def _record_failure(self) -> bool:
        """Record a failure. Returns True if proxy was just activated."""
        self._consecutive_failures += 1
        if (
            self._proxy_url
            and not self._proxy_active
            and self._consecutive_failures >= self.PROXY_THRESHOLD
        ):
            self._proxy_active = True
            log.warning(
                "[%s] %d consecutive failures — activating proxy",
                self.name,
                self._consecutive_failures,
            )
            self._consecutive_failures = 0
            return True
        return False

    def _record_success(self):
        self._consecutive_failures = 0

    @property
    def _proxy(self) -> str | None:
        return self._proxy_url if self._proxy_active else None

    def parse(self, raw_data) -> list[Vaga]:
        raise NotImplementedError

    async def crawl(
        self,
        known_ids: set[str] | None = None,
        locations: list[str] | None = None,
    ) -> list[Vaga]:
        raise NotImplementedError
