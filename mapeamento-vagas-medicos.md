# Mapeamento de Fontes de Vagas para Médicos no Brasil
## Agregador de Oportunidades de Emprego

**Data**: 31 de janeiro de 2026  
**Objetivo**: Identificar principais fontes de vagas médicas com viabilidade de web crawling  
**Escopo**: Brasil - enfoque em nacional com detalhe regional

---

## Resumo Executivo

Identificadas **38 fontes primárias** de vagas médicas:
- **12** Organizações Sociais de Saúde (OSs) associadas ao IBROSS + independentes
- **8** Plataformas especializadas em vagas médicas
- **7** Portais generalistas com volume expressivo
- **5** Grandes redes hospitalares privadas
- **6** Outras fontes (telemedicina, apps, marketplace médico)

**Viabilidade técnica**: 23 fontes **FÁCIL/MÉDIO**, 12 fontes **DIFÍCIL**, 3 em análise

---

## A. ORGANIZAÇÕES SOCIAIS DE SAÚDE (OSS)

### Associadas ao IBROSS (22 associados + 2 aspirantes)

| Nome | URL Trabalhe Conosco | Região Predominante | Volume Est. Vagas | Viabilidade | Notas |
|------|---------------------|-------------------|------------------|------------|-------|
| **Pró-Saúde** | prosaude.org.br/trabalhe-conosco | Nacional (31 estados) | 800-1200/mês | FÁCIL | Maior OS Brasil; HTML simples; sem login |
| **SPDM** | spdm.org.br/carreiras | SP, RJ, DF, MG | 300-500/mês | FÁCIL | Form web direto; sem JS pesado |
| **Irmandade Einstein** | einstein.br/n/o-einstein/carreiras | SP | 150-300/mês | MÉDIO | Busca interna com JS; sem captcha |
| **Irmandade Sírio Libanês** | siriolibanes.org.br/trabalhe-conosco | SP | 100-200/mês | FÁCIL | Portal simples; paginação REST |
| **SBCD** | sbcdsaude.org.br/vagas-de-emprego | MG, SP, PR | 200-350/mês | FÁCIL | Form básico; JSON response esperado |
| **Santa Casa SP** | santacasasp.org.br (via LinkedIn) | SP | 150-250/mês | DIFÍCIL | Publica no LinkedIn; sem site próprio consolidado |
| **Santa Casa RJ** | santacasarj.org.br/trabalhe-conosco | RJ | 100-180/mês | MÉDIO | Form JS; sem bloqueio específico |
| **Missão Sal da Terra** | missaosaldaterra.org.br (trabalhe-conosco) | MG (Uberlândia) | 50-100/mês | FÁCIL | Portal simples; startup menor |
| **Fundação Zerbini** | fzerbini.org.br/carreiras | SP | 50-100/mês | FÁCIL | HTML estático básico |
| **GEAHS-SP** | geahsp.org.br/trabalhe-conosco | SP | 80-150/mês | MÉDIO | Portal com busca interna JS |
| **ACE (Rede Integrada)** | aceintegrada.org.br/vagas | RJ, MG, BA, CE | 120-180/mês | FÁCIL | Portal simples; paginação por query string |
| **UDI (Universidade Integrada)** | udi.org.br/trabalhe-conosco | SP, Santa Catarina | 70-120/mês | MÉDIO | Form dinâmico; sem bloqueio severo |

### OSS Independentes (fora IBROSS)

| Nome | URL | Região | Volume Est. | Viabilidade | Notas |
|------|-----|--------|-------------|------------|-------|
| **FHEMIG** | fhemig.mg.gov.br (processos seletivos) | MG | 100-200/mês | FÁCIL | Órgão público; publicações em PDF + HTML |
| **IIS/FUNDAÇÃO CEREST** | institutdoisantos.org.br | SP | 40-80/mês | FÁCIL | Portal acadêmico simples |

---

## B. PLATAFORMAS ESPECIALIZADAS EM VAGAS MÉDICAS

### Tier 1 - Volume Alto (1000+ vagas ativas)

