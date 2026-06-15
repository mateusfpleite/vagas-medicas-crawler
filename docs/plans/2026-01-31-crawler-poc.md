# POC Crawler de Vagas Médicas — Plano de Implementação

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Validar que conseguimos extrair vagas médicas reais de múltiplas fontes (BNE, Vaga Médica, Indeed, Vagas.com, Trabalha Brasil) e salvá-las num formato normalizado em banco PostgreSQL.

**Architecture:** Projeto Python com Playwright para crawling. Cada fonte tem um spider independente que herda de uma classe base. Os spiders extraem vagas, normalizam para um schema comum, e gravam no PostgreSQL (Neon). Um script CLI orquestra a execução dos spiders.

**Tech Stack:** Python 3.13, Playwright (async) + playwright-stealth, BeautifulSoup4 (parsing HTML), httpx (requests HTTP diretas para APIs), PostgreSQL (Neon), psycopg (driver async), pytest + pytest-asyncio (testes).

**Critério de sucesso da POC:** pelo menos 2 fontes funcionando com vagas reais no banco. Indeed e Vagas.com são best-effort — se o anti-bot bloquear, seguir em frente.

---

## Estrutura do projeto

```
vagas-medicas/
├── pyproject.toml
├── src/
│   └── vagas/
│       ├── __init__.py
│       ├── models.py          # dataclass Vaga (schema normalizado)
│       ├── db.py              # conexão e operações PostgreSQL
│       ├── base_spider.py     # classe base dos spiders
│       ├── browser.py         # helper Playwright + stealth
│       ├── spiders/
│       │   ├── __init__.py
│       │   ├── bne.py         # BNE (API REST)
│       │   ├── vagamedica.py  # Vaga Médica (HTML estático)
│       │   ├── vagas_com.py   # Vagas.com.br (best-effort)
│       │   ├── indeed.py      # Indeed Brasil (best-effort)
│       │   └── trabalha_brasil.py  # Trabalha Brasil
│       └── cli.py             # entry point CLI
├── tests/
│   ├── conftest.py
│   ├── __init__.py
│   ├── fixtures/              # HTML/JSON salvos para testes offline
│   │   ├── bne_response.json
│   │   ├── vagamedica_page.html
│   │   ├── vagas_com_page.html
│   │   ├── indeed_page.html
│   │   └── trabalha_brasil_page.html
│   ├── test_models.py
│   ├── test_db.py
│   └── test_spiders/
│       ├── __init__.py
│       ├── test_bne.py
│       ├── test_vagamedica.py
│       ├── test_vagas_com.py
│       ├── test_indeed.py
│       └── test_trabalha_brasil.py
└── docs/
    └── plans/
```

---

## Task 1: Setup do projeto Python

**Files:**
- Create: `pyproject.toml`
- Create: `src/vagas/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/test_spiders/__init__.py`

**Step 1: Criar pyproject.toml**

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "vagas-medicas"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "playwright>=1.49",
    "playwright-stealth>=1.0.6",
    "beautifulsoup4>=4.12",
    "httpx>=0.28",
    "psycopg[binary]>=3.2",
    "lxml>=5.3",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.25",
]

[project.scripts]
vagas = "vagas.cli:main"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
```

**Step 2: Criar arquivos __init__.py**

```python
# src/vagas/__init__.py
# tests/__init__.py
# tests/test_spiders/__init__.py
```

(todos vazios)

**Step 3: Instalar dependências**

Run: `cd /home/mateus-leite/Documents/vagas-medicas && pip install -e ".[dev]"`
Expected: instalação bem-sucedida

**Step 4: Instalar Playwright + dependências de sistema**

Run: `playwright install --with-deps chromium`
Expected: download do Chromium + bibliotecas de sistema (libnss3, libatk-bridge, etc.)

**Step 5: Verificar que importa**

Run: `cd /home/mateus-leite/Documents/vagas-medicas && python -c "import vagas; print('ok')"`
Expected: `ok`

---

## Task 2: Modelo de dados (dataclass Vaga)

**Files:**
- Create: `src/vagas/models.py`
- Create: `tests/test_models.py`

**Step 1: Escrever o teste**

```python
# tests/test_models.py
from vagas.models import Vaga


