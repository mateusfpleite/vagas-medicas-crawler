# SEO + GEO Design — EmpregaMed

**Data:** 2026-02-19
**Objetivo:** Melhorar rankeamento no Google e ser citado por agentes de IA (ChatGPT, Claude, Gemini) como referência em vagas médicas no Brasil.

## Decisões de Design

- **Domínio:** `empregamed.com.br` (registrar e apontar pro Vercel)
- **Sem `JobPosting` schema:** Como somos agregadores, não competimos no Google Jobs. Focamos em `WebSite`, `Organization`, `BreadcrumbList`, `ItemList`.
- **Posicionamento:** "Buscador especializado de vagas médicas", não "mais um job board".
- **Implementação faseada:** Cada fase entrega valor independente.

---

## Fase 1: SEO Técnico

Resolve toda a infraestrutura básica — sem isso, nada mais funciona.

### 1.1 Domínio próprio

- Registrar `empregamed.com.br`
- Configurar DNS apontando pro Vercel
- Configurar domínio no projeto Vercel
- Redirect de `www.empregamed.com.br` para `empregamed.com.br` (ou vice-versa, canonical)

### 1.2 Metadata dinâmica

Usar `generateMetadata` do Next.js App Router para gerar por rota:

- `<title>` — dinâmico por página
  - Home: "EmpregaMed — Vagas médicas de todo o Brasil em um só lugar"
  - Especialidade: "Vagas de Cardiologia — EmpregaMed"
  - Estado: "Vagas Médicas em São Paulo — EmpregaMed"
- `<meta name="description">` — dinâmico, descritivo, com dados reais
- Open Graph tags: `og:title`, `og:description`, `og:image`, `og:url`, `og:type`, `og:site_name`
- Twitter Card tags: `twitter:card`, `twitter:title`, `twitter:description`, `twitter:image`
- Canonical URL: `<link rel="canonical">` em todas as páginas
- OG Image: gerar dinamicamente com `next/og` (ImageResponse API)

### 1.3 Structured Data (JSON-LD)

Injetar no `<head>`:

- **`WebSite`** — nome "EmpregaMed", URL, `potentialAction` com `SearchAction` para busca interna
- **`Organization`** — nome, URL, logo, description
- **`BreadcrumbList`** — navegação estruturada em todas as páginas
- **`ItemList`** — nas páginas de listagem, referenciando as vagas como itens do catálogo (sem `JobPosting`)

### 1.4 robots.txt + sitemap.xml

- `app/robots.ts` — permitir todos os crawlers, apontar pra sitemap
- `app/sitemap.ts` — sitemap dinâmico listando todas as rotas
- Submeter sitemap no Google Search Console

### 1.5 Google Search Console + Analytics

- Verificar domínio no GSC via DNS TXT record
- Configurar GA4 (ou Plausible/Umami como alternativa leve)
- Submeter sitemap
- Monitorar Core Web Vitals no GSC

### 1.6 Core Web Vitals

- Auditar com Lighthouse
- Targets: LCP < 2.5s, CLS < 0.1, INP < 200ms
- Next.js + Vercel SSR já deve estar bem; ajustar se necessário

---

## Fase 2: Páginas Estáticas por Especialidade e Região

Multiplica páginas indexáveis. Cada combinação relevante vira uma URL própria.

### 2.1 Rotas dedicadas

| Rota | Exemplo | Título H1 |
|------|---------|-----------|
| `/especialidade/[slug]` | `/especialidade/cardiologia` | "Vagas de Cardiologia" |
| `/estado/[uf]` | `/estado/sp` | "Vagas Médicas em São Paulo" |
| `/estado/[uf]/[cidade]` | `/estado/sp/sao-paulo` | "Vagas Médicas em São Paulo - SP" |
| `/especialidade/[slug]/[uf]` | `/especialidade/cardiologia/sp` | "Vagas de Cardiologia em São Paulo" |

Cada página inclui:
- H1 otimizado
- Meta description única com contagem de vagas
- Lista de vagas paginada (server-rendered)
- Breadcrumbs (Home > Cardiologia > SP)
- Links internos pra especialidades e cidades relacionadas
- JSON-LD `BreadcrumbList` + `ItemList`

### 2.2 SSG + ISR

- `generateStaticParams` pré-gera combinações com vagas ativas
- `revalidate: 3600` (ISR de 1 hora) mantém dados frescos
- Combinações sem vagas retornam `notFound()` (404 real)

### 2.3 Sitemap expandido

Sitemap inclui todas as rotas de especialidade/estado/cidade. Sitemap index com sub-sitemaps se volume for grande.

### 2.4 Internal linking

