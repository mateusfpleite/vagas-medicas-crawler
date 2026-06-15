# SEO + GEO Implementation Plan — EmpregaMed

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add SEO infrastructure, dedicated pages per specialty/region, and GEO optimizations so EmpregaMed ranks on Google and gets cited by AI agents.

**Architecture:** Three phases — (1) technical SEO foundation on existing pages, (2) new routes per specialty/state/city with ISR, (3) editorial content + llms.txt for AI citation. Each phase is independently deployable.

**Tech Stack:** Next.js 16 App Router (generateMetadata, robots.ts, sitemap.ts, next/og), Drizzle ORM, Tailwind CSS 4.

**Design doc:** `docs/plans/2026-02-19-seo-geo-design.md`

---

## Phase 1: Technical SEO Foundation

### Task 1: Rebrand to EmpregaMed

Update all existing references from "Vagas Medicas" to "EmpregaMed".

**Files:**
- Modify: `frontend/app/layout.tsx` (lines 18-21 metadata, line 37 footer text)
- Modify: `frontend/app/_components/Hero.tsx` (line 20 subtitle text)

**Step 1: Update layout metadata and footer**

In `frontend/app/layout.tsx`, change the metadata object:

```typescript
export const metadata: Metadata = {
  title: 'EmpregaMed — Vagas medicas de todo o Brasil em um so lugar',
  description:
    'Encontre vagas medicas agregadas de Indeed, BNE, Vagas.com, InfoJobs e PCI Concursos. Filtre por especialidade, cidade, estado e mais.',
}
```

In the footer, change "Vagas Medicas" to "EmpregaMed":
```typescript
<p className="font-[family-name:var(--font-serif)] text-lg text-ink">
  EmpregaMed
</p>
```

Add PCI Concursos to the sources list in the footer:
```tsx
<span className="font-medium text-source-infojobs">InfoJobs</span>
<span>·</span>
<span className="font-medium text-ink-light">PCI Concursos</span>
```

**Step 2: Update Hero subtitle**

In `frontend/app/_components/Hero.tsx`, update the subtitle:
```typescript
Agregamos vagas de Indeed, BNE, Vagas.com, InfoJobs e PCI Concursos para voce nao precisar procurar em cada site.
```

**Step 3: Verify the build**

Run: `npm run build --prefix frontend`
Expected: Build succeeds with no errors.

**Step 4: Commit**

```
feat: rebrand to EmpregaMed
```

---

### Task 2: Add robots.txt

**Files:**
- Create: `frontend/app/robots.ts`

**Step 1: Create robots.ts**

```typescript
import type { MetadataRoute } from 'next'

const BASE_URL = process.env.NEXT_PUBLIC_BASE_URL ?? 'https://empregamed.com.br'

export default function robots(): MetadataRoute.Robots {
  return {
    rules: {
      userAgent: '*',
      allow: '/',
    },
    sitemap: `${BASE_URL}/sitemap.xml`,
  }
}
```

**Step 2: Verify the build**

Run: `npm run build --prefix frontend`
Expected: Build succeeds. The `/robots.txt` route is listed in the build output.

**Step 3: Commit**

```
feat: add robots.txt with sitemap reference
```

---

### Task 3: Add sitemap.xml (basic)

Start with a simple sitemap for the home page. We'll expand it in Phase 2 when dedicated routes exist.

**Files:**
- Create: `frontend/app/sitemap.ts`

**Step 1: Create sitemap.ts**

```typescript
import type { MetadataRoute } from 'next'

const BASE_URL = process.env.NEXT_PUBLIC_BASE_URL ?? 'https://empregamed.com.br'

export default function sitemap(): MetadataRoute.Sitemap {
  return [
    {
      url: BASE_URL,
      lastModified: new Date(),
      changeFrequency: 'daily',
      priority: 1,
    },
  ]
}
```

**Step 2: Verify the build**

Run: `npm run build --prefix frontend`
Expected: Build succeeds. The `/sitemap.xml` route is listed.

**Step 3: Commit**

```
feat: add basic sitemap.xml
```

---

### Task 4: Add JSON-LD structured data (WebSite + Organization)

**Files:**
- Create: `frontend/lib/structured-data.ts`
- Modify: `frontend/app/layout.tsx` (add script tag to head)

**Step 1: Create structured data helpers**

Create `frontend/lib/structured-data.ts`:

```typescript
const BASE_URL = process.env.NEXT_PUBLIC_BASE_URL ?? 'https://empregamed.com.br'

export function websiteJsonLd() {
  return {
    '@context': 'https://schema.org',
    '@type': 'WebSite',
    name: 'EmpregaMed',
    url: BASE_URL,
    description:
      'Maior agregador de vagas medicas do Brasil. Reune oportunidades de Indeed, BNE, Vagas.com, InfoJobs e PCI Concursos em um so lugar.',
    potentialAction: {
      '@type': 'SearchAction',
      target: {
        '@type': 'EntryPoint',
        urlTemplate: `${BASE_URL}/?q={search_term_string}`,
      },
      'query-input': 'required name=search_term_string',
    },
  }
}

export function organizationJsonLd() {
  return {
    '@context': 'https://schema.org',
    '@type': 'Organization',
    name: 'EmpregaMed',
    url: BASE_URL,
    description:
      'Agregador de vagas medicas do Brasil. Reune oportunidades de multiplos sites de emprego, cobrindo 31 especialidades medicas.',
  }
}
```

**Step 2: Inject JSON-LD into layout**

In `frontend/app/layout.tsx`, import and add to the `<head>`:

```typescript
import { websiteJsonLd, organizationJsonLd } from '@/lib/structured-data'
```

Inside the `<html>` tag, before `<body>`:

```tsx
<head>
  <script
    type="application/ld+json"
    dangerouslySetInnerHTML={{
      __html: JSON.stringify([websiteJsonLd(), organizationJsonLd()]),
    }}
  />
</head>
```

**Step 3: Verify the build**

Run: `npm run build --prefix frontend`
Expected: Build succeeds.

**Step 4: Commit**

```
feat: add WebSite and Organization JSON-LD structured data
```

---

### Task 5: Add Open Graph and Twitter Card meta tags

**Files:**
- Modify: `frontend/app/layout.tsx` (expand metadata object)

**Step 1: Expand metadata in layout.tsx**

