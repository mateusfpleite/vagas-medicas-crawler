import os
from unittest.mock import patch

from vagas.base_spider import BaseSpider


class ConcreteSpider(BaseSpider):
    """Minimal concrete spider for testing."""
    name = "test"


def test_proxy_inactive_by_default():
    spider = ConcreteSpider()
    assert spider._proxy is None


def test_proxy_activates_after_3_failures():
    with patch.dict(os.environ, {"PROXY_URL": "http://user:pass@proxy:1234"}):
        spider = ConcreteSpider()
        spider._record_failure()
        spider._record_failure()
        assert spider._proxy is None
        spider._record_failure()
        assert spider._proxy == "http://user:pass@proxy:1234"


def test_proxy_stays_active_after_activation():
    with patch.dict(os.environ, {"PROXY_URL": "http://user:pass@proxy:1234"}):
        spider = ConcreteSpider()
        for _ in range(3):
            spider._record_failure()
        assert spider._proxy is not None
        spider._record_success()
        assert spider._proxy is not None  # does NOT deactivate


def test_proxy_never_activates_without_env_var():
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("PROXY_URL", None)
        spider = ConcreteSpider()
        for _ in range(10):
            spider._record_failure()
        assert spider._proxy is None


def test_record_success_resets_failure_count():
    with patch.dict(os.environ, {"PROXY_URL": "http://proxy:1234"}):
        spider = ConcreteSpider()
        spider._record_failure()
        spider._record_failure()
        spider._record_success()  # reset
        spider._record_failure()
        assert spider._proxy is None  # only 1 failure since reset


def test_proxy_threshold_is_3():
    assert BaseSpider.PROXY_THRESHOLD == 3


def test_record_failure_returns_true_on_activation():
    with patch.dict(os.environ, {"PROXY_URL": "http://proxy:1234"}):
        spider = ConcreteSpider()
        assert spider._record_failure() is False
        assert spider._record_failure() is False
        assert spider._record_failure() is True  # proxy just activated
        assert spider._record_failure() is False  # already active, no new activation


def test_record_failure_returns_false_without_proxy():
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("PROXY_URL", None)
        spider = ConcreteSpider()
        for _ in range(10):
            assert spider._record_failure() is False
