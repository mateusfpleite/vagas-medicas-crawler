# Source Strategy

## Mission & Positioning

**Mission**: Be the most reliable place for Brazilian doctors to find job postings — especially recent graduates struggling to navigate a fragmented market.

**Positioning**: A medical job aggregator that wins on two fronts:
- **Completeness** — Aggregate from every relevant source so doctors don't need to check 10 different sites
- **Trust** — Every posting has a real employer, clear location, and is confirmed to be for a physician. No spam, no ghosts.

**Not competing on**: Being a recruiter platform, salary negotiation, or employer tools (yet). The first goal is traffic through organic word-of-mouth driven by genuinely useful, high-quality listings.

**Future vision**: Once traffic exists, layer in community features (networking, experience sharing, mentorship for recent graduates). But community without traffic is dead — postings come first.

## Quality Standards

Every posting displayed on the site must meet these minimum quality bars:

| Criterion | Required? | How we enforce it |
|-----------|-----------|-------------------|
| Job is for a physician | **Yes** | Normalize specialty + AI enrichment filters non-medical postings |
| Clear location (city + state, or "Remoto") | **Yes** | Reject postings with only vague regions. "Remoto" is valid — remote consultations are a real and growing category |
| Identified employer | **Yes** | Filter out "Confidencial" or anonymous postings, or flag them visually as lower trust |
| Job is current (not stale) | **Yes** | Frontend shows newest first; backend tracks `published_at` and can expire postings after N days without re-crawl |
| Salary/compensation info | Nice-to-have | Display when available, but absence doesn't disqualify a posting |

**Deduplication**: The same job often appears on multiple boards. The current `dedup_key` (SHA256 of title+company+location) handles exact matches. As source data reliability improves, cross-source fuzzy dedup becomes a natural next step.

**Freshness strategy**: A posting that hasn't been re-seen by any spider in 30 days should be automatically hidden (not deleted — it may come back). This prevents the "graveyard" effect of stale listings that kills trust.

## Source Strategy (Layered Approach)

### Layer 1: Baseline — Capital Coverage (current focus)

Ensure solid coverage across all 27 state capitals. This makes the site feel complete and useful to any doctor in Brazil.

**Current state**: Heavy SP/RJ bias. Many capitals have zero postings.

**Goal**: At least some postings in every capital. New sources should be evaluated partly on whether they add geographic diversity.

### Layer 2: Differentiator — Underserved Regions

What no competitor does well. Sources that surface jobs in interior cities, municipal health systems, UBS networks, government programs.

**Why this matters**: Doctors in smaller cities have fewer options to discover opportunities. Being the only platform that reliably surfaces these makes us indispensable for a segment that has no alternative.

**Key interior metro hubs to target**: Uberlandia/MG, Ribeirao Preto/SP, Londrina/PR, Ipatinga/MG, Campinas/SP, Sao Jose dos Campos/SP, Juiz de Fora/MG, Joinville/SC, Sorocaba/SP, Feira de Santana/BA.

### Layer 3: Don't Over-Invest — Sao Paulo/RJ

Current spiders already cover the big metros well. New spider development should not prioritize adding more SP/RJ volume — focus effort on sources that fill geographic gaps.

### Source Selection Criteria

When evaluating a new source, score it on:

1. **Geographic diversity** — Does it add cities/states we're weak on?
2. **Data quality** — Does it provide employer name, location, freshness date?
3. **Volume** — How many physician postings does it have?
4. **Overlap** — How much of its content do we already capture from other spiders?
5. **Technical feasibility** — API available? Scrapable HTML? Anti-bot defenses?

## Source Roadmap

### Currently Active

| Source | Strength | Weakness |
|--------|----------|----------|
| Indeed | High volume (~44%) | SP-heavy, stale postings common, aggregates other sources |
| BNE | Good volume (~40%) | Similar geographic bias, data completeness varies |
| InfoJobs | Moderate volume (~9%) | Smaller pool |
| Vagas.com | Low volume (~7%) | Few postings, but data quality tends to be good |

### Currently Inactive

| Source | Why inactive | Worth revisiting? |
|--------|-------------|-------------------|
| TrabalhaBrasil | Blocked by reCAPTCHA v3 | Maybe — with proxy it could work now |
| VagaMedica | WhatsApp-based links, low quality | Yes — spider exists, retest and activate if data quality improved |

### Implementation Roadmap (prioritized)