def test_vaga_creation_minimal():
    v = Vaga(
        title="Médico Plantonista",
        location="São Paulo - SP",
        source="bne",
        url="https://example.com/vaga/123",
    )
    assert v.title == "Médico Plantonista"
    assert v.source == "bne"
    assert v.salary is None
    assert v.company is None


def test_vaga_creation_full():
    v = Vaga(
        title="Médico Clínico Geral",
        company="Hospital São Luiz",
        location="Rio de Janeiro - RJ",
        salary="R$ 120/hora",
        job_type="plantao",
        specialty="Clínica Médica",
        source="vagamedica",
        url="https://vagamedica.com.br/vaga/456",
        external_id="456",
        description="Plantão 12h em emergência",
    )
    assert v.company == "Hospital São Luiz"
    assert v.salary == "R$ 120/hora"
    assert v.external_id == "456"


def test_vaga_dedup_key():
    v = Vaga(
        title="Médico Plantonista",
        company="Hospital X",
        location="SP",
        source="bne",
        url="https://example.com/1",
    )
    key = v.dedup_key()
    assert isinstance(key, str)
    assert len(key) == 64  # SHA-256 hex digest


def test_vaga_same_dedup_key_different_sources():
    kwargs = dict(
        title="Médico Plantonista",
        company="Hospital X",
        location="São Paulo",
        source="bne",
        url="https://example.com/1",
    )
    v1 = Vaga(**kwargs)
    v2 = Vaga(**{**kwargs, "source": "indeed", "url": "https://other.com/2"})
    assert v1.dedup_key() == v2.dedup_key()


def test_vaga_dedup_key_normalizes_accents():
    v1 = Vaga(title="Médico", location="São Paulo - SP", source="a", url="http://a")
    v2 = Vaga(title="Medico", location="Sao Paulo - SP", source="b", url="http://b")
    assert v1.dedup_key() == v2.dedup_key()


def test_vaga_dedup_key_normalizes_punctuation():
    v1 = Vaga(title="Médico", location="São Paulo - SP", source="a", url="http://a")
    v2 = Vaga(title="Médico", location="São Paulo/SP", source="b", url="http://b")
    assert v1.dedup_key() == v2.dedup_key()
```

**Step 2: Rodar teste e verificar que falha**

Run: `cd /home/mateus-leite/Documents/vagas-medicas && pytest tests/test_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'vagas.models'`

**Step 3: Implementar models.py**

```python
# src/vagas/models.py
import hashlib
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import UTC, datetime


def _normalize(text: str) -> str:
    """Remove acentos, pontuação e espaços extras para comparação."""
    # Remove acentos
    nfkd = unicodedata.normalize("NFKD", text)
    ascii_text = nfkd.encode("ascii", "ignore").decode("ascii")
    # Remove pontuação e normaliza espaços
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
    external_id: str | None = None
    description: str | None = None
    crawled_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def dedup_key(self) -> str:
        """Hash baseado em título + empresa + localização normalizados."""
        parts = [
            _normalize(self.title),
            _normalize(self.company or ""),
            _normalize(self.location),
        ]
        raw = "|".join(parts)
        return hashlib.sha256(raw.encode()).hexdigest()
```

**Step 4: Rodar teste e verificar que passa**

Run: `cd /home/mateus-leite/Documents/vagas-medicas && pytest tests/test_models.py -v`
Expected: 6 passed

---

## Task 3: Camada de banco de dados

**Files:**
- Create: `src/vagas/db.py`
- Create: `tests/test_db.py`

Nota: Para os testes, vamos usar o banco Neon real (POC, não produção). A connection string vem de variável de ambiente `DATABASE_URL`.

**Step 1: Escrever o teste**

```python
# tests/test_db.py
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
    assert second is False  # duplicata, não inseriu

    vagas = await db.list_vagas(source="test")
    assert len(vagas) == 1
