# Frontend MVP — Vagas Medicas

## Objetivo

Frontend publico para medicos buscarem vagas agregadas de multiplos job boards brasileiros. Pagina unica com listagem filtrada, SEO-friendly, consumindo dados do Supabase.

## Pre-requisitos (banco de dados)

Ja aplicados no Supabase:

```sql
-- View com coluna computada para ordenacao (sem raw_html)
CREATE OR REPLACE VIEW vagas_public
WITH (security_invoker = true)
AS
SELECT
    id, external_id, source, title, location, company,
    salary, salary_min, salary_max, salary_period,
    job_type, specialty, city, state,
    description, benefits, url, published_at, first_seen_at,
    COALESCE(published_at, first_seen_at) AS effective_date
FROM vagas;

-- Busca accent-insensitive via RPC
CREATE EXTENSION IF NOT EXISTS unaccent;

CREATE OR REPLACE FUNCTION search_vagas(search_term text)
RETURNS SETOF vagas_public
LANGUAGE sql STABLE
AS $$
  SELECT * FROM vagas_public
  WHERE unaccent(title) ILIKE '%' || unaccent(search_term) || '%'
$$;
```

RLS e policies ja configurados:
- `vagas`: RLS ON, `anon` SELECT only, `service_role` ALL
- `discarded_ids`: RLS ON, `service_role` ALL
- View com `security_invoker = true`

Variaveis de ambiente necessarias no frontend (`.env.local`):
- `NEXT_PUBLIC_SUPABASE_URL`
- `NEXT_PUBLIC_SUPABASE_ANON_KEY`

## Stack

- Next.js 15 (App Router) + TypeScript
- Tailwind CSS
- supabase-js + @supabase/ssr
- Headless UI (combobox acessivel)
- Deploy: Vercel

## Estrutura de pastas

```
frontend/
├── app/
│   ├── layout.tsx            # Layout raiz, meta tags, fonts
│   ├── page.tsx              # Server Component — carga inicial (SEO)
│   └── _components/
│       ├── VagaList.tsx      # Client Component — lista + filtros interativos
│       ├── VagaCard.tsx      # Card individual
│       ├── Combobox.tsx      # Wrapper do Headless UI Combobox
│       └── Pagination.tsx    # Paginacao
├── lib/
│   ├── supabase/
│   │   ├── server.ts         # Cliente Supabase p/ Server Components
│   │   └── client.ts         # Cliente Supabase p/ browser
│   ├── queries.ts            # Funcoes de query compartilhadas (server + client)
│   └── types.ts              # Tipo Vaga derivado do schema
├── tailwind.config.ts
├── next.config.ts
└── package.json
```

## Pagina principal (`/`)

### Layout

```
┌──────────────────────────────────────────┐
│  Header: "Vagas Medicas" + tagline       │
├──────────────────────────────────────────┤
│  Filtros (inline):                       │
│  [Especialidade ▼] [Cidade ▼] [Busca…]  │
├──────────────────────────────────────────┤
│  "243 vagas encontradas"                 │
├──────────────────────────────────────────┤
│  ┌─ VagaCard ──────────────────────────┐ │
│  │ Cardiologista        Sao Paulo, SP  │ │
│  │ Hospital Albert Einstein            │ │
│  │ R$ 15.000 - 20.000/mes    Indeed    │ │
│  │ Publicada ha 3 dias    [Ver vaga →] │ │
│  └─────────────────────────────────────┘ │
│  ...                                     │
├──────────────────────────────────────────┤
│  [← Anterior]  Pagina 1 de 12  [Prox →] │
└──────────────────────────────────────────┘
```

### Filtros

Dois combobox buscaveis (Headless UI) + input de texto:

1. **Especialidade** — opcoes carregadas dinamicamente via `SELECT DISTINCT specialty FROM vagas_public WHERE specialty IS NOT NULL ORDER BY specialty`
2. **Cidade** — opcoes carregadas dinamicamente via `SELECT DISTINCT city FROM vagas_public WHERE city IS NOT NULL ORDER BY city` (~174 cidades, 98% das vagas tem cidade)
3. **Busca por texto** — input com debounce, busca accent-insensitive no titulo via RPC `search_vagas`