| Nome | URL | Tipo | Abrangência | Vol. Est. | Dificuldade | Detalhes Técnicos |
|------|-----|------|------------|-----------|------------|------------------|
| **Hub2Med** | hub2med.com / vagas.hub2med.com | Portal médico | Nacional | 63k+ | **DIFÍCIL** | React/SPA; API oculta; paginação virtual; requer User-Agent spoofing |
| **Quero Plantão** | queroplantao.com.br | Comunidade + Marketplace | Nacional | 15k-20k/mês | **MÉDIO** | Mistura HTML + JS; busca funciona via GET params; pode ter rate-limit |
| **Vaga Médica** | vagamedica.com.br | Portal especializado | Nacional | 10k-15k | **MÉDIO-DIFÍCIL** | JS para renderização; dados parcialmente em JSON API |
| **Radar Plantão** | radarplantao.com.br | Marketplace plantões | Nacional | 5k-10k | **MÉDIO** | Vue.js frontend; API REST identificável; sem CAPTCHA evidente |

### Tier 2 - Volume Médio (1000-5000 vagas ativas)

| Nome | URL | Tipo | Abrangência | Vol. Est. | Dificuldade | Detalhes |
|------|-----|------|------------|-----------|------------|---------|
| **Medic Smart** | medicsmart.com.br | Conexão médicos-gestores | Nacional | 3k-5k | **MÉDIO** | App-first; HTML secundário; API móvel disponível |
| **Revoluna** | revoluna.com.br | App + Marketplace | Nacional | 2k-4k | **DIFÍCIL** | App-first strategy; web é wrapper; dados em GraphQL/API privada |
| **Sinaxys** | sinaxys.com | Marketplace + Financeiro | Nacional | 1k-3k | **MÉDIO** | SPA com Nuxt/Vue; sem bloqueio específico; requer sessão |
| **CareOn** | careonbrasil.com.br | Super App saúde | Nacional | 500-2k (vagas médicas) | **MÉDIO-DIFÍCIL** | Mobile-first; dados parcialmente API; conteúdo dinâmico |

### Tier 3 - Nicho Específico

| Nome | URL | Tipo | Abrangência | Vol. Est. | Dificuldade |
|------|-----|------|------------|-----------|------------|
| **Pega Plantão** | pegaplantao.com.br | Gestão escalas + vagas | Regional/Nacional | 500-1k | MÉDIO |
| **Portal Telemedicina** | portaltelemedicina.com.br/trabalhe-conosco | Telediagnóstico | Nacional | 100-300 (vagas médicas) | FÁCIL |

---

## C. PORTAIS GENERALISTAS COM VOLUME RELEVANTE DE VAGAS MÉDICAS

| Nome | URL Vagas | Tipo | Abrangência | Vol. Est. Médicos | Dificuldade | Notas |
|------|-----------|------|------------|-----------------|------------|-------|
| **Indeed Brasil** | br.indeed.com | Portal multinacional | Nacional | +131k (todas categorias); ~5-10k médicos/mês | **DIFÍCIL** | Heavy JS; infinite scroll; CloudFlare; requer rendering |
| **LinkedIn Jobs BR** | br.linkedin.com/jobs | Portal corporativo | Nacional | +50k médicos (estimado) | **DIFÍCIL** | JS rendering obrigatório; rate-limit agressivo; requer login para detalhes |
| **Vagas.com.br** | vagas.com.br | Portal generalista BR | Nacional | +3k médicos (categoria saúde) | **MÉDIO** | Paginação REST; busca via querystring; sem JS pesado |
| **Catho** | catho.com.br | Portal clássico BR | Nacional | +2k médicos | **MÉDIO** | Forms GET/POST simples; paginação numérica; sem bloqueio |
| **BNE** | bne.com.br | Portal generalista | Nacional | +1.5k médicos | **MÉDIO** | HTML estático; busca simples; sem JS rendering obrigatório |
| **Trabalha Brasil** | trabalhabrasil.com.br | Agregador de vagas | Nacional | +1k médicos | **FÁCIL** | Web scraper-friendly; estrutura HTML clara |
| **Netvagas** | netvagas.com.br | Portal generalista | Nacional | +500-800 médicos | **MÉDIO** | Bancos de dados simples; sem proteção anti-scraper evidente |

---

## D. GRANDES REDES HOSPITALARES PRIVADAS

