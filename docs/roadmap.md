# Roadmap — Agregador de Vagas Médicas

## Fontes de dados

### Ativas
| Fonte | Volume | Método | Dados extraídos |
|-------|--------|--------|-----------------|
| **Indeed** | ~117/exec | Mosaic JS (multi-query, browser fresco/query) | título, empresa, local, salário (estruturado), tipo, benefícios, snippet, especialidade |
| **Vagas.com** | ~40/exec | Browser + HTML parsing | título, empresa, local, descrição, tipo, raw_html |

### Quebradas (consertar)
| Fonte | Problema | Ação |
|-------|----------|------|
| **BNE** | API retorna 403 | Investigar — pode precisar de browser ou headers diferentes |
| **TrabalhaBrasil** | reCAPTCHA v3 bloqueia | Baixa prioridade — difícil de contornar |

### A dropar
| Fonte | Motivo |
|-------|--------|
| **VagaMédica** | Sem data de publicação, vagas expiradas, sem empresa, sem ID, URLs WhatsApp |

### Futuras (roadmap)
| Fonte | Prioridade | Notas |
|-------|-----------|-------|
| **Catho** | Alta | 360k+ empresas, grande volume de vagas médicas |
| **InfoJobs** | Alta | 46M candidatos, boa cobertura |
| **Gupy** | Média | 4k+ empresas, muito usado em hospitais |
| **LinkedIn** | Baixa | API restrita, scraping arriscado (ToS) |

## Enriquecimento de dados

### Fase 1: Normalização determinística (sem IA)
- Normalizar especialidades com dicionário (`"GINECOLOGISTA"` → `"Ginecologista"`, `"Pediatra UAPS"` → `"Pediatra"`)
- Padronizar localizações
- Filtrar ruído (vagas não-médicas que passam pelo filtro)

### Fase 2: Enriquecimento com IA (Gemini 2 Flash — free tier)
- Extrair do snippet/descrição: regime (CLT/PJ/plantão), carga horária, requisitos (RQE, residência, experiência)
- Classificar setting (hospital, UBS, ambulatório, home care, telemedicina)
- Genérico para todas as fontes
- ~200 vagas × ~200 tokens = ~40K tokens/exec → cabe folgado no free tier (1M tokens/dia)

## Próximos passos (em ordem)
1. ~~Documentar roadmap~~ (este arquivo)
2. Consertar Vagas.com — filtro de ruído, qualidade de dados
3. Investigar BNE — testar abordagem alternativa
4. Implementar normalização determinística
5. Implementar enriquecimento com Gemini Flash
6. Adicionar Catho e InfoJobs