Replace the existing `metadata` export with:

```typescript
const BASE_URL = process.env.NEXT_PUBLIC_BASE_URL ?? 'https://empregamed.com.br'

export const metadata: Metadata = {
  title: {
    default: 'EmpregaMed — Vagas medicas de todo o Brasil em um so lugar',
    template: '%s | EmpregaMed',
  },
  description:
    'Encontre vagas medicas agregadas de Indeed, BNE, Vagas.com, InfoJobs e PCI Concursos. Filtre por especialidade, cidade, estado e mais.',
  metadataBase: new URL(BASE_URL),
  alternates: {
    canonical: '/',
  },
  openGraph: {
    title: 'EmpregaMed — Vagas medicas de todo o Brasil em um so lugar',
    description:
      'Encontre vagas medicas agregadas de Indeed, BNE, Vagas.com, InfoJobs e PCI Concursos. Filtre por especialidade, cidade, estado e mais.',
    url: BASE_URL,
    siteName: 'EmpregaMed',
    locale: 'pt_BR',
    type: 'website',
  },
  twitter: {
    card: 'summary_large_image',
    title: 'EmpregaMed — Vagas medicas de todo o Brasil em um so lugar',
    description:
      'Encontre vagas medicas agregadas de Indeed, BNE, Vagas.com, InfoJobs e PCI Concursos.',
  },
  robots: {
    index: true,
    follow: true,
  },
}
```

Note: `metadataBase` sets the base for all relative URLs in metadata. The `title.template` allows child pages to set just their title and get ` | EmpregaMed` appended.

**Step 2: Verify the build**

Run: `npm run build --prefix frontend`
Expected: Build succeeds.

**Step 3: Commit**

```
feat: add Open Graph, Twitter Card, and canonical meta tags
```

---

### Task 6: Add NEXT_PUBLIC_BASE_URL to environment

**Files:**
- Modify: `frontend/.env.local` (add variable)

**Step 1: Add the env var**

Add to `frontend/.env.local`:
```
NEXT_PUBLIC_BASE_URL=https://empregamed.com.br
```

Also set this in Vercel project settings (Settings > Environment Variables).

Note: Until the domain is registered, you can use the current `.vercel.app` URL temporarily.

**Step 2: Commit**

No commit needed (`.env.local` is gitignored). But document the env var.

