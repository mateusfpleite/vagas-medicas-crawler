# HTML Storage: Salvar páginas completas de vagas em disco

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Cada spider busca a página individual de cada vaga e salva o HTML completo + metadados em disco, para iterarmos sobre o parser sem re-crawlear.

**Architecture:** Após parsear a listagem, cada spider navega sequencialmente nas URLs das vagas, captura o HTML via `page.content()`, e salva em `data/{source}/{id}.html` + `data/{source}/{id}.json`. VagaMédica e Trabalha Brasil não buscam detalhes (WhatsApp / bloqueado). O banco de dados não é mais necessário no fluxo principal.

**Tech Stack:** Python 3.13, Playwright, httpx, BeautifulSoup, pathlib, json

---

### Task 1: Criar módulo storage.py

**Files:**
- Create: `src/vagas/storage.py`
- Test: `tests/test_storage.py`

**Step 1: Write the failing test**

```python
# tests/test_storage.py
import json
from pathlib import Path
from vagas.models import Vaga
from vagas.storage import save_vaga


def test_save_vaga_with_html(tmp_path):
    vaga = Vaga(
        title="Médico Clínico",
        location="São Paulo, SP",
        source="indeed",
        url="https://indeed.com/job/123",
        company="Hospital X",
        external_id="abc123",
    )
    html = "<html><body>Job details here</body></html>"

    save_vaga(vaga, tmp_path, raw_html=html)

    html_file = tmp_path / "indeed" / "abc123.html"
    json_file = tmp_path / "indeed" / "abc123.json"

    assert html_file.exists()
    assert html_file.read_text(encoding="utf-8") == html

    assert json_file.exists()
    meta = json.loads(json_file.read_text(encoding="utf-8"))
    assert meta["title"] == "Médico Clínico"
    assert meta["company"] == "Hospital X"
    assert meta["source"] == "indeed"
    assert meta["url"] == "https://indeed.com/job/123"
    assert "raw_html" not in meta  # raw_html não deve ir pro JSON


def test_save_vaga_without_html(tmp_path):
    vaga = Vaga(
        title="Ginecologista",
        location="PI",
        source="vagamedica",
        url="https://wa.me/123",
    )

    save_vaga(vaga, tmp_path, raw_html=None)

    json_file = tmp_path / "vagamedica" / vaga.dedup_key()[:12] + ".json"
    assert json_file.exists()

    html_files = list((tmp_path / "vagamedica").glob("*.html"))
    assert len(html_files) == 0


def test_save_vaga_uses_dedup_key_when_no_external_id(tmp_path):
    vaga = Vaga(
        title="Pediatra",
        location="RS",
        source="vagamedica",
        url="https://wa.me/456",
    )

    save_vaga(vaga, tmp_path)

    key = vaga.dedup_key()[:12]
    json_file = tmp_path / "vagamedica" / f"{key}.json"
    assert json_file.exists()
```

**Step 2: Run test to verify it fails**

Run: `cd /home/mateus-leite/Documents/vagas-medicas && python -m pytest tests/test_storage.py -v`
Expected: FAIL — `ImportError: cannot import name 'save_vaga' from 'vagas.storage'`

**Step 3: Write minimal implementation**

```python
# src/vagas/storage.py
import json
import logging
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from vagas.models import Vaga

log = logging.getLogger(__name__)


def _file_id(vaga: Vaga) -> str:
    """Retorna external_id se disponível, senão primeiros 12 chars do dedup_key."""
    return vaga.external_id or vaga.dedup_key()[:12]


def _serialize_vaga(vaga: Vaga) -> dict:
    """Converte Vaga para dict serializável em JSON (exclui raw_html)."""
    d = asdict(vaga)
    d.pop("raw_html", None)  # HTML salvo em arquivo separado
    # datetime -> ISO string
    for k, v in d.items():
        if isinstance(v, datetime):
            d[k] = v.isoformat()
    return d


def save_vaga(vaga: Vaga, output_dir: Path, raw_html: str | None = None) -> Path:
    """Salva metadados JSON e opcionalmente HTML de uma vaga em disco.

    Estrutura:
        output_dir/
          {source}/
            {file_id}.json
            {file_id}.html   (se raw_html fornecido)

    Retorna o Path da pasta da fonte.
    """
    source_dir = output_dir / vaga.source
    source_dir.mkdir(parents=True, exist_ok=True)

    file_id = _file_id(vaga)

    # Salvar metadados
    json_path = source_dir / f"{file_id}.json"
    json_path.write_text(
        json.dumps(_serialize_vaga(vaga), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # Salvar HTML se disponível
    if raw_html:
        html_path = source_dir / f"{file_id}.html"
        html_path.write_text(raw_html, encoding="utf-8")

    log.debug("Saved %s/%s", vaga.source, file_id)
    return source_dir
```