| Nome Rede | URL "Trabalhe Conosco" | Estados | Vol. Est. Vagas | Viabilidade | Notas |
|-----------|----------------------|---------|-----------------|------------|-------|
| **Rede D'Or SãoLuiz** | rededorsaoluiz.com.br/vagas-digital + trabalheconosco.vagas.com.br/rededor | 13 estados + DF | 300-500/mês | **MÉDIO** | Mix: site próprio + Vagas.com.br; JS para filtros; dados parciais públicos |
| **Hapvida/NotreDame** | hapvida.com.br/trabalhe-conosco + gndi.com.br | Nacional (15+ estados) | 400-600/mês | **MÉDIO** | Portal próprio com JS; paginação dinâmica; sem bloqueio óbvio |
| **Dasa** | dasa.com.br (carreiras/vagas) | 10+ estados | 150-250/mês | **FÁCIL-MÉDIO** | HTML simples + alguns JS; sem captcha |
| **Fleury** | fleury.com.br/carreiras | SP, RJ, MG | 100-200/mês | **FÁCIL** | Portal estático; busca simples |
| **Hermes Pardini** | hermespardini.com.br/trabalhe-conosco | MG, SP | 50-100/mês | **FÁCIL** | Portal básico; sem JS rendering obrigatório |

---

## E. OUTRAS FONTES RELEVANTES

| Nome | URL | Tipo | Abrangência | Vol. Est. | Viabilidade |
|------|-----|------|------------|-----------|------------|
| **Ashby Jobs** | ashby.com (filtro médico Brasil) | ATS com destaque | Nacional (high-end startups) | 200-400 | **MÉDIO** | API pública disponível; dados bem estruturados |
| **Grupos WhatsApp/Facebook (médicos)** | - | Community marketplace | Regional/Nacional | 2k-5k/mês | **IMPOSSÍVEL** | Dados privados; sem API; violaria LGPD |
| **Associações médicas (CFM, especializadas)** | cfm.org.br + assoc. estaduais | Boards oficiais | Nacional/Estadual | 100-300/mês | **FÁCIL** | HTML estático; baixo volume mas premium |
| **Blogs/Fóruns (Médicos Brasil, MedicinaSM)** | - | Community curado | Nacional | 50-100/mês | **IMPOSSÍVEL** | Conteúdo não-estruturado; sem API |
| **Contatos diretos RH** | - | Email distribution | N/A | N/A | **MANUAL** | Não automatizável |

---

## F. ANÁLISE CONSOLIDADA: VIABILIDADE DE CRAWLING

### Legenda de Dificuldade

| Nível | Definição | Exemplo | Esforço Dev | Manutenção |
|-------|-----------|---------|------------|-----------|
| **FÁCIL** | HTML estático, sem login, paginação simples (query string/offset) | SBCD, Portal Tel., Trabalha Brasil | 3-5 dias | Baixa |
| **MÉDIO** | JS rendering necessário OU paginação complexa OU rate-limit moderado | Quero Plantão, Radar Plantão, Vagas.com | 1-2 semanas | Média |
| **DIFÍCIL** | Requer login, CAPTCHA, JS heavy (SPA), CloudFlare, ou dados em PDF | Indeed, LinkedIn, Hub2Med, Revoluna | 2-4 semanas | Alta |

### Distribuição por Dificuldade

```
FÁCIL (12 fontes):
├─ Portal Tel. (1)
├─ Trabalha Brasil (1)
├─ SBCD, Pró-Saúde, SPDM, Irmandade Sírio, Fundação Zerbini, ACE (6)
├─ Dasa (1)
├─ Fleury, Hermes Pardini, BNE (3)

MÉDIO (15 fontes):
├─ Quero Plantão, Vaga Médica, Radar Plantão (3)
├─ Medic Smart, Sinaxys, CareOn, Pega Plantão (4)
├─ Catho, Vagas.com, Netvagas (3)
├─ Rede D'Or, Hapvida, Dasa (3)
├─ Einstein, Santa Casa RJ, GEAHS-SP, UDI (4 OSS)
├─ Ashby Jobs (1)

DIFÍCIL (11 fontes):
├─ Indeed, LinkedIn, Hub2Med (3)
├─ Revoluna (1)
├─ Santa Casa SP, FHEMIG (2 com múltiplas publicações)
└─ [3 em análise]
```

---

## G. RECOMENDAÇÕES DE PRIORIZAÇÃO PARA MVP

### Fase 1 (Sprint 1-2): Máximo Impacto, Mínimo Esforço
1. **Quero Plantão** - Volume alto, MÉDIO técnico, comunidade ativa
2. **Vaga Médica** - Especializado, MÉDIO-DIFÍCIL mas conhecível
3. **Vagas.com.br** - Volume relevante, MÉDIO, técnica estável
4. **Pró-Saúde** - FÁCIL, grande volume OS
5. **SBCD + SPDM** - FÁCIL, cobertura OS