Add to `frontend/.env.local.example` (create if it doesn't exist):
```
DATABASE_URL=
NEXT_PUBLIC_BASE_URL=https://empregamed.com.br
```

```
chore: add .env.local.example with NEXT_PUBLIC_BASE_URL
```

---

## Phase 2: Dedicated Routes per Specialty and Region

### Task 7: Add slug utility functions

**Files:**
- Create: `frontend/lib/slugs.ts`

**Step 1: Create slug utilities**

```typescript
/**
 * Convert a specialty name to a URL slug.
 * "Clinica Geral" -> "clinica-geral"
 * "Medicina do Trabalho" -> "medicina-do-trabalho"
 */
export function toSlug(text: string): string {
  return text
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/\s+/g, '-')
    .replace(/[^a-z0-9-]/g, '')
    .replace(/-+/g, '-')
    .replace(/^-|-$/g, '')
}

/**
 * Convert a URL slug back to display text.
 * "clinica-geral" -> "Clinica Geral"
 * Note: This is a best-effort reversal. Accents are lost.
 */
export function fromSlug(slug: string): string {
  return slug
    .split('-')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ')
}
```

**Step 2: Verify the build**

Run: `npm run build --prefix frontend`
Expected: Build succeeds.

**Step 3: Commit**

```
feat: add slug utility functions for URL generation
```

---

### Task 8: Add queries for dedicated routes

**Files:**
- Modify: `frontend/lib/queries.ts` (add new query functions)

**Step 1: Add fetchSpecialties and fetchStatesWithCities**

Add to the end of `frontend/lib/queries.ts`:

```typescript
/** All specialties that have at least one vaga. */
export async function fetchAllSpecialties(): Promise<string[]> {
  const rows = await db
    .selectDistinct({ specialty: vagasPublic.specialty })
    .from(vagasPublic)
    .where(isNotNull(vagasPublic.specialty))
    .orderBy(vagasPublic.specialty)

  return rows.map((r) => r.specialty!)
}

/** All states that have at least one vaga. */
export async function fetchAllStates(): Promise<string[]> {
  const rows = await db
    .selectDistinct({ state: vagasPublic.state })
    .from(vagasPublic)
    .where(isNotNull(vagasPublic.state))
    .orderBy(vagasPublic.state)

  return rows.map((r) => r.state!)
}

/** All cities for a given state that have at least one vaga. */
export async function fetchCitiesByState(state: string): Promise<string[]> {
  const rows = await db
    .selectDistinct({ city: vagasPublic.city })
    .from(vagasPublic)
    .where(and(eq(vagasPublic.state, state), isNotNull(vagasPublic.city)))
    .orderBy(vagasPublic.city)

  return rows.map((r) => r.city!)
}

/** Count vagas for a specialty (used in meta descriptions). */
export async function fetchCountBySpecialty(specialty: string): Promise<number> {
  const [row] = await db
    .select({ count: count() })
    .from(vagasPublic)
    .where(eq(vagasPublic.specialty, specialty))

  return row.count
}

/** Count vagas for a state (used in meta descriptions). */
export async function fetchCountByState(state: string): Promise<number> {
  const [row] = await db
    .select({ count: count() })
    .from(vagasPublic)
    .where(eq(vagasPublic.state, state))

  return row.count
}
```

**Step 2: Verify the build**

Run: `npm run build --prefix frontend`
Expected: Build succeeds.

**Step 3: Commit**

```
feat: add queries for specialty/state/city routes
```

---

### Task 9: Create Breadcrumbs component

**Files:**
- Create: `frontend/app/_components/Breadcrumbs.tsx`

**Step 1: Create component**

```tsx
import Link from 'next/link'

type Crumb = {
  label: string
  href?: string
}

export function Breadcrumbs({ crumbs }: { crumbs: Crumb[] }) {
  return (
    <nav aria-label="Breadcrumb" className="mb-4 text-[0.78rem] text-ink-muted">
      <ol className="flex flex-wrap items-center gap-1">
        {crumbs.map((crumb, i) => (
          <li key={i} className="flex items-center gap-1">
            {i > 0 && <span aria-hidden="true">/</span>}
            {crumb.href ? (
              <Link href={crumb.href} className="hover:text-primary hover:underline">
                {crumb.label}
              </Link>
            ) : (
              <span className="text-ink-light">{crumb.label}</span>
            )}
          </li>
        ))}
      </ol>
    </nav>
  )
}

export function breadcrumbJsonLd(crumbs: Crumb[]) {
  const BASE_URL = process.env.NEXT_PUBLIC_BASE_URL ?? 'https://empregamed.com.br'

  return {
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    itemListElement: crumbs
      .filter((c) => c.href)
      .map((crumb, i) => ({
        '@type': 'ListItem',
        position: i + 1,
        name: crumb.label,
        item: `${BASE_URL}${crumb.href}`,
      })),
  }
}
```

**Step 2: Verify the build**

Run: `npm run build --prefix frontend`
Expected: Build succeeds.

**Step 3: Commit**

```
feat: add Breadcrumbs component with JSON-LD support
```

---

### Task 10: Create specialty route `/especialidade/[slug]`

**Files:**
- Create: `frontend/app/especialidade/[slug]/page.tsx`

**Step 1: Create the specialty page**

```tsx
import { notFound } from 'next/navigation'
import type { Metadata } from 'next'
import { fetchVagas, fetchFilterOptions, fetchAllSpecialties, fetchCountBySpecialty } from '@/lib/queries'
import { fromSlug, toSlug } from '@/lib/slugs'
import { VagaList } from '@/app/_components/VagaList'
import { Breadcrumbs, breadcrumbJsonLd } from '@/app/_components/Breadcrumbs'

const BASE_URL = process.env.NEXT_PUBLIC_BASE_URL ?? 'https://empregamed.com.br'

type Props = {
  params: Promise<{ slug: string }>
  searchParams: Promise<Record<string, string | undefined>>
}

export async function generateStaticParams() {
  const specialties = await fetchAllSpecialties()
  return specialties.map((s) => ({ slug: toSlug(s) }))
}

export const revalidate = 3600

async function resolveSpecialty(slug: string): Promise<string | null> {
  const specialties = await fetchAllSpecialties()
  return specialties.find((s) => toSlug(s) === slug) ?? null
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params
  const specialty = await resolveSpecialty(slug)
  if (!specialty) return {}

  const count = await fetchCountBySpecialty(specialty)
  const title = `Vagas de ${specialty}`
  const description = `${count} vagas de ${specialty} agregadas de Indeed, BNE, Vagas.com, InfoJobs e PCI Concursos.`

  return {
    title,
    description,
    alternates: { canonical: `/especialidade/${slug}` },
    openGraph: {
      title: `${title} | EmpregaMed`,
      description,
      url: `${BASE_URL}/especialidade/${slug}`,
    },
  }
}

export default async function SpecialtyPage({ params, searchParams }: Props) {
  const { slug } = await params
  const sp = await searchParams
  const specialty = await resolveSpecialty(slug)
  if (!specialty) notFound()

  const page = sp.page ? Number(sp.page) : undefined
  const { vagas, count } = await fetchVagas({ specialty, page })
  const { specialties, cities, states } = await fetchFilterOptions()

  const crumbs = [
    { label: 'Inicio', href: '/' },
    { label: specialty },
  ]

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumbJsonLd(crumbs)) }}
      />
      <section className="border-b border-cream-dark bg-gradient-to-b from-white to-cream">
        <div className="mx-auto max-w-5xl px-6 py-10">
          <Breadcrumbs crumbs={crumbs} />
          <h1 className="font-[family-name:var(--font-serif)] text-3xl font-bold text-ink sm:text-4xl">
            Vagas de {specialty}
          </h1>
          <p className="mt-2 text-ink-muted">
            {count} {count === 1 ? 'vaga encontrada' : 'vagas encontradas'} em todo o Brasil.
          </p>
        </div>
      </section>
      <VagaList
        initialVagas={vagas}
        initialCount={count}
        specialties={specialties}
        cities={cities}
        states={states}
      />
    </>
  )
}
```

**Step 2: Verify the build**

Run: `npm run build --prefix frontend`
Expected: Build succeeds. Route `/especialidade/[slug]` appears in output.

**Step 3: Commit**

```
feat: add /especialidade/[slug] route with SSG+ISR
```

---

### Task 11: Create state route `/estado/[uf]`

**Files:**
- Create: `frontend/app/estado/[uf]/page.tsx`

**Step 1: Create the state page**

```tsx
import { notFound } from 'next/navigation'
import type { Metadata } from 'next'
import { fetchVagas, fetchFilterOptions, fetchAllStates, fetchCountByState } from '@/lib/queries'
import { UFS } from '@/lib/constants'
import { VagaList } from '@/app/_components/VagaList'
import { Breadcrumbs, breadcrumbJsonLd } from '@/app/_components/Breadcrumbs'

const BASE_URL = process.env.NEXT_PUBLIC_BASE_URL ?? 'https://empregamed.com.br'

type Props = {
  params: Promise<{ uf: string }>
  searchParams: Promise<Record<string, string | undefined>>
}

export async function generateStaticParams() {
  const states = await fetchAllStates()
  return states.map((s) => ({ uf: s.toLowerCase() }))
}

export const revalidate = 3600

function resolveStateName(uf: string): string | null {
  const entry = UFS.find((u) => u.sigla.toLowerCase() === uf.toLowerCase())
  return entry?.nome ?? null
}

function resolveStateSigla(uf: string): string | null {
  const entry = UFS.find((u) => u.sigla.toLowerCase() === uf.toLowerCase())
  return entry?.sigla ?? null
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { uf } = await params
  const sigla = resolveStateSigla(uf)
  const nome = resolveStateName(uf)
  if (!sigla || !nome) return {}

  const count = await fetchCountByState(sigla)
  const title = `Vagas Medicas em ${nome}`
  const description = `${count} vagas medicas em ${nome} (${sigla}) agregadas de Indeed, BNE, Vagas.com, InfoJobs e PCI Concursos.`

  return {
    title,
    description,
    alternates: { canonical: `/estado/${uf.toLowerCase()}` },
    openGraph: {
      title: `${title} | EmpregaMed`,
      description,
      url: `${BASE_URL}/estado/${uf.toLowerCase()}`,
    },
  }
}

export default async function StatePage({ params, searchParams }: Props) {
  const { uf } = await params
  const sp = await searchParams
  const sigla = resolveStateSigla(uf)
  const nome = resolveStateName(uf)
  if (!sigla || !nome) notFound()

  const page = sp.page ? Number(sp.page) : undefined
  const { vagas, count } = await fetchVagas({ state: sigla, page })
  const { specialties, cities, states } = await fetchFilterOptions({ state: sigla })

  const crumbs = [
    { label: 'Inicio', href: '/' },
    { label: nome },
  ]

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumbJsonLd(crumbs)) }}
      />
      <section className="border-b border-cream-dark bg-gradient-to-b from-white to-cream">
        <div className="mx-auto max-w-5xl px-6 py-10">
          <Breadcrumbs crumbs={crumbs} />
          <h1 className="font-[family-name:var(--font-serif)] text-3xl font-bold text-ink sm:text-4xl">
            Vagas Medicas em {nome}
          </h1>
          <p className="mt-2 text-ink-muted">
            {count} {count === 1 ? 'vaga encontrada' : 'vagas encontradas'} em {nome} ({sigla}).
          </p>
        </div>
      </section>
      <VagaList
        initialVagas={vagas}
        initialCount={count}
        specialties={specialties}
        cities={cities}
        states={states}
      />
    </>
  )
}
```

**Step 2: Verify the build**

Run: `npm run build --prefix frontend`
Expected: Build succeeds.

**Step 3: Commit**

```
feat: add /estado/[uf] route with SSG+ISR
```

---

### Task 12: Create city route `/estado/[uf]/[cidade]`

**Files:**
- Create: `frontend/app/estado/[uf]/[cidade]/page.tsx`

**Step 1: Create the city page**

```tsx
import { notFound } from 'next/navigation'
import type { Metadata } from 'next'
import { fetchVagas, fetchFilterOptions, fetchCitiesByState, fetchAllStates } from '@/lib/queries'
import { UFS } from '@/lib/constants'
import { toSlug, fromSlug } from '@/lib/slugs'
import { VagaList } from '@/app/_components/VagaList'
import { Breadcrumbs, breadcrumbJsonLd } from '@/app/_components/Breadcrumbs'

const BASE_URL = process.env.NEXT_PUBLIC_BASE_URL ?? 'https://empregamed.com.br'

type Props = {
  params: Promise<{ uf: string; cidade: string }>
  searchParams: Promise<Record<string, string | undefined>>
}

export async function generateStaticParams() {
  const states = await fetchAllStates()
  const params: { uf: string; cidade: string }[] = []

  for (const state of states) {
    const cities = await fetchCitiesByState(state)
    for (const city of cities) {
      params.push({ uf: state.toLowerCase(), cidade: toSlug(city) })
    }
  }

  return params
}

export const revalidate = 3600

function resolveUf(uf: string) {
  const entry = UFS.find((u) => u.sigla.toLowerCase() === uf.toLowerCase())
  return entry ? { sigla: entry.sigla, nome: entry.nome } : null
}

async function resolveCity(state: string, cidadeSlug: string): Promise<string | null> {
  const cities = await fetchCitiesByState(state)
  return cities.find((c) => toSlug(c) === cidadeSlug) ?? null
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { uf, cidade } = await params
  const ufData = resolveUf(uf)
  if (!ufData) return {}

  const city = await resolveCity(ufData.sigla, cidade)
  if (!city) return {}

  const { count } = await fetchVagas({ state: ufData.sigla, city: [city] })
  const title = `Vagas Medicas em ${city} - ${ufData.sigla}`
  const description = `${count} vagas medicas em ${city}, ${ufData.nome}. Agregadas de Indeed, BNE, Vagas.com, InfoJobs e PCI Concursos.`

  return {
    title,
    description,
    alternates: { canonical: `/estado/${uf.toLowerCase()}/${cidade}` },
    openGraph: {
      title: `${title} | EmpregaMed`,
      description,
      url: `${BASE_URL}/estado/${uf.toLowerCase()}/${cidade}`,
    },
  }
}

export default async function CityPage({ params, searchParams }: Props) {
  const { uf, cidade } = await params
  const sp = await searchParams
  const ufData = resolveUf(uf)
  if (!ufData) notFound()

  const city = await resolveCity(ufData.sigla, cidade)
  if (!city) notFound()

  const page = sp.page ? Number(sp.page) : undefined
  const { vagas, count } = await fetchVagas({ state: ufData.sigla, city: [city], page })
  const { specialties, cities, states } = await fetchFilterOptions({ state: ufData.sigla })

  const crumbs = [
    { label: 'Inicio', href: '/' },
    { label: ufData.nome, href: `/estado/${uf.toLowerCase()}` },
    { label: city },
  ]

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumbJsonLd(crumbs)) }}
      />
      <section className="border-b border-cream-dark bg-gradient-to-b from-white to-cream">
        <div className="mx-auto max-w-5xl px-6 py-10">
          <Breadcrumbs crumbs={crumbs} />
          <h1 className="font-[family-name:var(--font-serif)] text-3xl font-bold text-ink sm:text-4xl">
            Vagas Medicas em {city}
          </h1>
          <p className="mt-2 text-ink-muted">
            {count} {count === 1 ? 'vaga encontrada' : 'vagas encontradas'} em {city}, {ufData.nome}.
          </p>
        </div>
      </section>
      <VagaList
        initialVagas={vagas}
        initialCount={count}
        specialties={specialties}
        cities={cities}
        states={states}
      />
    </>
  )
}
```

**Step 2: Verify the build**

Run: `npm run build --prefix frontend`
Expected: Build succeeds.

**Step 3: Commit**

```
feat: add /estado/[uf]/[cidade] route with SSG+ISR
```

---

### Task 13: Create specialty+state route `/especialidade/[slug]/[uf]`

**Files:**
- Create: `frontend/app/especialidade/[slug]/[uf]/page.tsx`

**Step 1: Create the combined page**

```tsx
import { notFound } from 'next/navigation'
import type { Metadata } from 'next'
import { fetchVagas, fetchFilterOptions, fetchAllSpecialties, fetchAllStates } from '@/lib/queries'
import { toSlug } from '@/lib/slugs'
import { UFS } from '@/lib/constants'
import { VagaList } from '@/app/_components/VagaList'
import { Breadcrumbs, breadcrumbJsonLd } from '@/app/_components/Breadcrumbs'

const BASE_URL = process.env.NEXT_PUBLIC_BASE_URL ?? 'https://empregamed.com.br'

type Props = {
  params: Promise<{ slug: string; uf: string }>
  searchParams: Promise<Record<string, string | undefined>>
}

export async function generateStaticParams() {
  const [specialties, states] = await Promise.all([fetchAllSpecialties(), fetchAllStates()])
  const params: { slug: string; uf: string }[] = []

  for (const s of specialties) {
    for (const st of states) {
      params.push({ slug: toSlug(s), uf: st.toLowerCase() })
    }
  }

  return params
}

export const revalidate = 3600

async function resolveSpecialty(slug: string): Promise<string | null> {
  const specialties = await fetchAllSpecialties()
  return specialties.find((s) => toSlug(s) === slug) ?? null
}

function resolveUf(uf: string) {
  const entry = UFS.find((u) => u.sigla.toLowerCase() === uf.toLowerCase())
  return entry ? { sigla: entry.sigla, nome: entry.nome } : null
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug, uf } = await params
  const specialty = await resolveSpecialty(slug)
  const ufData = resolveUf(uf)
  if (!specialty || !ufData) return {}

  const { count } = await fetchVagas({ specialty, state: ufData.sigla })
  const title = `Vagas de ${specialty} em ${ufData.nome}`
  const description = `${count} vagas de ${specialty} em ${ufData.nome} (${ufData.sigla}). Agregadas de Indeed, BNE, Vagas.com, InfoJobs e PCI Concursos.`

  return {
    title,
    description,
    alternates: { canonical: `/especialidade/${slug}/${uf.toLowerCase()}` },
    openGraph: {
      title: `${title} | EmpregaMed`,
      description,
      url: `${BASE_URL}/especialidade/${slug}/${uf.toLowerCase()}`,
    },
  }
}

export default async function SpecialtyStatePage({ params, searchParams }: Props) {
  const { slug, uf } = await params
  const sp = await searchParams
  const specialty = await resolveSpecialty(slug)
  const ufData = resolveUf(uf)
  if (!specialty || !ufData) notFound()

  const page = sp.page ? Number(sp.page) : undefined
  const { vagas, count } = await fetchVagas({ specialty, state: ufData.sigla, page })
  const { specialties, cities, states } = await fetchFilterOptions({ state: ufData.sigla })

  if (count === 0) notFound()

  const crumbs = [
    { label: 'Inicio', href: '/' },
    { label: specialty, href: `/especialidade/${slug}` },
    { label: ufData.nome },
  ]

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumbJsonLd(crumbs)) }}
      />
      <section className="border-b border-cream-dark bg-gradient-to-b from-white to-cream">
        <div className="mx-auto max-w-5xl px-6 py-10">
          <Breadcrumbs crumbs={crumbs} />
          <h1 className="font-[family-name:var(--font-serif)] text-3xl font-bold text-ink sm:text-4xl">
            Vagas de {specialty} em {ufData.nome}
          </h1>
          <p className="mt-2 text-ink-muted">
            {count} {count === 1 ? 'vaga encontrada' : 'vagas encontradas'}.
          </p>
        </div>
      </section>
      <VagaList
        initialVagas={vagas}
        initialCount={count}
        specialties={specialties}
        cities={cities}
        states={states}
      />
    </>
  )
}
```

**Step 2: Verify the build**

Run: `npm run build --prefix frontend`
Expected: Build succeeds.

**Step 3: Commit**

```
feat: add /especialidade/[slug]/[uf] combined route
```

---

### Task 14: Expand sitemap with all routes

**Files:**
- Modify: `frontend/app/sitemap.ts` (expand to include all routes)

**Step 1: Rewrite sitemap.ts**

Replace the entire file:

```typescript
import type { MetadataRoute } from 'next'
import { fetchAllSpecialties, fetchAllStates, fetchCitiesByState } from '@/lib/queries'
import { toSlug } from '@/lib/slugs'

const BASE_URL = process.env.NEXT_PUBLIC_BASE_URL ?? 'https://empregamed.com.br'

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const [specialties, states] = await Promise.all([
    fetchAllSpecialties(),
    fetchAllStates(),
  ])

  const entries: MetadataRoute.Sitemap = [
    {
      url: BASE_URL,
      lastModified: new Date(),
      changeFrequency: 'daily',
      priority: 1,
    },
  ]

  // Specialty pages
  for (const s of specialties) {
    entries.push({
      url: `${BASE_URL}/especialidade/${toSlug(s)}`,
      lastModified: new Date(),
      changeFrequency: 'daily',
      priority: 0.8,
    })
  }

  // State pages
  for (const st of states) {
    entries.push({
      url: `${BASE_URL}/estado/${st.toLowerCase()}`,
      lastModified: new Date(),
      changeFrequency: 'daily',
      priority: 0.8,
    })

    // City pages
    const cities = await fetchCitiesByState(st)
    for (const city of cities) {
      entries.push({
        url: `${BASE_URL}/estado/${st.toLowerCase()}/${toSlug(city)}`,
        lastModified: new Date(),
        changeFrequency: 'daily',
        priority: 0.6,
      })
    }
  }

  // Specialty + state combinations
  for (const s of specialties) {
    for (const st of states) {
      entries.push({
        url: `${BASE_URL}/especialidade/${toSlug(s)}/${st.toLowerCase()}`,
        lastModified: new Date(),
        changeFrequency: 'daily',
        priority: 0.6,
      })
    }
  }

  return entries
}
```

**Step 2: Verify the build**

Run: `npm run build --prefix frontend`
Expected: Build succeeds.

**Step 3: Commit**

```
feat: expand sitemap with specialty, state, and city routes
```

---

### Task 15: Add internal linking from home page

Update `SpecialtyPicks` to link to dedicated pages instead of filtering via query params. Also add a states section.

**Files:**
- Modify: `frontend/app/_components/SpecialtyPicks.tsx` (link to dedicated routes)
- Create: `frontend/app/_components/PopularStates.tsx`
- Modify: `frontend/app/page.tsx` (add PopularStates section)

**Step 1: Refactor SpecialtyPicks to use links**

Replace the entire `SpecialtyPicks.tsx`:

```tsx
import Link from 'next/link'
import { SpecialtyCount } from '@/lib/types'
import { toSlug } from '@/lib/slugs'

export function SpecialtyPicks({ specialtyCounts }: { specialtyCounts: SpecialtyCount[] }) {
  if (specialtyCounts.length === 0) return null

  return (
    <section className="border-b border-cream-dark bg-white/60 py-6">
      <div className="mx-auto max-w-5xl px-6">
        <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-ink-muted">
          Especialidades mais procuradas
        </p>
        <div className="flex flex-wrap gap-2">
          {specialtyCounts.map((sc, i) => (
            <Link
              key={sc.specialty}
              href={`/especialidade/${toSlug(sc.specialty)}`}
              className="animate-fade-in inline-flex items-center gap-1.5 rounded-full bg-cream-dark/60 px-3.5 py-1.5 text-sm font-medium text-ink-light transition-all hover:bg-primary-light hover:text-primary-dark"
              style={{ animationDelay: `${300 + i * 40}ms` }}
            >
              {sc.specialty}
              <span className="text-xs text-ink-faint">
                {sc.count}
              </span>
            </Link>
          ))}
        </div>
      </div>
    </section>
  )
}
```

Note: this changes `SpecialtyPicks` from a client component to a server component (removing `'use client'`, `useRouter`, `useSearchParams`). The buttons become `<Link>` elements pointing to dedicated routes.

**Step 2: Create PopularStates component**

Create `frontend/app/_components/PopularStates.tsx`:

```tsx
import Link from 'next/link'
import { UFS } from '@/lib/constants'

type StateCount = { state: string; count: number }

export function PopularStates({ stateCounts }: { stateCounts: StateCount[] }) {
  if (stateCounts.length === 0) return null

  return (
    <section className="border-b border-cream-dark py-6">
      <div className="mx-auto max-w-5xl px-6">
        <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-ink-muted">
          Estados com mais vagas
        </p>
        <div className="flex flex-wrap gap-2">
          {stateCounts.map((sc, i) => {
            const uf = UFS.find((u) => u.sigla === sc.state)
            return (
              <Link
                key={sc.state}
                href={`/estado/${sc.state.toLowerCase()}`}
                className="animate-fade-in inline-flex items-center gap-1.5 rounded-full bg-cream-dark/60 px-3.5 py-1.5 text-sm font-medium text-ink-light transition-all hover:bg-primary-light hover:text-primary-dark"
                style={{ animationDelay: `${300 + i * 40}ms` }}
              >
                {uf?.nome ?? sc.state}
                <span className="text-xs text-ink-faint">
                  {sc.count}
                </span>
              </Link>
            )
          })}
        </div>
      </div>
    </section>
  )
}
```

**Step 3: Add fetchStateCounts query**

Add to `frontend/lib/queries.ts`:

```typescript
export async function fetchStateCounts(): Promise<{ state: string; count: number }[]> {
  const rows = await db
    .select({
      state: vagasPublic.state,
      count: count(),
    })
    .from(vagasPublic)
    .where(isNotNull(vagasPublic.state))
    .groupBy(vagasPublic.state)
    .orderBy(desc(count()))
    .limit(10)

  return rows.map((r) => ({
    state: r.state!,
    count: r.count,
  }))
}
```

**Step 4: Update home page to include PopularStates**

In `frontend/app/page.tsx`, add the import and usage:

```typescript
import { fetchVagas, fetchFilterOptions, fetchStats, fetchSpecialtyCounts, fetchStateCounts } from '@/lib/queries'
import { Hero } from './_components/Hero'
import { SpecialtyPicks } from './_components/SpecialtyPicks'
import { PopularStates } from './_components/PopularStates'
import { VagaList } from './_components/VagaList'

type Props = {
  searchParams: Promise<Record<string, string | undefined>>
}

export default async function Page({ searchParams }: Props) {
  const params = await searchParams

  const { vagas, count } = await fetchVagas({
    specialty: params.specialty,
    city: params.city ? params.city.split(',') : undefined,
    state: params.state,
    q: params.q,
    page: params.page ? Number(params.page) : undefined,
  })
  const { specialties, cities, states } = await fetchFilterOptions(
    params.state ? { state: params.state } : undefined,
  )
  const stats = await fetchStats()
  const specialtyCounts = await fetchSpecialtyCounts()
  const stateCounts = await fetchStateCounts()

  return (
    <>
      <Hero stats={stats} />
      <SpecialtyPicks specialtyCounts={specialtyCounts} />
      <PopularStates stateCounts={stateCounts} />
      <VagaList
        initialVagas={vagas}
        initialCount={count}
        specialties={specialties}
        cities={cities}
        states={states}
      />
    </>
  )
}
```

**Step 5: Verify the build**

Run: `npm run build --prefix frontend`
Expected: Build succeeds.

**Step 6: Commit**

```
feat: add internal linking with SpecialtyPicks links and PopularStates section
```

---

## Phase 3: Content + GEO

### Task 16: Add llms.txt

**Files:**
- Create: `frontend/public/llms.txt`

**Step 1: Create llms.txt**

```
# EmpregaMed

> Maior agregador de vagas medicas do Brasil. Reune oportunidades de
> Indeed, BNE, Vagas.com, InfoJobs e PCI Concursos em um so lugar.

## O que fazemos
- Agregamos vagas medicas de 5+ fontes brasileiras
- Cobrimos 31 especialidades medicas
- Atualizamos diariamente com crawlers automatizados
- Dados disponiveis por especialidade, estado e cidade

## Especialidades cobertas
Cardiologia, Ortopedia, Pediatria, Clinica Geral, Ginecologia,
Dermatologia, Oftalmologia, Psiquiatria, Neurologia, Anestesiologia,
Cirurgia Geral, Radiologia, Urologia, Medicina do Trabalho,
Medicina da Familia, Emergencia, UTI, Oncologia, Endocrinologia,
Gastroenterologia, Nefrologia, Pneumologia, Reumatologia,
Hematologia, Infectologia, Geriatria, Medicina Esportiva,
Otorrinolaringologia, Cirurgia Plastica, Cirurgia Cardiovascular,
Medicina Nuclear

## Fontes
- Indeed Brasil (indeed.com.br)
- BNE (bne.com.br)
- Vagas.com (vagas.com.br)
- InfoJobs (infojobs.com.br)
- PCI Concursos (pciconcursos.com.br)

## Paginas principais
- Pagina inicial: https://empregamed.com.br
- Especialidades: https://empregamed.com.br/especialidade/cardiologia
- Estados: https://empregamed.com.br/estado/sp
- Cidades: https://empregamed.com.br/estado/sp/sao-paulo
```

**Step 2: Commit**

```
feat: add llms.txt for AI discoverability
```

---

### Task 17: Create "Sobre" page (E-E-A-T)

**Files:**
- Create: `frontend/app/sobre/page.tsx`

**Step 1: Create the about page**

```tsx
import type { Metadata } from 'next'
import { fetchStats, fetchAllSpecialties } from '@/lib/queries'
import { organizationJsonLd } from '@/lib/structured-data'
import { Breadcrumbs, breadcrumbJsonLd } from '@/app/_components/Breadcrumbs'

const BASE_URL = process.env.NEXT_PUBLIC_BASE_URL ?? 'https://empregamed.com.br'

export const metadata: Metadata = {
  title: 'Sobre o EmpregaMed',
  description:
    'O EmpregaMed e o maior agregador de vagas medicas do Brasil. Saiba como funciona, quantas vagas temos e quais fontes utilizamos.',
  alternates: { canonical: '/sobre' },
  openGraph: {
    title: 'Sobre o EmpregaMed',
    description:
      'O EmpregaMed e o maior agregador de vagas medicas do Brasil.',
    url: `${BASE_URL}/sobre`,
  },
}

export const revalidate = 3600

export default async function SobrePage() {
  const stats = await fetchStats()
  const specialties = await fetchAllSpecialties()

  const crumbs = [
    { label: 'Inicio', href: '/' },
    { label: 'Sobre' },
  ]

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{
          __html: JSON.stringify([
            organizationJsonLd(),
            breadcrumbJsonLd(crumbs),
          ]),
        }}
      />
      <section className="border-b border-cream-dark bg-gradient-to-b from-white to-cream">
        <div className="mx-auto max-w-5xl px-6 py-10">
          <Breadcrumbs crumbs={crumbs} />
          <h1 className="font-[family-name:var(--font-serif)] text-3xl font-bold text-ink sm:text-4xl">
            Sobre o EmpregaMed
          </h1>
        </div>
      </section>
      <article className="mx-auto max-w-3xl px-6 py-10">
        <p className="text-lg leading-relaxed text-ink-light">
          O EmpregaMed e o maior agregador de vagas medicas do Brasil. Reunimos{' '}
          <strong className="text-ink">{stats.totalVagas.toLocaleString('pt-BR')} vagas</strong> de{' '}
          <strong className="text-ink">5 fontes</strong> diferentes, cobrindo{' '}
          <strong className="text-ink">{specialties.length} especialidades</strong> em{' '}
          <strong className="text-ink">{stats.totalCities.toLocaleString('pt-BR')} cidades</strong> de{' '}
          <strong className="text-ink">{stats.totalStates} estados</strong> brasileiros.
        </p>

        <h2 className="mt-10 font-[family-name:var(--font-serif)] text-2xl font-bold text-ink">
          Como funciona
        </h2>
        <p className="mt-3 leading-relaxed text-ink-light">
          Nossos crawlers automatizados visitam diariamente os principais sites de emprego do Brasil
          — Indeed, BNE, Vagas.com, InfoJobs e PCI Concursos — e coletam todas as vagas destinadas
          a medicos. Cada vaga e normalizada, classificada por especialidade e disponibilizada em
          nossa plataforma com filtros por especialidade, estado e cidade.
        </p>

        <h2 className="mt-10 font-[family-name:var(--font-serif)] text-2xl font-bold text-ink">
          Nossa missao
        </h2>
        <p className="mt-3 leading-relaxed text-ink-light">
          Facilitar a busca de emprego para medicos no Brasil. Em vez de visitar multiplos sites de
          emprego, o medico encontra todas as oportunidades em um so lugar, com filtros especializados
          para a area medica.
        </p>

        <h2 className="mt-10 font-[family-name:var(--font-serif)] text-2xl font-bold text-ink">
          Fontes de dados
        </h2>
        <ul className="mt-3 space-y-2 text-ink-light">
          <li><strong className="text-ink">Indeed Brasil</strong> — Maior site de empregos do mundo</li>
          <li><strong className="text-ink">BNE</strong> — Banco Nacional de Empregos</li>
          <li><strong className="text-ink">Vagas.com</strong> — Plataforma brasileira de recrutamento</li>
          <li><strong className="text-ink">InfoJobs</strong> — Portal de empregos com foco no Brasil</li>
          <li><strong className="text-ink">PCI Concursos</strong> — Concursos publicos e processos seletivos</li>
        </ul>

        <h2 className="mt-10 font-[family-name:var(--font-serif)] text-2xl font-bold text-ink">
          Especialidades cobertas
        </h2>
        <p className="mt-3 leading-relaxed text-ink-light">
          Cobrimos {specialties.length} especialidades medicas, incluindo:{' '}
          {specialties.join(', ')}.
        </p>
      </article>
    </>
  )
}
```

**Step 2: Add link to Sobre in footer**

In `frontend/app/layout.tsx`, add a link in the footer:

```tsx
<p className="font-[family-name:var(--font-serif)] text-lg text-ink">
  EmpregaMed
</p>
<a href="/sobre" className="text-xs text-ink-muted hover:text-primary hover:underline">
  Sobre
</a>
```

**Step 3: Add /sobre to sitemap**

In `frontend/app/sitemap.ts`, add after the home entry:

```typescript
{
  url: `${BASE_URL}/sobre`,
  lastModified: new Date(),
  changeFrequency: 'monthly',
  priority: 0.5,
},
```

**Step 4: Verify the build**

Run: `npm run build --prefix frontend`
Expected: Build succeeds.

**Step 5: Commit**

```
feat: add /sobre page with E-E-A-T content and real-time stats
```

---

### Task 18: Add FAQ section to home page (GEO optimization)

Add a FAQ section to the home page with structured data that AI agents can extract.

**Files:**
- Create: `frontend/app/_components/FAQ.tsx`
- Modify: `frontend/app/page.tsx` (add FAQ after VagaList)

**Step 1: Create FAQ component**

```tsx
const FAQS = [
  {
    question: 'O que e o EmpregaMed?',
    answer:
      'O EmpregaMed e o maior agregador de vagas medicas do Brasil. Reunimos oportunidades de Indeed, BNE, Vagas.com, InfoJobs e PCI Concursos em um so lugar, cobrindo 31 especialidades medicas.',
  },
  {
    question: 'O EmpregaMed e gratuito?',
    answer:
      'Sim, o EmpregaMed e totalmente gratuito para medicos. Basta acessar o site, filtrar por especialidade, estado ou cidade e clicar na vaga para ser redirecionado ao site original.',
  },
  {
    question: 'Com que frequencia as vagas sao atualizadas?',
    answer:
      'Nossos crawlers automatizados atualizam as vagas diariamente, garantindo que voce veja as oportunidades mais recentes.',
  },
  {
    question: 'Quais especialidades medicas estao disponiveis?',
    answer:
      'Cobrimos 31 especialidades, incluindo Cardiologia, Ortopedia, Pediatria, Clinica Geral, Ginecologia, Dermatologia, Psiquiatria, Neurologia, Cirurgia Geral, Medicina do Trabalho, entre outras.',
  },
]

export function FAQ() {
  return (
    <section className="border-t border-cream-dark py-12">
      <div className="mx-auto max-w-3xl px-6">
        <h2 className="font-[family-name:var(--font-serif)] text-2xl font-bold text-ink">
          Perguntas frequentes
        </h2>
        <dl className="mt-6 space-y-6">
          {FAQS.map((faq) => (
            <div key={faq.question}>
              <dt className="font-semibold text-ink">{faq.question}</dt>
              <dd className="mt-1 leading-relaxed text-ink-light">{faq.answer}</dd>
            </div>
          ))}
        </dl>
      </div>
    </section>
  )
}

export function faqJsonLd() {
  return {
    '@context': 'https://schema.org',
    '@type': 'FAQPage',
    mainEntity: FAQS.map((faq) => ({
      '@type': 'Question',
      name: faq.question,
      acceptedAnswer: {
        '@type': 'Answer',
        text: faq.answer,
      },
    })),
  }
}
```

**Step 2: Add FAQ to home page**

In `frontend/app/page.tsx`, import and add:

```typescript
import { FAQ, faqJsonLd } from './_components/FAQ'
```

Add after `<VagaList>`:
```tsx
<FAQ />
```

Add JSON-LD to the page. Wrap the return in a fragment and add a script tag at the top:

```tsx
return (
  <>
    <script
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: JSON.stringify(faqJsonLd()) }}
    />
    <Hero stats={stats} />
    <SpecialtyPicks specialtyCounts={specialtyCounts} />
    <PopularStates stateCounts={stateCounts} />
    <VagaList ... />
    <FAQ />
  </>
)
```

**Step 3: Verify the build**

Run: `npm run build --prefix frontend`
Expected: Build succeeds.

**Step 4: Commit**

```
feat: add FAQ section with FAQPage JSON-LD for GEO optimization
```

---

### Task 19: Add GEO-optimized intro text to home page

Add a descriptive paragraph below the hero that contains factual, declarative statements optimized for AI citation.

**Files:**
- Modify: `frontend/app/page.tsx` (add intro section)

**Step 1: Add intro section**

After `<Hero stats={stats} />` and before `<SpecialtyPicks>`, add:

```tsx
<section className="border-b border-cream-dark bg-white/40 py-6">
  <div className="mx-auto max-w-3xl px-6 text-center">
    <p className="text-sm leading-relaxed text-ink-muted">
      O EmpregaMed agrega {stats.totalVagas.toLocaleString('pt-BR')} vagas medicas de 5 fontes
      brasileiras — Indeed, BNE, Vagas.com, InfoJobs e PCI Concursos — cobrindo 31
      especialidades em {stats.totalCities.toLocaleString('pt-BR')} cidades
      de {stats.totalStates} estados. Atualizado diariamente.
    </p>
  </div>
</section>
```

**Step 2: Verify the build**

Run: `npm run build --prefix frontend`
Expected: Build succeeds.

**Step 3: Commit**

```
feat: add GEO-optimized intro paragraph with real-time stats
```

---

### Task 20: Final verification and cleanup

**Step 1: Full build verification**

Run: `npm run build --prefix frontend`
Expected: Build succeeds with all new routes listed.

**Step 2: Verify route list**

Expected routes in build output:
- `/` (home)
- `/sobre`
- `/especialidade/[slug]` (SSG)
- `/especialidade/[slug]/[uf]` (SSG)
- `/estado/[uf]` (SSG)
- `/estado/[uf]/[cidade]` (SSG)
- `/robots.txt`
- `/sitemap.xml`

**Step 3: Lint check**

Run: `npm run lint --prefix frontend`
Expected: No errors.

**Step 4: Commit any remaining fixes**

```
chore: final cleanup for SEO implementation
```

---

## Summary

| Phase | Tasks | What it delivers |
|-------|-------|------------------|
| Phase 1 (Tasks 1-6) | Rebrand, robots.txt, sitemap, JSON-LD, OG tags, env | SEO foundation — Google can crawl and understand the site |
| Phase 2 (Tasks 7-15) | Slug utils, queries, Breadcrumbs, 4 route types, expanded sitemap, internal linking | 50+ indexable pages — captures long-tail search traffic |
| Phase 3 (Tasks 16-19) | llms.txt, /sobre page, FAQ with JSON-LD, GEO intro text | AI citability + authority + rich snippets |
| Task 20 | Final verification | Everything works together |

## Post-implementation (manual steps)

These are not code tasks — do them after deploying:

1. **Register `empregamed.com.br`** domain and configure in Vercel
2. **Set `NEXT_PUBLIC_BASE_URL`** environment variable in Vercel
3. **Set up Google Search Console** — verify domain, submit sitemap
4. **Set up analytics** (GA4 or Plausible) — add tracking script
5. **Test with Google Rich Results Test** — validate structured data
6. **Test AI citation** — ask ChatGPT/Claude/Gemini about vagas medicas no Brasil