**Step 4: Run test to verify it passes**

Run: `cd /home/mateus-leite/Documents/vagas-medicas && python -m pytest tests/test_storage.py -v`
Expected: 3 PASSED

---

### Task 2: Refatorar IndeedSpider para buscar detalhes

**Files:**
- Modify: `src/vagas/spiders/indeed.py`
- Test: `tests/test_spiders/test_indeed.py` (adicionar teste)

**Step 1: Write the failing test**

Adicionar ao final de `tests/test_spiders/test_indeed.py`:

```python
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

def test_crawl_fetches_detail_pages():
    """crawl() deve buscar HTML individual de cada vaga."""
    listing_html = Path(__file__).parent.parent.joinpath(
        "fixtures", "indeed_page.html"
    ).read_text()

    detail_html = "<html><body>Detail page</body></html>"

    # Mock stealth_page context manager
    mock_page = AsyncMock()
    mock_page.content = AsyncMock(side_effect=[listing_html] + [detail_html] * 20)
    mock_page.goto = AsyncMock()
    mock_page.wait_for_selector = AsyncMock()
    mock_page.wait_for_timeout = AsyncMock()

    from vagas.spiders.indeed import IndeedSpider
    spider = IndeedSpider()

    vagas = spider.parse(listing_html)
    # Verificar que parse retorna vagas sem raw_html
    assert len(vagas) > 0
    assert all(v.raw_html is None for v in vagas)
```

**Step 2: Run test to verify it fails**

Run: `cd /home/mateus-leite/Documents/vagas-medicas && python -m pytest tests/test_spiders/test_indeed.py::test_crawl_fetches_detail_pages -v`
Expected: FAIL — `AttributeError: 'Vaga' has no attribute 'raw_html'`

**Step 3: Adicionar `raw_html` ao modelo Vaga**

Em `src/vagas/models.py`, adicionar campo ao dataclass:

```python
raw_html: str | None = None
```

Logo após o campo `crawled_at`. Não entra no `dedup_key()`.

**Step 4: Run test to verify it passes**

Run: `cd /home/mateus-leite/Documents/vagas-medicas && python -m pytest tests/test_spiders/test_indeed.py::test_crawl_fetches_detail_pages -v`
Expected: PASS

**Step 5: Refatorar `crawl()` do IndeedSpider**

Substituir o método `crawl()` em `src/vagas/spiders/indeed.py`:

```python
import asyncio  # adicionar no topo do arquivo

async def crawl(self) -> list[Vaga]:
    async with stealth_page() as page:
        # 1. Buscar listagem
        try:
            await page.goto(self.SEARCH_URL, wait_until="domcontentloaded")
            await page.wait_for_selector(self.WAIT_SELECTOR, timeout=20000)
        except Exception:
            log.warning("%s blocked or failed -- skipping", self.name)
            return []

        listing_html = await page.content()
        vagas = self.parse(listing_html)

        if not vagas:
            return []

        # 2. Buscar detalhe de cada vaga sequencialmente
        fetched = 0
        for vaga in vagas:
            if not vaga.url:
                continue
            try:
                await page.goto(vaga.url, wait_until="domcontentloaded")
                await asyncio.sleep(1)
                vaga.raw_html = await page.content()
                fetched += 1
                log.debug("[%s] Fetched detail: %s", self.name, vaga.url)
            except Exception as e:
                log.warning("[%s] Failed to fetch detail %s: %s", self.name, vaga.url, e)
        log.info("[%s] Fetched details: %d/%d", self.name, fetched, len(vagas))

    return vagas
```

Substituir `from vagas.browser import fetch_rendered_html` por `from vagas.browser import stealth_page`.

**Step 6: Run all Indeed tests**

Run: `cd /home/mateus-leite/Documents/vagas-medicas && python -m pytest tests/test_spiders/test_indeed.py -v`
Expected: ALL PASS

---

### Task 3: Refatorar VagasComSpider para buscar detalhes

**Files:**
- Modify: `src/vagas/spiders/vagas_com.py`

**Step 1: Refatorar `crawl()` do VagasComSpider**

Mesma abordagem do Indeed. Substituir `crawl()` em `src/vagas/spiders/vagas_com.py`:

```python
import asyncio  # adicionar no topo do arquivo

async def crawl(self) -> list[Vaga]:
    async with stealth_page() as page:
        # 1. Buscar listagem
        try:
            await page.goto(self.SEARCH_URL, wait_until="domcontentloaded")
            await page.wait_for_selector(self.WAIT_SELECTOR, timeout=20000)
        except Exception:
            log.warning("%s blocked or failed -- skipping", self.name)
            return []

        listing_html = await page.content()
        vagas = self.parse(listing_html)

        if not vagas:
            return []

        # 2. Buscar detalhe de cada vaga sequencialmente
        fetched = 0
        for vaga in vagas:
            if not vaga.url:
                continue
            try:
                await page.goto(vaga.url, wait_until="domcontentloaded")
                await asyncio.sleep(1)
                vaga.raw_html = await page.content()
                fetched += 1
                log.debug("[%s] Fetched detail: %s", self.name, vaga.url)
            except Exception as e:
                log.warning("[%s] Failed to fetch detail %s: %s", self.name, vaga.url, e)
        log.info("[%s] Fetched details: %d/%d", self.name, fetched, len(vagas))

    return vagas
```

Substituir `from vagas.browser import fetch_rendered_html` por `from vagas.browser import stealth_page`.

**Step 2: Run all Vagas.com tests**

Run: `cd /home/mateus-leite/Documents/vagas-medicas && python -m pytest tests/test_spiders/test_vagas_com.py -v`
Expected: ALL PASS

---

### Task 4: BNE Spider — buscar detalhes via httpx

**Files:**
- Modify: `src/vagas/spiders/bne.py`

**Step 1: Adicionar fetch de detalhes no BNE**

Após o loop de paginação no `crawl()`, adicionar busca de detalhes. BNE já tem o `httpx.AsyncClient` aberto. Páginas de detalhe do BNE podem precisar de headers browser-like (a listagem já precisa de Playwright), então adicionamos User-Agent e Referer. Se httpx receber < 1KB de resposta, logamos warning (provável bloqueio).

Adicionar no final do `crawl()`, antes do `return`, ainda dentro do `async with httpx.AsyncClient`:

```python
        # 3. Fetch detail pages
        detail_headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Referer": SEARCH_PAGE,
        }
        fetched = 0
        for vaga in all_vagas:
            if not vaga.url or vaga.url == SEARCH_PAGE:
                continue
            try:
                resp = await client.get(vaga.url, follow_redirects=True, headers=detail_headers)
                resp.raise_for_status()
                if len(resp.text) < 1000:
                    log.warning("[%s] Detail page suspiciously small (%d bytes): %s", self.name, len(resp.text), vaga.url)
                else:
                    vaga.raw_html = resp.text
                    fetched += 1
                log.debug("[%s] Fetched detail: %s", self.name, vaga.url)
                await asyncio.sleep(1)
            except Exception as e:
                log.warning("[%s] Failed to fetch detail %s: %s", self.name, vaga.url, e)
        log.info("[%s] Fetched details: %d/%d", self.name, fetched, len(all_vagas))
```

Adicionar `import asyncio` no topo do arquivo.

**Step 2: Run BNE tests**

Run: `cd /home/mateus-leite/Documents/vagas-medicas && python -m pytest tests/test_spiders/test_bne.py -v`
Expected: ALL PASS

---

### Task 5: Refatorar CLI para salvar em disco

**Files:**
- Modify: `src/vagas/cli.py`
- Test: `tests/test_cli.py`

**Step 1: Write the failing test**

```python
# tests/test_cli.py
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from vagas.cli import run
from vagas.models import Vaga


@pytest.fixture
def fake_vagas():
    return [
        Vaga(
            title="Médico Clínico",
            location="SP",
            source="indeed",
            url="https://indeed.com/job/1",
            external_id="job1",
            raw_html="<html>detail</html>",
        ),
        Vaga(
            title="Pediatra",
            location="RJ",
            source="indeed",
            url="https://indeed.com/job/2",
            external_id="job2",
        ),
    ]


async def test_run_saves_to_disk(tmp_path, fake_vagas):
    with patch("vagas.cli.ALL_SPIDERS") as mock_spiders:
        mock_spider_cls = type("MockSpider", (), {
            "name": "indeed",
            "__call__": lambda self: self,
            "crawl": AsyncMock(return_value=fake_vagas),
        })
        mock_spiders.__iter__ = lambda self: iter([mock_spider_cls])

        await run(output_dir=tmp_path)

    # Deve ter criado arquivos
    indeed_dir = tmp_path / "indeed"
    assert indeed_dir.exists()
    assert (indeed_dir / "job1.html").exists()
    assert (indeed_dir / "job1.json").exists()
    assert (indeed_dir / "job2.json").exists()
    # job2 não tem raw_html, então não deve ter .html
    assert not (indeed_dir / "job2.html").exists()
```

**Step 2: Run test to verify it fails**

Run: `cd /home/mateus-leite/Documents/vagas-medicas && python -m pytest tests/test_cli.py -v`
Expected: FAIL

**Step 3: Reescrever CLI para salvar em disco**

Substituir `src/vagas/cli.py`:

```python
# src/vagas/cli.py
import argparse
import asyncio
import logging
from pathlib import Path

from vagas.storage import save_vaga
from vagas.spiders.bne import BNESpider
from vagas.spiders.vagamedica import VagaMedicaSpider
from vagas.spiders.indeed import IndeedSpider
from vagas.spiders.vagas_com import VagasComSpider
from vagas.spiders.trabalha_brasil import TrabalhaBrasilSpider

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
log = logging.getLogger("vagas.cli")

ALL_SPIDERS = [BNESpider, VagaMedicaSpider, IndeedSpider, VagasComSpider, TrabalhaBrasilSpider]

DEFAULT_OUTPUT = Path("data")


async def run(
    spider_names: list[str] | None = None,
    dry_run: bool = False,
    output_dir: Path = DEFAULT_OUTPUT,
):
    spiders = ALL_SPIDERS
    if spider_names:
        spiders = [s for s in ALL_SPIDERS if s.name in spider_names]

    if not spiders:
        log.error("No spiders matched. Available: %s", [s.name for s in ALL_SPIDERS])
        return

    total_saved = 0

    for spider_cls in spiders:
        spider = spider_cls()
        log.info("[%s] Crawling...", spider.name)
        try:
            vagas = await spider.crawl()
            log.info("[%s] Found %d vagas", spider.name, len(vagas))

            if dry_run:
                for v in vagas[:5]:
                    has_html = "✓" if v.raw_html else "✗"
                    print(f"  [{has_html}] {v.title} | {v.location} | {v.url}")
                if len(vagas) > 5:
                    print(f"  ... and {len(vagas) - 5} more")
            else:
                for v in vagas:
                    save_vaga(v, output_dir, raw_html=v.raw_html)
                    total_saved += 1
                log.info("[%s] Saved %d vagas to %s", spider.name, len(vagas), output_dir / spider.name)

        except Exception:
            log.exception("[%s] Failed", spider.name)

    if not dry_run:
        log.info("Done. Total: %d vagas saved to %s", total_saved, output_dir)


def main():
    parser = argparse.ArgumentParser(description="Crawler de vagas médicas")
    parser.add_argument("spiders", nargs="*", help="Spiders to run (default: all)")
    parser.add_argument("--dry-run", action="store_true", help="Print vagas without saving")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT, help="Output directory (default: data/)")
    args = parser.parse_args()
    asyncio.run(run(args.spiders or None, args.dry_run, args.output_dir))


if __name__ == "__main__":
    main()
```

**Step 4: Run CLI test**

Run: `cd /home/mateus-leite/Documents/vagas-medicas && python -m pytest tests/test_cli.py -v`
Expected: PASS

**Step 5: Run all tests**

Run: `cd /home/mateus-leite/Documents/vagas-medicas && python -m pytest -v`
Expected: ALL PASS

---

### Task 6: Adicionar `data/` ao .gitignore e testar E2E

**Files:**
- Create: `.gitignore` (se não existir)

**Step 1: Criar .gitignore**

```
# Crawled data (HTML + JSON files)
data/

# Python
__pycache__/
*.pyc
*.egg-info/
dist/
build/

# Environment
.env
.venv/
```

**Step 2: Teste E2E manual**

Run: `cd /home/mateus-leite/Documents/vagas-medicas && python -m vagas.cli indeed --dry-run`

Expected: Lista de vagas com `[✓]` ou `[✗]` indicando se capturou HTML de detalhe.

Run: `cd /home/mateus-leite/Documents/vagas-medicas && python -m vagas.cli indeed --output-dir data`

Expected: Arquivos criados em `data/indeed/`. Cada vaga com `.json` e `.html`.

Verificar:
- `ls data/indeed/` — deve ter pares de arquivos
- `cat data/indeed/<id>.json` — metadados da vaga
- Abrir `data/indeed/<id>.html` no browser — página completa da vaga

---

## Resumo de mudanças

| Arquivo | Ação |
|---------|------|
| `src/vagas/models.py` | Adicionar campo `raw_html: str \| None = None` |
| `src/vagas/storage.py` | **Novo** — `save_vaga()` salva HTML + JSON em disco |
| `src/vagas/spiders/indeed.py` | Refatorar `crawl()` — reutilizar sessão, buscar detalhes |
| `src/vagas/spiders/vagas_com.py` | Refatorar `crawl()` — idem |
| `src/vagas/spiders/bne.py` | Adicionar fetch de detalhes via httpx |
| `src/vagas/cli.py` | Substituir DB por storage em disco |
| `tests/test_storage.py` | **Novo** — testes do módulo storage |
| `tests/test_cli.py` | **Novo** — teste do CLI com disco |
| `.gitignore` | **Novo** — ignorar `data/` |

**Sem mudanças:** `vagamedica.py` (WhatsApp, não busca detalhes), `trabalha_brasil.py` (stub), `browser.py`, `db.py` (mantido mas não usado no fluxo principal).
