from unittest.mock import AsyncMock, patch

from vagas.browser import stealth_context


async def test_stealth_context_passes_proxy_to_launch():
    mock_browser = AsyncMock()
    mock_context = AsyncMock()
    mock_browser.new_context.return_value = mock_context

    mock_chromium = AsyncMock()
    mock_chromium.launch.return_value = mock_browser

    mock_pw = AsyncMock()
    mock_pw.chromium = mock_chromium

    with patch("vagas.browser.async_playwright") as mock_apw:
        mock_apw.return_value.__aenter__ = AsyncMock(return_value=mock_pw)
        mock_apw.return_value.__aexit__ = AsyncMock(return_value=False)

        async with stealth_context(proxy="http://user:pass@proxy:1234") as ctx:
            pass

        mock_chromium.launch.assert_called_once()
        call_kwargs = mock_chromium.launch.call_args[1]
        assert call_kwargs["proxy"] == {"server": "http://proxy:1234", "username": "user", "password": "pass"}


async def test_stealth_context_no_proxy_by_default():
    mock_browser = AsyncMock()
    mock_context = AsyncMock()
    mock_browser.new_context.return_value = mock_context

    mock_chromium = AsyncMock()
    mock_chromium.launch.return_value = mock_browser

    mock_pw = AsyncMock()
    mock_pw.chromium = mock_chromium

    with patch("vagas.browser.async_playwright") as mock_apw:
        mock_apw.return_value.__aenter__ = AsyncMock(return_value=mock_pw)
        mock_apw.return_value.__aexit__ = AsyncMock(return_value=False)

        async with stealth_context() as ctx:
            pass

        call_kwargs = mock_chromium.launch.call_args[1]
        assert "proxy" not in call_kwargs