| # | Source | Type | Effort | Impact | Notes |
|---|--------|------|--------|--------|-------|
| 1 | ~~**PCI Concursos**~~ | Concursos publicos | Low | High | **DONE** — spider ativo |
| 2 | **Gupy Portal/API** | Career pages hospitais | Low | **Very High** | API publica documentada (developers.gupy.io). Um spider cobre Hapvida, SPDM, Conexa, Sirio-Libanes, etc. Hapvida e o maior empregador do Nordeste — preenche gap regional |
| 3 | **trabalheconosco.vagas.com.br** | Career pages hospitais | Low-Medium | High | White-label Vagas.com. Rede D'Or (1.085+ vagas, maior rede privada da LatAm), Einstein, Sirio-Libanes. Mesmo formato = um spider cobre varios |
| 4 | **Sanar Med Concursos** | Agregador concursos | Medium | High | Agrega todos os concursos medicos do Brasil. Complementa PCI. SPA com API interna, precisa reverse-engineer |
| 5 | **vagamedica.com.br** | Plataforma medica | Minimal | Medium | Spider ja existe (inativo). Reativar e testar |
| 6 | **radarplantao.com.br** | Plataforma medica | Low-Medium | Medium | Portal web estruturado, plantoes/PJ, cobertura nacional |
| 7 | **RH Saude** | Portal saude | Medium | Medium | ~120 vagas medicas ativas. Portal dedicado a saude. JS-dependent (Playwright). rhsaude.com.br |
| 8 | **Solides Vagas** | ATS hospitalar | Medium | Medium | Plataforma HR brasileira crescente. Hospitais que nao usam Gupy usam Solides (ex: Unimed JP). vagas.solides.com.br |
| 9 | **Grupo Livemed** | Hospital network SP | Low | Medium | Portal dedicado a medicos em Campinas, Sorocaba, SJC, Ribeirao Preto. URL: vagas.grupolivemed.com.br |
| 10 | **Jooble API** | Agregador/discovery | Low | Low-Medium | API REST gratuita. Usar campo `source` para descobrir fontes novas, nao como spider permanente |

### Evaluated and Deferred

| Source | Verdict | Reason |
|--------|---------|--------|
| Hub2Med | **Skip — competitor** | Plataforma de staffing medico com conteudo proprietario de primeira mao. Scraping seria anticompetitivo e eticamente questionavel |
| Catho | **Defer** | Akamai Bot Manager (anti-bot pesado), login parcial. ~500-1500 vagas medicas. Jooble ja agrega Catho |
| SINE Nacional (Emprega Brasil) | **Defer** | Login Gov.br obrigatorio + CAPTCHA. Sem API publica. SPA React atras de autenticacao |
| SINEs estaduais (BA, CE) | **Defer** | Paginas publicas existem (SineBahia, IDT Ceara) mas vagas medicas sao raras no SINE |
| EBSERH (gov.br) | **Defer** | 45 hospitais universitarios, ~25 PSS/ano. Dados valiosos mas gov.br bloqueia acesso automatizado e dados detalhados estao em PDFs. PCI Concursos ja agrega editais EBSERH |
| JC Concursos | **Defer** | Similar ao PCI mas com anti-bot (403). Considerar apos PCI funcionar |
| Mais Medicos | **Defer** | Programa federal, alto valor, mas periodico (poucos editais/ano). Monitorar manualmente |
| SIMESP BEM | **Defer** | Banco de empregos do sindicato medico de SP. Cobre todo o estado de SP. Precisa investigar scrapabilidade |
| FHEMIG | **Defer** | Cobre Uberlandia, Ipatinga, Juiz de Fora. Editais estruturados. Considerar como complemento ao PCI |
| Prefeituras individuais | **Skip** | Fragmentado demais — cada uma tem formato diferente. PCI Concursos ja agrega |
| Pega Plantao | **Defer** | App de gestao de plantoes (Sirio-Libanes, HCor, Unimed-RS). Volume enorme mas conteudo atras de login. Considerar parceria/API |
| Glassdoor Brasil | **Defer** | 134k+ vagas medicas, mas anti-scraping pesado (CAPTCHA, rate limiting). Custo alto de infra |
| Escalize | **Defer** | Plataforma de plantoes com verificacao CRM. Volume publico muito baixo |
| Escala de Plantao | **Skip** | Volume minimo (1 listing visivel). WhatsApp-based |
| Quero Plantao | **Defer** | Maior comunidade de plantoes, mas conteudo via WhatsApp/Telegram. Portal web (vagas.queroplantao.com.br) e SPA — investigar API |

### Fontes Governamentais Identificadas (para futuro)

Essas fontes sao valiosas para cobertura regional mas fragmentadas. Priorizar agregadores (Sanar Med, PCI) ao inves de scraping individual.