Filtros refletidos na URL via query params (`?specialty=Cardiologista&city=Curitiba&q=plantonista`) para compartilhamento e SEO.

### VagaCard

Card expansivel. Visao compacta por padrao, clique expande para mostrar descricao e beneficios.

**Compacto (sempre visivel):**
- **Titulo** da vaga
- **Badge de especialidade** (se existir)
- **Empresa** (ou "Confidencial" se null)
- **Cidade + Estado**
- **Salario** formatado ("R$ 15.000 - 20.000/mes"), oculto se null
- **Fonte** (badge: Indeed, Vagas.com, BNE, InfoJobs)
- **Data** relativa ("ha 3 dias") — `effective_date` (= `published_at ?? first_seen_at`)
- **Botao "Ver vaga"** — abre URL original em nova aba

**Expandido (ao clicar):**
- **Descricao** — truncada em ~300 caracteres com "ver mais" que mostra completa
- **Beneficios** — lista de badges (JSONB array)

### Paginacao

- 20 vagas por pagina
- Ordenacao: `effective_date DESC` (coluna computada na view)
- Offset-based via `.range()` (aceitavel para o volume atual de ~426 vagas)

## Data fetching

### Colunas selecionadas

Listagem seleciona apenas colunas exibidas no card (sem `description`, `benefits`, `external_id`):

```ts
const LISTING_COLUMNS = 'id, title, specialty, company, city, state, salary, salary_min, salary_max, salary_period, job_type, source, url, effective_date, description, benefits'
```

### Carga inicial (Server Component — SEO)

`page.tsx` recebe `searchParams` e faz a query filtrada no servidor via @supabase/ssr. URLs como `/?specialty=Cardiologista` renderizam HTML ja filtrado, indexavel pelo Google.

```ts
// app/page.tsx (Server Component)
export default async function Page({ searchParams }) {
  const { specialty, city, q, page } = await searchParams
  const { vagas, count } = await fetchVagas({ specialty, city, q, page })

  return <VagaList initialVagas={vagas} initialCount={count} />
}
```

### Filtros interativos (Client Component — hidratacao)

`VagaList` recebe `initialVagas` e `initialCount` como props e usa como estado inicial. Queries client-side so disparam quando o usuario muda filtros ou pagina:

```ts
// _components/VagaList.tsx ("use client")
const [vagas, setVagas] = useState(initialVagas)
const [count, setCount] = useState(initialCount)

// So faz query quando filtros mudam (nao no mount)
useEffect(() => {
  if (!filtersChanged) return
  fetchVagas({ specialty, city, q, page }).then(({ vagas, count }) => {
    setVagas(vagas)
    setCount(count)
  })
}, [specialty, city, q, page])
```

### Funcao de query compartilhada

Usada tanto no server quanto no client:

```ts
// lib/queries.ts
async function fetchVagas({ specialty, city, q, page }) {
  if (q) {
    // Busca accent-insensitive via RPC
    const { data, count } = await supabase
      .rpc('search_vagas', { search_term: q }, { count: 'exact' })
      .select(LISTING_COLUMNS)
      .order('effective_date', { ascending: false })
      .range(offset, offset + 19)
    // Aplicar filtros de specialty/city apos RPC se necessario
  } else {
    // Query direta na view
    let query = supabase
      .from('vagas_public')
      .select(LISTING_COLUMNS, { count: 'exact' })
      .order('effective_date', { ascending: false })

    if (specialty) query = query.eq('specialty', specialty)
    if (city) query = query.eq('city', city)

    query = query.range(offset, offset + 19)
  }
}
```

## Fonte de dados

View `vagas_public` (sem `raw_html`, com `effective_date` computado), protegida por RLS:

- `anon`: SELECT only
- `service_role`: ALL
- `postgres` (conexao direta): bypassa RLS

### Dados atuais (referencia)

- 426 vagas, 174 cidades, 28 especialidades
- 98% das vagas tem cidade preenchida
- 58% tem published_at (restante usa first_seen_at via effective_date)

## Fora do escopo (MVP)

- Pagina de detalhe da vaga
- Dashboard / analytics
- Autenticacao de usuarios
- Alertas / notificacoes
- Filtro por faixa salarial
- Paginacao cursor-based (offset suficiente para volume atual)