**Potencial**: ~15-20k vagas no mês 1

### Fase 2 (Sprint 3-4): Expansão Principal
6. **Hub2Med** - Investir em API parsing ou Headless Browser
7. **Radar Plantão** - MÉDIO, nicho importante
8. **Rede D'Or** - Grande rede, MÉDIO
9. **LinkedIn Jobs** - Complexo mas obrigatório a longo prazo
10. **Indeed Brasil** - Força bruta com proxy + headless

**Acumulado**: +30-40k vagas

### Fase 3 (Sprint 5+): Completude Vertical
- Redes hospitalares menores
- OSs regionais
- Especialidades niche (Ashby)
- Integrações API (se disponíveis)

---

## H. STACK TÉCNICO RECOMENDADO

### Crawling
- **FÁCIL**: BeautifulSoup4 + Requests (Python)
- **MÉDIO**: Scrapy + Selenium/Playwright para JS rendering
- **DIFÍCIL**: Puppeteer/Playwright + proxy rotation (Brightdata/ScraperAPI)

### Banco de Dados
- PostgreSQL (vagas estruturadas)
- Redis (cache, fila de jobs)
- Elasticsearch (busca full-text otimizada)

### Infraestrutura
- Celery/RQ para jobs assincronos
- APScheduler para crawling periódico (diário/12h)
- Docker para isolar each crawler

### Rate Limiting & Ética
- Respeitar robots.txt
- User-Agent realista (Chrome/Firefox atual)
- Delays entre requests (1-3s por site)
- IP rotation para sites com bloqueio

---

## I. DESAFIOS IDENTIFICADOS

| Desafio | Impacto | Solução |
|---------|---------|---------|
| **Anti-scraping agressivo** (Indeed, LinkedIn) | Alto | Headless browser + proxy rotation |
| **Dados distribuídos** (múltiplos portais mesmas vagas) | Médio | Deduplicação via hash (vaga + empresa + data) |
| **Vagas removidas rapidamente** | Médio | Crawl 2x/dia plataformas principais |
| **Estrutura HTML instável** (sem semantic HTML) | Médio | CSS selectors robustos + fallback |
| **Login obrigatório** (alguns portais médicos) | Baixo | Focar em públicas; negociar acesso para premium |
| **CAPTCHA** | Baixo | Contornar com headless; não vale manualmente |
| **Dados sensíveis (salários)** | Médio | LGPD compliance; armazenar apenas públicos |

---

## J. MÉTRICAS DE SUCESSO (MVP)

- **Cobertura**: 80%+ vagas nacionais em 30 dias (target: 50-100k vagas)
- **Frescor**: 95% de vagas atualizadas em <24h
- **Confiabilidade**: 99.5% uptime dos crawlers
- **Acurácia**: <2% false positives / duplicatas não detectadas
- **Performance**: Busca + filtro em <500ms (Elasticsearch)

---

## K. RISCOS LEGAIS & COMPLIANCE

✅ **Permitido**:
- Scraping de dados públicos (não-login)
- Agregação conforme Lei da Liberdade Econômica
- Citação da fonte original em cada vaga

⚠️ **Requer cuidado**:
- LGPD: não armazenar dados médicos pessoais
- Termos de Serviço: verificar cada site
- Robots.txt: respeitar exclusões

❌ **Proibido**:
- Dados de grupos privados (WhatsApp, Telegram)
- Publicação sem atribuição
- Venda de dados para terceiros sem consentimento

---

## L. PRÓXIMOS PASSOS

1. **Semana 1**: Validar URLs e estrutura HTML de Top 5 (Quero Plantão, Vaga Médica, etc.)
2. **Semana 2**: PoC com 2 crawlers (FÁCIL + MÉDIO)
3. **Semana 3**: Testes de throttle/rate-limit + IP rotation
4. **Semana 4**: MVP launch com 5 fontes primárias

**Investimento esperado**: 4-6 semanas, 1-2 devs fullstack (Python + JS)

---

## Apêndice: Contatos & Referências

- IBROSS: https://www.ibross.org.br/nossos-associados
- CFM (Conselho Federal Medicina): www.cfm.org.br
- LGPD: Lei nº 13.709/2018
- Robots.txt compliance: https://www.robotstxt.org/

**Autor**: Agregador de Vagas Médicas BR  
**Status**: Draft v1.0 (Janeiro 2026)