| Source | Estado/Cidade | URL | Notes |
|--------|--------------|-----|-------|
| SESAB | Bahia | saude.ba.gov.br/educacao/processos-seletivos/ | WordPress, baixa dificuldade. Preenche gap Nordeste |
| RioSaude PSS | Rio de Janeiro | pss.riosaude.rio.br | Dezenas de especialidades. Editais em PDF |
| Prefeitura SP Selecao | Sao Paulo | capital.sp.gov.br/web/saude/selecao_publica/ | 1.300+ vagas medicas |
| SP SES Painel | Sao Paulo (estado) | saude.sp.gov.br/.../painel-de-vagas | Rede SES-SP inteira |
| SES Goias | Goias | selecao.go.gov.br | Plataforma centralizada. Gap Centro-Oeste |
| SES Parana | Parana | saude.pr.gov.br/Pagina/Editais | 84 vagas medicas em concurso recente |
| SES Santa Catarina | Santa Catarina | saude.sc.gov.br/.../processos-seletivos-ses | Alta frequencia de PSS |
| SES Minas Gerais | Minas Gerais | saude.mg.gov.br/processoseletivo/ | 2o estado mais populoso |
| AgSUS/SESAI | Nacional (indigena) | agenciasus.org.br | 671 vagas em territorios indigenas. Norte/Centro-Oeste |

### OSS e Redes Hospitalares Identificadas

Organizacoes Sociais de Saude com portais de vagas proprios. Muitas ja cobertas pelo spider Gupy.

| Source | Cobertura | Portal | Notes |
|--------|-----------|--------|-------|
| Rede D'Or | Nacional (20+ estados) | trabalheconosco.vagas.com.br/rededor | 1.085+ vagas. Maior rede privada LatAm |
| SPDM/PAIS | SP, RJ | spdmpais.gupy.io | ~100 unidades. Coberto pelo spider Gupy |
| CEJAM | SP, RJ | cejam.org.br/processo-seletivos | ESF/PSF, atencao primaria |
| ISAC | BA, GO, TO | vagas.isac.org.br | Regioes subatendidas (NE/CO/N) |
| IBSaude | Multi-estado | ibsaude.org.br/publicacoes/vagas/ | WordPress, inclui saude indigena |
| IABAS | RJ, SP | iabas.org.br | 70 vagas ESF na zona oeste do RJ |
| FESF-SUS | Bahia | fesfsus.ba.gov.br/.../editais | Saude da familia |
| Conexa Saude | Nacional (remoto) | conexasaude.gupy.io | Telemedicina. Coberto pelo spider Gupy |

### CRMs com Quadros de Vagas

| CRM | Estado | URL | Notes |
|-----|--------|-----|-------|
| CRM-PR | Parana | crmpr.org.br/Classificados... | Vagas moderadas pelo CRM. Empregadores verificados |
| CREMERS | Rio Grande do Sul | cremers.org.br/painel-de-anuncios/ | Pode precisar de login |
| CREMESP | Sao Paulo | Banco de Empregos CREMESP/APM | Parceria desde 2003. Interface web a investigar |
| CREMERN | Rio Grande do Norte | cremern.org.br/noticias/vagas-de-emprego/ | Volume muito baixo |

### Key Insight: Gupy Platform

Many hospitals and health organizations use Gupy (gupy.io) for recruitment. Each gets a standardized subdomain. Building one parametrized Gupy spider could cover dozens of hospitals by adding URLs:
- hapvidandi.gupy.io (Hapvida NotreDame Intermedica — nacional, dominante no Nordeste)
- sistemahapvida.gupy.io (Hapvida — portal alternativo)
- spdmpais.gupy.io (SPDM — SP interior + SJC)
- hmdjcf.gupy.io (Hospital Municipal SJC)
- conexasaude.gupy.io (Conexa Saude — telemedicina nacional)

**API publica documentada**: developers.gupy.io — Bearer token auth, mas portal de busca e publico. Existem scrapers open-source no GitHub.

**Portal centralizado**: portal.gupy.io/job-search permite buscar "medico" em todas as empresas de uma vez. Alternativa ao scraping por subdomain.

This is the most scalable approach for hospital career pages.

## Technical Principles for New Spiders

### Build for Reliability

- All spiders are async and implement `BaseSpider.crawl()`
- Use the proxy system — it auto-activates after 3 failures, no need to pre-configure per spider
- Each spider should handle pagination gracefully and fail silently on individual postings (one bad page shouldn't kill the whole crawl)

### Build for Quality

- Every `Vaga` must have: `title`, `location`, `source`, `url`, `company` (skip postings missing company)
- Extract `published_at` whenever available — this is critical for freshness
- Extract `external_id` from the source to enable proper upsert and re-crawl detection
- Prefer sources that give structured data (APIs, JSON-LD) over raw HTML scraping when possible

### Build for Geographic Diversity

- New spiders should parameterize location in their queries when the source supports it
- Don't just search "medico" — use the specialty list from `normalize.py` to cast a wider net
- Track which states/capitals each spider covers and identify gaps

### Freshness & Staleness

- Crawl frequency: daily for high-volume sources, every 2-3 days for smaller ones
- A posting not re-seen in 30 days gets hidden from the frontend
- `crawled_at` is already tracked — use it to power staleness logic

### Don't Duplicate Effort

- Before building a new spider, manually check overlap with existing sources (Indeed especially is an aggregator that may already include postings from smaller boards)
- If a source is mostly duplicates, it's not worth maintaining a spider for it
