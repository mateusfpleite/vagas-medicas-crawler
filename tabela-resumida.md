# Tabela Resumida: Viabilidade de Crawling

## Ranking de Priorização (Top 20)

| Posição | Nome | Tipo | Vol. Estimado | Dificuldade | Impacto Técnico | Score |
|---------|------|------|---------------|------------|-----------------|-------|
| 1 | **Quero Plantão** | Marketplace médico | 15-20k/mês | MÉDIO | Alto | 9.2/10 |
| 2 | **Hub2Med** | Portal especializado | 63k+ | DIFÍCIL | Alto (mas vale) | 8.8/10 |
| 3 | **Pró-Saúde** | OS | 800-1.2k/mês | FÁCIL | Médio | 8.5/10 |
| 4 | **Vaga Médica** | Portal médico | 10-15k | MÉDIO-DIFÍCIL | Médio | 8.3/10 |
| 5 | **Indeed Brasil** | Portal generalista | 5-10k médicos/mês | DIFÍCIL | Alto | 8.0/10 |
| 6 | **Vagas.com.br** | Portal generalista | 3k | MÉDIO | Médio | 7.8/10 |
| 7 | **Radar Plantão** | Marketplace plantões | 5-10k | MÉDIO | Médio-Alto | 7.5/10 |
| 8 | **LinkedIn Jobs BR** | Social profissional | 50k+ (geral) | DIFÍCIL | Alto | 7.3/10 |
| 9 | **Rede D'Or** | Rede hospitalar | 300-500/mês | MÉDIO | Médio | 7.0/10 |
| 10 | **SBCD** | OS | 200-350/mês | FÁCIL | Baixo | 6.9/10 |
| 11 | **Hapvida/NotreDame** | Rede hospitalar | 400-600/mês | MÉDIO | Médio | 6.8/10 |
| 12 | **SPDM** | OS | 300-500/mês | FÁCIL | Médio | 6.7/10 |
| 13 | **Catho** | Portal generalista | 2k | MÉDIO | Médio | 6.5/10 |
| 14 | **Medic Smart** | Marketplace | 3-5k | MÉDIO | Médio | 6.3/10 |
| 15 | **Sinaxys** | Marketplace | 1-3k | MÉDIO | Médio | 6.0/10 |
| 16 | **Einstein** | OS | 150-300/mês | MÉDIO | Médio | 5.8/10 |
| 17 | **BNE** | Portal generalista | 1.5k | MÉDIO | Baixo-Médio | 5.5/10 |
| 18 | **Trabalha Brasil** | Agregador | 1k | FÁCIL | Baixo | 5.3/10 |
| 19 | **Dasa** | Rede hospitalar | 150-250/mês | FÁCIL-MÉDIO | Médio | 5.2/10 |
| 20 | **Netvagas** | Portal generalista | 500-800 | MÉDIO | Médio | 5.0/10 |

---

## Quick Reference: Dificuldade Técnica

### ✅ FÁCIL (8-12 horas por fonte)
```
Pró-Saúde
SBCD
SPDM
Trabalha Brasil
Dasa (básico)
Fleury
Hermes Pardini
Portal Telemedicina
```

**Stack**: BeautifulSoup4 + Requests + Regex
**Deployment**: Simples, baixa manutenção

### ⚠️ MÉDIO (1-2 semanas por fonte)
```
Quero Plantão
Vaga Médica
Vagas.com.br
Radar Plantão
Catho
Medic Smart
Sinaxys
CareOn
Rede D'Or
Hapvida
Einstein
Santa Casa RJ
BNE
Netvagas
```

**Stack**: Scrapy + Playwright/Selenium + Proxy
**Deployment**: Moderate, requer manutenção mensal (~4h/mês)

### 🔴 DIFÍCIL (2-4 semanas por fonte)
```
Hub2Med
Indeed Brasil
LinkedIn Jobs
Revoluna
Santa Casa SP
FHEMIG
Ashby (se bloqueado)
```

**Stack**: Puppeteer/Headless Chrome + IP Rotation + Handling anti-bot
**Deployment**: Complexo, alta manutenção (10-15h/mês)

---

## Recomendação de MVP (30 dias)

### Sprint 1-2: Foundation (Week 1-2)
**Objetivo**: 10-15k vagas, prova de conceito
- ✅ Pró-Saúde (800/mês) - FÁCIL
- ✅ Quero Plantão (15-20k/mês) - MÉDIO
- ✅ Vaga Médica (10-15k) - MÉDIO
- ✅ SBCD (200/mês) - FÁCIL
- ✅ SPDM (300/mês) - FÁCIL

**Investimento**: ~80 horas dev

### Sprint 3-4: Expansion (Week 3-4)
**Objetivo**: +20-30k vagas, cobertura completa
- ✅ Vagas.com.br (3k) - MÉDIO
- ✅ Radar Plantão (5-10k) - MÉDIO
- ✅ Rede D'Or (300-500/mês) - MÉDIO
- ✅ Hub2Med (63k+) - DIFÍCIL
- ⚠️ Indeed Brasil - DIFÍCIL (baixa prioridade se MVP bem-sucedido)

**Investimento**: ~120 horas dev

**Total MVP**: ~200 horas = 5 semanas (1 dev fullstack) ou 2.5 semanas (2 devs)

---

## Deduplicação & Matching

**Desafio**: Mesma vaga aparece em múltiplos portais

**Estratégia**:
1. Hash: SHA-256(company + speciality + location + date_posted)
2. Similarity: Fuzzy match título+descrição (80%+ threshold)
3. Canonical URL: Preferir fonte primária (site hospital > portal genérico)

**Impacto**: Redução de ~20-30% de duplicatas esperada

---

## Monitoramento & Alertas

| Métrica | Target | Alert If |
|---------|--------|----------|
| Vagas novas/dia | 5-10k | <2k ou >20k (anomalia) |
| Crawl success rate | 95%+ | <90% |
| Avg crawl time | <5min por site | >10min |
| Data freshness | <24h | >48h |
| Duplicatas detectadas | <5% | >10% |

---

## Contatos Estratégicos para Negociação (Fase 2)

| Plataforma | Contato | Objetivo | Prioridade |
|-----------|---------|----------|-----------|
| Hub2Med | partners@hub2med.com | API access, partnership | ALTA |
| Quero Plantão | comercial@queroplantao.com | Feed/API, co-marketing | ALTA |
| Indeed Brasil | BR-business-team@indeed.com | Data feed partnership | MÉDIA |
| Pró-Saúde | parceiros@prosaude.org.br | Dados estruturados | MÉDIA |
| LinkedIn | enterprise-sales@linkedin.com | Official jobs API | BAIXA (custoso) |

---

## Estimativa de Retorno

| Milestone | Semanas | Vagas Acumuladas | Usuários Target | ROI |
|-----------|---------|-----------------|-----------------|-----|
| MVP v1 | 4-5 | 20-30k | 500-1k | Baixo (prove concept) |
| v1.1 Expansão | +2 | 50-80k | 2-3k | Médio |
| v2 Completa | +4 | 100-150k | 5-10k | Alto |
| v3 Premium | +6 | 150k+ | 10k+ | Muito Alto |

**Break-even**: ~3 meses com modelo freemium + premium
**Custo operacional**: ~$1-2k/mês (infra + proxies)