```

**Step 2: Rodar teste e verificar que falha**

Run: `cd /home/mateus-leite/Documents/vagas-medicas && DATABASE_URL="<connection_string>" pytest tests/test_db.py -v`
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Implementar db.py**

```python
# src/vagas/db.py
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
        """Insere vaga se não existir (baseado em dedup_key). Retorna True se inseriu."""
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
```

**Step 4: Criar banco no Neon e rodar teste**

Primeiro, criar um projeto no Neon (ou usar existente). Obter a connection string.

Run: `cd /home/mateus-leite/Documents/vagas-medicas && DATABASE_URL="postgresql://..." pytest tests/test_db.py -v`
Expected: 2 passed

---

## Task 4: Browser helper (Playwright + stealth)

**Files:**
- Create: `src/vagas/browser.py`

Módulo compartilhado que configura Playwright com stealth para todos os spiders que precisam de browser.

**Step 1: Implementar browser.py**

```python
# src/vagas/browser.py
import logging
from contextlib import asynccontextmanager

from playwright.async_api import Page, async_playwright
from playwright_stealth import stealth_async

log = logging.getLogger(__name__)


@asynccontextmanager
async def stealth_page(headless: bool = True):
    """Abre um browser Playwright com stealth e retorna uma Page."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        page = await browser.new_page(
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1920, "height": 1080},
        )
        await stealth_async(page)
        try:
            yield page
        finally:
            await browser.close()


async def fetch_rendered_html(url: str, wait_selector: str, timeout: int = 15000) -> str | None:
    """Navega até a URL, espera o seletor, retorna o HTML. Retorna None se falhar."""
    try:
        async with stealth_page() as page:
            await page.goto(url, wait_until="domcontentloaded")
            await page.wait_for_selector(wait_selector, timeout=timeout)
            return await page.content()
    except Exception as e:
        log.warning("Failed to fetch %s: %s", url, e)
        return None
```

**Step 2: Testar manualmente**

Run: `cd /home/mateus-leite/Documents/vagas-medicas && python -c "
import asyncio
from vagas.browser import fetch_rendered_html

async def test():
    html = await fetch_rendered_html('https://www.bne.com.br/vagas-de-emprego-para-medico', 'a', timeout=10000)
    print(f'Got {len(html)} bytes' if html else 'FAILED')

asyncio.run(test())
"`
Expected: `Got XXXXX bytes`

---

## Task 5: Spider base + Spider BNE (API REST)

**Files:**
- Create: `src/vagas/base_spider.py`
- Create: `src/vagas/spiders/__init__.py`
- Create: `src/vagas/spiders/bne.py`
- Create: `tests/fixtures/bne_response.json`
- Create: `tests/test_spiders/test_bne.py`

**Step 1: Investigar a API do BNE ao vivo**

Abrir o BNE com Playwright, interceptar chamadas de rede para identificar a API de vagas.

Run:

```bash
cd /home/mateus-leite/Documents/vagas-medicas && python3 -c "
import asyncio, json
from vagas.browser import stealth_page

async def investigate():
    async with stealth_page() as page:
        api_responses = []

        async def capture(response):
            if 'api' in response.url and response.status == 200:
                try:
                    body = await response.json()
                    api_responses.append((response.url, body))
                except:
                    pass

        page.on('response', capture)
        await page.goto('https://www.bne.com.br/vagas-de-emprego-para-medico')
        await page.wait_for_timeout(8000)

        for url, body in api_responses:
            print(f'URL: {url}')
            print(f'Type: {type(body).__name__}, Keys/Len: {list(body.keys()) if isinstance(body, dict) else len(body)}')
            print()

        # Salvar a maior resposta como fixture
        if api_responses:
            biggest = max(api_responses, key=lambda x: len(json.dumps(x[1])))
            with open('tests/fixtures/bne_response.json', 'w') as f:
                json.dump(biggest[1], f, ensure_ascii=False, indent=2)
            print(f'Saved fixture from: {biggest[0]}')

asyncio.run(investigate())
"
```

Expected: Lista de URLs de API + fixture salva. Anotar a URL principal e o formato do JSON.

**Step 2: Escrever teste do parser**

```python
# tests/test_spiders/test_bne.py
import json
from pathlib import Path
from vagas.spiders.bne import BNESpider

FIXTURES = Path(__file__).parent.parent / "fixtures"


def test_parse_bne_response():
    raw = json.loads((FIXTURES / "bne_response.json").read_text())
    spider = BNESpider()
    vagas = spider.parse(raw)
    assert len(vagas) > 0
    for v in vagas:
        assert v.title
        assert v.location
        assert v.source == "bne"
        assert v.url.startswith("http")
```

**Step 3: Rodar teste, verificar que falha**

Run: `cd /home/mateus-leite/Documents/vagas-medicas && pytest tests/test_spiders/test_bne.py -v`
Expected: FAIL

**Step 4: Implementar base_spider e BNE spider**

```python
# src/vagas/base_spider.py
import logging
from vagas.models import Vaga

log = logging.getLogger(__name__)


class BaseSpider:
    name: str = "base"

    def parse(self, raw_data) -> list[Vaga]:
        raise NotImplementedError

    async def crawl(self) -> list[Vaga]:
        raise NotImplementedError
```

```python
# src/vagas/spiders/__init__.py
```

```python
# src/vagas/spiders/bne.py
import httpx
from vagas.base_spider import BaseSpider
from vagas.models import Vaga


class BNESpider(BaseSpider):
    name = "bne"
    # PREENCHER após investigação no Step 1
    API_URL = "https://api.vagas.bne.com.br/..."
    SEARCH_TERM = "médico"

    def parse(self, raw_data: dict) -> list[Vaga]:
        """Parseia a resposta JSON da API do BNE.
        Adaptar ao formato real descoberto no Step 1.
        """
        vagas = []
        items = raw_data if isinstance(raw_data, list) else raw_data.get("items", raw_data.get("data", []))
        for item in items:
            vagas.append(Vaga(
                title=item.get("title", item.get("titulo", "")),
                company=item.get("company", item.get("empresa")),
                location=item.get("location", item.get("cidade", "")),
                salary=item.get("salary", item.get("salario")),
                source=self.name,
                url=item.get("url", item.get("link", "")),
                external_id=str(item.get("id", "")),
                description=item.get("description", item.get("descricao")),
            ))
        return vagas

    async def crawl(self) -> list[Vaga]:
        async with httpx.AsyncClient() as client:
            resp = await client.get(self.API_URL, params={"q": self.SEARCH_TERM})
            resp.raise_for_status()
            return self.parse(resp.json())
```

**Step 5: Ajustar parse ao JSON real e rodar teste**

Run: `cd /home/mateus-leite/Documents/vagas-medicas && pytest tests/test_spiders/test_bne.py -v`
Expected: PASS

---

## Task 6: Spider Vaga Médica (HTML estático)

**Files:**
- Create: `src/vagas/spiders/vagamedica.py`
- Create: `tests/fixtures/vagamedica_page.html`
- Create: `tests/test_spiders/test_vagamedica.py`

**Step 1: Capturar HTML real**

```bash
cd /home/mateus-leite/Documents/vagas-medicas && python3 -c "
import httpx, pathlib
r = httpx.get('https://vagamedica.com.br/', follow_redirects=True)
pathlib.Path('tests/fixtures/vagamedica_page.html').write_text(r.text)
print(f'Status: {r.status_code}, Size: {len(r.text)} bytes')
"
```

Expected: HTML salvo na fixture

**Step 2: Analisar o HTML manualmente**

Abrir `tests/fixtures/vagamedica_page.html`, identificar:
- Seletor CSS dos cards de vaga (revisão identificou que são `.jb-card`, `.jb-role`, `.jb-location` — confirmar)
- Onde estão título, localização, salário, link
- Nota: muitos links são `wa.me/...` (WhatsApp) — tratar como URL válida, o frontend decidirá como exibir

**Step 3: Escrever teste**

```python
# tests/test_spiders/test_vagamedica.py
from pathlib import Path
from vagas.spiders.vagamedica import VagaMedicaSpider

FIXTURES = Path(__file__).parent.parent / "fixtures"


def test_parse_vagamedica():
    html = (FIXTURES / "vagamedica_page.html").read_text()
    spider = VagaMedicaSpider()
    vagas = spider.parse(html)
    assert len(vagas) > 0
    for v in vagas:
        assert v.title
        assert v.source == "vagamedica"
        assert v.url  # pode ser wa.me ou link web
```

**Step 4: Rodar teste, verificar que falha**

Run: `cd /home/mateus-leite/Documents/vagas-medicas && pytest tests/test_spiders/test_vagamedica.py -v`
Expected: FAIL

**Step 5: Implementar spider**

```python
# src/vagas/spiders/vagamedica.py
import httpx
from bs4 import BeautifulSoup
from vagas.base_spider import BaseSpider
from vagas.models import Vaga


class VagaMedicaSpider(BaseSpider):
    name = "vagamedica"
    BASE_URL = "https://vagamedica.com.br"

    def parse(self, html: str) -> list[Vaga]:
        soup = BeautifulSoup(html, "lxml")
        vagas = []
        # Seletores reais identificados na revisão: .jb-card, .jb-role, .jb-location
        # CONFIRMAR e ajustar após Step 2
        for card in soup.select(".jb-card"):
            title = card.select_one(".jb-role")
            location = card.select_one(".jb-location")
            link = card.select_one("a[href]")
            salary = card.select_one(".jb-salary")

            if title:
                href = link["href"] if link else ""
                vagas.append(Vaga(
                    title=title.get_text(strip=True),
                    location=location.get_text(strip=True) if location else "",
                    salary=salary.get_text(strip=True) if salary else None,
                    source=self.name,
                    url=self._full_url(href),
                ))
        return vagas

    def _full_url(self, href: str) -> str:
        if not href:
            return ""
        if href.startswith(("http", "wa.me")):
            return href if href.startswith("http") else f"https://{href}"
        return f"{self.BASE_URL}{href}"

    async def crawl(self) -> list[Vaga]:
        async with httpx.AsyncClient() as client:
            resp = await client.get(self.BASE_URL, follow_redirects=True)
            resp.raise_for_status()
            return self.parse(resp.text)
```

**Step 6: Ajustar seletores ao HTML real e rodar teste**

Run: `cd /home/mateus-leite/Documents/vagas-medicas && pytest tests/test_spiders/test_vagamedica.py -v`
Expected: PASS

---

## Task 7: Spider Indeed Brasil (Playwright + stealth, best-effort)

**Nota: este spider é best-effort. Indeed tem anti-bot agressivo. Se a captura do HTML falhar mesmo com stealth, pular para a Task 8.**

**Files:**
- Create: `src/vagas/spiders/indeed.py`
- Create: `tests/fixtures/indeed_page.html`
- Create: `tests/test_spiders/test_indeed.py`

**Step 1: Capturar HTML renderizado com Playwright + stealth**

```bash
cd /home/mateus-leite/Documents/vagas-medicas && python3 -c "
import asyncio, pathlib
from vagas.browser import fetch_rendered_html

async def capture():
    html = await fetch_rendered_html(
        'https://br.indeed.com/jobs?q=m%C3%A9dico&l=',
        '.job_seen_beacon',  # ajustar se necessário
        timeout=20000,
    )
    if html:
        pathlib.Path('tests/fixtures/indeed_page.html').write_text(html)
        print(f'Captured {len(html)} bytes')
    else:
        print('BLOCKED - Indeed anti-bot ativo. Pular este spider.')

asyncio.run(capture())
"
```

Expected: HTML salvo **OU** mensagem de bloqueio. Se bloqueado, **pular para Task 8**.

**Step 2: Se capturou, analisar HTML e identificar seletores**

Abrir fixture, identificar cards de vaga e campos.

**Step 3: Escrever teste**

```python
# tests/test_spiders/test_indeed.py
from pathlib import Path
import pytest
from vagas.spiders.indeed import IndeedSpider

FIXTURES = Path(__file__).parent.parent / "fixtures"


@pytest.mark.skipif(
    not (FIXTURES / "indeed_page.html").exists(),
    reason="Indeed fixture not captured (anti-bot blocked)",
)
def test_parse_indeed():
    html = (FIXTURES / "indeed_page.html").read_text()
    spider = IndeedSpider()
    vagas = spider.parse(html)
    assert len(vagas) > 0
    for v in vagas:
        assert v.title
        assert v.source == "indeed"
```

**Step 4: Implementar spider**

```python
# src/vagas/spiders/indeed.py
import logging

from bs4 import BeautifulSoup
from vagas.base_spider import BaseSpider
from vagas.browser import fetch_rendered_html
from vagas.models import Vaga

log = logging.getLogger(__name__)


class IndeedSpider(BaseSpider):
    name = "indeed"
    SEARCH_URL = "https://br.indeed.com/jobs?q=m%C3%A9dico&l="
    WAIT_SELECTOR = ".job_seen_beacon"  # ajustar se necessário

    def parse(self, html: str) -> list[Vaga]:
        soup = BeautifulSoup(html, "lxml")
        vagas = []
        for card in soup.select(self.WAIT_SELECTOR):
            title_el = card.select_one("h2 a, .jobTitle a")
            company_el = card.select_one("[data-testid='company-name']")
            location_el = card.select_one("[data-testid='text-location']")
            salary_el = card.select_one(".salary-snippet-container")

            if title_el:
                href = title_el.get("href", "")
                vagas.append(Vaga(
                    title=title_el.get_text(strip=True),
                    company=company_el.get_text(strip=True) if company_el else None,
                    location=location_el.get_text(strip=True) if location_el else "",
                    salary=salary_el.get_text(strip=True) if salary_el else None,
                    source=self.name,
                    url=f"https://br.indeed.com{href}" if href.startswith("/") else href,
                ))
        return vagas

    async def crawl(self) -> list[Vaga]:
        html = await fetch_rendered_html(self.SEARCH_URL, self.WAIT_SELECTOR, timeout=20000)
        if not html:
            log.warning("Indeed blocked — skipping")
            return []
        return self.parse(html)
```

**Step 5: Rodar teste (se fixture existe)**

Run: `cd /home/mateus-leite/Documents/vagas-medicas && pytest tests/test_spiders/test_indeed.py -v`
Expected: PASS ou SKIPPED

---

## Task 8: Spider Vagas.com.br (Playwright + stealth, best-effort)

**Nota: Vagas.com tem Cloudflare. Best-effort igual ao Indeed.**

**Files:**
- Create: `src/vagas/spiders/vagas_com.py`
- Create: `tests/fixtures/vagas_com_page.html`
- Create: `tests/test_spiders/test_vagas_com.py`

Segue exatamente o mesmo padrão da Task 7:

**Step 1:** Capturar HTML com `fetch_rendered_html('https://www.vagas.com.br/vagas-de-medico', '.informacoes-header', timeout=20000)`. Se bloqueado pelo Cloudflare, pular.
**Step 2:** Analisar seletores (se capturou)
**Step 3:** Escrever teste com `skipif` (mesma estrutura do Indeed)
**Step 4:** Implementar spider (mesma estrutura: parse + crawl com fallback para `[]`)
**Step 5:** Rodar teste

---

## Task 9: Spider Trabalha Brasil (Playwright + stealth)

**Files:**
- Create: `src/vagas/spiders/trabalha_brasil.py`
- Create: `tests/fixtures/trabalha_brasil_page.html`
- Create: `tests/test_spiders/test_trabalha_brasil.py`

**Step 1:** Capturar HTML com `fetch_rendered_html('https://www.trabalhabrasil.com.br/vagas-de-emprego/medico', '.job-card', timeout=20000)`. Tem reCAPTCHA v3 — stealth pode ou não passar.
**Step 2:** Analisar seletores
**Step 3:** Escrever teste com `skipif`
**Step 4:** Implementar spider
**Step 5:** Rodar teste

---

## Task 10: CLI para rodar todos os spiders

**Files:**
- Create: `src/vagas/cli.py`

**Step 1: Implementar CLI**

```python
# src/vagas/cli.py
import argparse
import asyncio
import logging
import os

from vagas.db import VagaDB
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


async def run(spider_names: list[str] | None = None, dry_run: bool = False):
    spiders = ALL_SPIDERS
    if spider_names:
        spiders = [s for s in ALL_SPIDERS if s.name in spider_names]

    if not spiders:
        log.error("No spiders matched. Available: %s", [s.name for s in ALL_SPIDERS])
        return

    db = None
    if not dry_run:
        dsn = os.environ.get("DATABASE_URL")
        if not dsn:
            log.error("DATABASE_URL not set. Use --dry-run to skip DB.")
            return
        db = VagaDB(dsn)
        await db.connect()
        await db.setup_tables()

    total_new = 0
    total_dupes = 0

    for spider_cls in spiders:
        spider = spider_cls()
        log.info("[%s] Crawling...", spider.name)
        try:
            vagas = await spider.crawl()
            log.info("[%s] Found %d vagas", spider.name, len(vagas))

            if dry_run:
                for v in vagas[:5]:
                    print(f"  - {v.title} | {v.location} | {v.salary or 'N/A'}")
                if len(vagas) > 5:
                    print(f"  ... and {len(vagas) - 5} more")
            elif vagas:
                new = 0
                for v in vagas:
                    if await db.upsert_vaga(v):
                        new += 1
                dupes = len(vagas) - new
                total_new += new
                total_dupes += dupes
                log.info("[%s] Inserted %d new, %d duplicates", spider.name, new, dupes)

        except Exception:
            log.exception("[%s] Failed", spider.name)

    if db:
        await db.close()

    log.info("Done. Total: %d new vagas, %d duplicates skipped.", total_new, total_dupes)


def main():
    parser = argparse.ArgumentParser(description="Crawler de vagas médicas")
    parser.add_argument("spiders", nargs="*", help="Spiders to run (default: all)")
    parser.add_argument("--dry-run", action="store_true", help="Print vagas without saving to DB")
    args = parser.parse_args()
    asyncio.run(run(args.spiders or None, args.dry_run))


if __name__ == "__main__":
    main()
```

**Step 2: Testar dry run com spider que funciona**

Run: `cd /home/mateus-leite/Documents/vagas-medicas && vagas vagamedica --dry-run`
Expected: Lista de vagas impressas no terminal.

**Step 3: Testar com banco**

Run: `cd /home/mateus-leite/Documents/vagas-medicas && DATABASE_URL="postgresql://..." vagas vagamedica`
Expected: Vagas inseridas no banco.

**Step 4: Testar todos os spiders**

Run: `cd /home/mateus-leite/Documents/vagas-medicas && vagas --dry-run`
Expected: Todos os spiders rodam. BNE e VagaMedica retornam vagas. Indeed/Vagas.com/TrabalhaBrasil retornam vagas ou log de warning se bloqueados.

---

## Task 11: Teste de integração end-to-end

**Step 1: Rodar todos os spiders contra o banco real**

Run: `cd /home/mateus-leite/Documents/vagas-medicas && DATABASE_URL="postgresql://..." vagas`

**Step 2: Verificar resultados no banco**

Run:

```bash
cd /home/mateus-leite/Documents/vagas-medicas && DATABASE_URL="postgresql://..." python3 -c "
import asyncio, os
import psycopg.rows
from vagas.db import VagaDB

async def check():
    db = VagaDB(os.environ['DATABASE_URL'])
    await db.connect()
    async with db.conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
        await cur.execute('SELECT source, COUNT(*) as total FROM vagas GROUP BY source ORDER BY total DESC')
        for row in await cur.fetchall():
            print(f'{row[\"source\"]}: {row[\"total\"]} vagas')
        await cur.execute('SELECT COUNT(*) as total FROM vagas')
        total = await cur.fetchone()
        print(f'\nTotal: {total[\"total\"]} vagas')
    await db.close()

asyncio.run(check())
"
```

Expected: Contagem de vagas por fonte. **Critério mínimo: 2+ fontes com vagas reais no banco.**

---

## Notas importantes para implementação

1. **Tasks 5-9 são parcialmente exploratórias.** Seletores CSS e formatos de API precisam ser descobertos ao vivo. O plano dá o esqueleto — os detalhes vêm da investigação.

2. **Comece sempre capturando o HTML/JSON real** e salvando como fixture antes de escrever o parser. Isso garante testes offline.

3. **Indeed e Vagas.com são best-effort.** Se o stealth não passar, skip e siga. O objetivo da POC é validar o approach, não ter cobertura total.

4. **Não otimize ainda.** Sem paginação, sem paralelismo, sem retry. POC = uma página por fonte já valida o conceito.

5. **Ordem de implementação por chance de sucesso:** BNE (API) > VagaMedica (HTML estático) > Trabalha Brasil (reCAPTCHA v3) > Vagas.com (Cloudflare) > Indeed (anti-bot agressivo).