- `VagaCard` linka pra página da especialidade e da cidade
- Sidebar/footer com "Especialidades populares" e "Cidades com mais vagas"
- Breadcrumbs em todas as páginas

### 2.5 Home como hub

A home se torna hub de navegação:
- Links pras top especialidades (já existe `SpecialtyPicks`)
- Links pros top estados/cidades
- Stats gerais
- Filtros continuam funcionando, redirecionando pra rotas dedicadas

---

## Fase 3: Conteúdo Editorial + GEO

Constrói autoridade e otimiza pra citação por IAs.

### 3.1 `llms.txt`

Arquivo na raiz do site seguindo o protocolo llms.txt:

```
# EmpregaMed
> Maior agregador de vagas médicas do Brasil. Reúne oportunidades de
> Indeed, BNE, Vagas.com, InfoJobs e PCI Concursos em um só lugar.

## O que fazemos
- Agregamos vagas médicas de 5+ fontes brasileiras
- Cobrimos 31 especialidades médicas
- Atualizamos diariamente com crawlers automatizados
- Dados disponíveis por especialidade, estado e cidade

## Especialidades cobertas
Cardiologia, Ortopedia, Pediatria, Clínica Geral, Ginecologia,
Dermatologia, Oftalmologia, Psiquiatria, Neurologia, Anestesiologia,
Cirurgia Geral, Radiologia, Urologia, Medicina do Trabalho,
Medicina da Família, Emergência, UTI, Oncologia, Endocrinologia,
Gastroenterologia, Nefrologia, Pneumologia, Reumatologia,
Hematologia, Infectologia, Geriatria, Medicina Esportiva,
Otorrinolaringologia, Cirurgia Plástica, Cirurgia Cardiovascular,
Medicina Nuclear

## Fontes
Indeed Brasil, BNE, Vagas.com, InfoJobs, PCI Concursos

## URL
https://empregamed.com.br
```

### 3.2 Página "Sobre" (E-E-A-T)

Rota `/sobre` com:
- O que é o EmpregaMed
- Quantas vagas, fontes, cidades (dados reais do DB, server-side)
- Como funciona (crawler automatizado, atualização diária)
- Missão: facilitar a busca de emprego para médicos no Brasil
- JSON-LD `Organization` detalhado

### 3.3 Blog

Rota `/blog` com artigos estratégicos:

**Factuais/estatísticos** (otimizados pra citação por IAs):
- "Panorama das Vagas Médicas no Brasil em 2026"
- "Especialidades médicas com mais vagas abertas"
- "Salários médicos por estado: comparativo 2026"
- "Cidades com mais oportunidades para médicos"

**Guias práticos** (tráfego orgânico long-tail):
- "Como encontrar vagas médicas online: guia completo"
- "Cardiologia: carreira, salário e vagas disponíveis" (um por especialidade)

**Data-driven** (diferencial competitivo):
- Relatórios periódicos automáticos gerados dos dados do crawler
- "X novas vagas esta semana, Y% em cardiologia, Z% em SP"

Artigos com:
- JSON-LD `Article` + `FAQPage` (perguntas e respostas que IAs extraem)
- Structured data `BreadcrumbList`
- Internal linking pro agregador

### 3.4 GEO (Generative Engine Optimization)

Técnicas pra aumentar citação por IAs:

- **Frases declarativas e factuais** nos primeiros parágrafos de cada página
  - "O EmpregaMed agrega mais de X vagas médicas de 5 fontes brasileiras, cobrindo 31 especialidades em Y cidades."
- **Dados quantitativos**: números, percentuais, rankings
- **FAQ estruturado**: perguntas frequentes com respostas concisas
- **Autoridade topical**: cobrir cada especialidade com página dedicada + artigo
- **Citações e fontes**: referenciar dados oficiais (CFM, CRM, IBGE) nos artigos

### 3.5 Domínio `empregamed.com.br`

- Registrar domínio
- Configurar no Vercel
- Atualizar todas as referências internas
- Redirect do antigo `.vercel.app` pro novo domínio

---

## Fora de Escopo

- `JobPosting` schema (somos agregador, risco de duplicação)
- Competir no Google for Jobs
- API pública de dados
- Internacionalização (pt-BR only)
- Google Ads / mídia paga

## Métricas de Sucesso

- Google Search Console: impressões e cliques crescendo mês a mês
- Páginas indexadas: de 1 (home) para 50+ (especialidades + estados + cidades)
- Core Web Vitals: todos verdes
- Citação por IAs: testar periodicamente perguntando a ChatGPT/Claude/Gemini sobre vagas médicas no Brasil
- Tráfego orgânico: meta de 1k visitas/mês em 3 meses
