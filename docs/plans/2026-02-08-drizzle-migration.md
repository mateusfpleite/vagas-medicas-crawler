# Replace Supabase JS Client with Drizzle ORM

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the Supabase JS client with Drizzle ORM so the frontend queries Postgres directly from Server Components, eliminating the PostgREST middleman and enabling proper SQL aggregations (`GROUP BY`, `DISTINCT`, `COUNT`).

**Architecture:** All database queries move from Supabase PostgREST (via `@supabase/supabase-js`) to direct Postgres queries via Drizzle ORM + `postgres.js` driver. Client-side data fetching (`VagaList`, `useFilteredCities`) is replaced with Next.js URL-driven server re-renders. The `vagas_public` view and `search_vagas` function remain in Postgres unchanged.

**Tech Stack:** `drizzle-orm`, `postgres` (postgres.js driver), `drizzle-kit` (dev, schema introspection)

---

### Task 1: Install dependencies and configure Drizzle

**Files:**
- Modify: `frontend/package.json`
- Create: `frontend/drizzle.config.ts`
- Create: `frontend/lib/db/index.ts`
- Modify: `frontend/.env.local`

**Step 1: Install drizzle-orm, postgres driver, and drizzle-kit**

Run from `frontend/`:

```bash
npm install drizzle-orm postgres server-only
npm install -D drizzle-kit
```

**Step 2: Add `DATABASE_URL` to `.env.local`**

Add this line to `frontend/.env.local` (same connection string used by the crawler in the root `.env`):

```
DATABASE_URL=<same connection string used by the crawler in the root .env>
```

Keep the existing `NEXT_PUBLIC_*` vars for now — they'll be removed in Task 6.

**Step 3: Create `drizzle.config.ts`**

```ts
import { defineConfig } from 'drizzle-kit'

export default defineConfig({
  dialect: 'postgresql',
  out: './lib/db',
  dbCredentials: {
    url: process.env.DATABASE_URL!,
  },
})
```

**Step 4: Create `frontend/lib/db/index.ts`**

```ts
import { drizzle } from 'drizzle-orm/postgres-js'
import postgres from 'postgres'

const client = postgres(process.env.DATABASE_URL!, { prepare: false })
export const db = drizzle(client)
```

Note: `prepare: false` is needed because Supabase's connection pooler (PgBouncer in transaction mode) does not support prepared statements.

**Step 5: Pull the schema from the existing database**

Run from `frontend/`:

```bash
npx drizzle-kit pull
```

This introspects the live database and generates `lib/db/schema.ts` (and possibly `lib/db/relations.ts`) with the `vagas` table and `vagas_public` view definitions.

**Step 6: Verify the generated schema**

Open `frontend/lib/db/schema.ts` and confirm it contains:
- A `vagas` table with all expected columns (`id`, `external_id`, `source`, `title`, `specialty`, `city`, `state`, `salary`, `salary_min`, `salary_max`, `salary_period`, `job_type`, `company`, `description`, `benefits`, `url`, `published_at`, `first_seen_at`, etc.)
- A `vagasPublic` view (or equivalent) with the `effective_date` computed column

If the view is not generated (drizzle-kit may skip views), we'll define it manually in Task 2.

**Step 7: Verify connection works**

Create a quick test at the bottom of `lib/db/index.ts` (temporary, remove after):

```bash
npx tsx -e "const { db } = require('./lib/db'); db.execute('SELECT 1 as ok').then(r => { console.log(r); process.exit(0) })"
```

Or just proceed to Task 2 — the build will surface connection errors.

**Step 8: Commit**

```
feat: add drizzle-orm with postgres.js driver and pull schema
```

---

### Task 2: Define the `vagas_public` view schema (if needed)

**Files:**
- Modify: `frontend/lib/db/schema.ts`

`drizzle-kit pull` may not generate view definitions. If `vagasPublic` is missing from the schema, define it manually.

**Step 1: Check if schema.ts has the view**

If `vagas_public` / `vagasPublic` is already in `schema.ts`, skip this entire task.

**Step 2: Add the view definition**

Add to `schema.ts`:

```ts
import { pgView, text, integer, numeric, timestamp, jsonb, serial } from 'drizzle-orm/pg-core'

export const vagasPublic = pgView('vagas_public', {
  id: serial('id'),
  externalId: text('external_id'),
  source: text('source').notNull(),
  title: text('title').notNull(),
  location: text('location'),
  company: text('company'),
  salary: text('salary'),
  salaryMin: numeric('salary_min'),
  salaryMax: numeric('salary_max'),
  salaryPeriod: text('salary_period'),
  jobType: text('job_type'),
  specialty: text('specialty'),
  city: text('city'),
  state: text('state'),
  description: text('description'),
  benefits: jsonb('benefits'),
  url: text('url'),
  publishedAt: timestamp('published_at', { withTimezone: true }),
  firstSeenAt: timestamp('first_seen_at', { withTimezone: true }),
  effectiveDate: timestamp('effective_date', { withTimezone: true }),
}).existing()
```

The `.existing()` tells Drizzle this view already exists in the DB — don't try to create it.

**Step 3: Commit**

```
feat: add vagas_public view definition to drizzle schema
```

---

### Task 3: Rewrite `queries.ts` — remove Supabase, use Drizzle

**Files:**
- Modify: `frontend/lib/queries.ts`

This is the core task. Rewrite all 4 functions to use Drizzle instead of the Supabase client. **Keep the same exported types and function signatures** (except removing the `supabase: SupabaseClient` parameter).

**Step 1: Rewrite the full file**

```ts
import 'server-only'

import { db } from './db'
import { vagasPublic } from './db/schema'
import { eq, and, inArray, isNotNull, desc, sql, count, countDistinct, gte, ilike } from 'drizzle-orm'
import { Vaga, SiteStats, SpecialtyCount } from './types'

const PAGE_SIZE = 20

export type FetchVagasParams = {
  specialty?: string
  city?: string | string[]
  state?: string
  q?: string
  page?: number
}

export type FetchVagasResult = {
  vagas: Vaga[]
  count: number
}

export async function fetchVagas(params: FetchVagasParams): Promise<FetchVagasResult> {
  const { specialty, city, state, q, page = 1 } = params
  const offset = (page - 1) * PAGE_SIZE

  const conditions = []
  if (specialty) conditions.push(eq(vagasPublic.specialty, specialty))
  if (state) conditions.push(eq(vagasPublic.state, state))
  if (city) {
    const cities = Array.isArray(city) ? city : [city]
    conditions.push(cities.length === 1 ? eq(vagasPublic.city, cities[0]) : inArray(vagasPublic.city, cities))
  }

  if (q) {
    // search_vagas uses unaccent + ILIKE on title
    conditions.push(sql`unaccent(${vagasPublic.title}) ILIKE '%' || unaccent(${q}) || '%'`)
  }

  const where = conditions.length > 0 ? and(...conditions) : undefined

  const [rows, [{ total }]] = await Promise.all([
    db
      .select({
        id: vagasPublic.id,
        title: vagasPublic.title,
        specialty: vagasPublic.specialty,
        company: vagasPublic.company,
        city: vagasPublic.city,
        state: vagasPublic.state,
        salary: vagasPublic.salary,
        salaryMin: vagasPublic.salaryMin,
        salaryMax: vagasPublic.salaryMax,
        salaryPeriod: vagasPublic.salaryPeriod,
        jobType: vagasPublic.jobType,
        source: vagasPublic.source,
        url: vagasPublic.url,
        effectiveDate: vagasPublic.effectiveDate,
        description: vagasPublic.description,
        benefits: vagasPublic.benefits,
      })
      .from(vagasPublic)
      .where(where)
      .orderBy(desc(vagasPublic.effectiveDate))
      .limit(PAGE_SIZE)
      .offset(offset),
    db
      .select({ total: count() })
      .from(vagasPublic)
      .where(where),
  ])

  const vagas: Vaga[] = rows.map((r) => ({
    id: r.id,
    title: r.title,
    specialty: r.specialty,
    company: r.company,
    city: r.city,
    state: r.state,
    salary: r.salary,
    salary_min: r.salaryMin ? Number(r.salaryMin) : null,
    salary_max: r.salaryMax ? Number(r.salaryMax) : null,
    salary_period: r.salaryPeriod,
    job_type: r.jobType,
    source: r.source,
    url: r.url,
    effective_date: r.effectiveDate?.toISOString().split('T')[0] ?? '',
    description: r.description,
    benefits: r.benefits as string[] | null,
  }))

  return { vagas, count: total }
}

export type FilterOptions = {
  specialties: string[]
  cities: string[]
  states: string[]
}

export async function fetchFilterOptions(
  params?: { state?: string },
): Promise<FilterOptions> {
  const cityConditions = [isNotNull(vagasPublic.city)]
  if (params?.state) cityConditions.push(eq(vagasPublic.state, params.state))

  const [specialtiesRows, citiesRows, statesRows] = await Promise.all([
    db
      .selectDistinct({ specialty: vagasPublic.specialty })
      .from(vagasPublic)
      .where(isNotNull(vagasPublic.specialty))
      .orderBy(vagasPublic.specialty),
    db
      .selectDistinct({ city: vagasPublic.city })
      .from(vagasPublic)
      .where(and(...cityConditions))
      .orderBy(vagasPublic.city),
    db
      .selectDistinct({ state: vagasPublic.state })
      .from(vagasPublic)
      .where(isNotNull(vagasPublic.state))
      .orderBy(vagasPublic.state),
  ])

  return {
    specialties: specialtiesRows.map((r) => r.specialty!),
    cities: citiesRows.map((r) => r.city!),
    states: statesRows.map((r) => r.state!),
  }
}

export async function fetchStats(): Promise<SiteStats> {
  const today = new Date()
  const todayStr = today.toLocaleDateString('en-CA')
  const weekAgo = new Date(today)
  weekAgo.setDate(weekAgo.getDate() - 7)
  const weekAgoStr = weekAgo.toLocaleDateString('en-CA')

  const [
    [{ total }],
    [{ newToday }],
    [{ newThisWeek }],
    [{ totalCities }],
    [{ totalStates }],
  ] = await Promise.all([
    db.select({ total: count() }).from(vagasPublic),
    db.select({ newToday: count() }).from(vagasPublic).where(gte(vagasPublic.effectiveDate, new Date(todayStr))),
    db.select({ newThisWeek: count() }).from(vagasPublic).where(gte(vagasPublic.effectiveDate, new Date(weekAgoStr))),
    db.select({ totalCities: countDistinct(vagasPublic.city) }).from(vagasPublic).where(isNotNull(vagasPublic.city)),
    db.select({ totalStates: countDistinct(vagasPublic.state) }).from(vagasPublic).where(isNotNull(vagasPublic.state)),
  ])

  return {
    totalVagas: total,
    newToday,
    newThisWeek,
    totalCities,
    totalStates,
  }
}

export async function fetchSpecialtyCounts(): Promise<SpecialtyCount[]> {
  const rows = await db
    .select({
      specialty: vagasPublic.specialty,
      count: count(),
    })
    .from(vagasPublic)
    .where(isNotNull(vagasPublic.specialty))
    .groupBy(vagasPublic.specialty)
    .orderBy(desc(count()))
    .limit(10)

  return rows.map((r) => ({
    specialty: r.specialty!,
    count: r.count,
  }))
}
```

Key changes:
- No more `supabase: SupabaseClient` parameter — functions now use the `db` singleton directly
- `fetchSpecialtyCounts`: 10,000 rows → 10 rows (GROUP BY in SQL)
- `fetchFilterOptions`: 30,000 rows → ~260 rows total (SELECT DISTINCT in SQL)
- `fetchStats`: 20,000 rows → 5 scalar results (COUNT DISTINCT in SQL)
- `fetchVagas` with search: inlines the `unaccent` ILIKE instead of calling the `search_vagas` RPC
- Column names map from snake_case DB columns to camelCase Drizzle schema, then back to snake_case `Vaga` type in the mapping

**Step 2: Verify types compile**

```bash
cd frontend && npx tsc --noEmit
```

Expected: errors in `page.tsx`, `VagaList.tsx`, `useFilteredCities.ts` because they still pass `supabase` to these functions. That's fixed in Tasks 4-5.

**Step 3: Commit**

```
feat: rewrite queries.ts from Supabase client to Drizzle ORM
```

---

### Task 4: Update `page.tsx` — remove Supabase client

**Files:**
- Modify: `frontend/app/page.tsx`

**Step 1: Rewrite `page.tsx`**

```ts
import { fetchVagas, fetchFilterOptions, fetchStats, fetchSpecialtyCounts } from '@/lib/queries'
import { Hero } from './_components/Hero'
import { SpecialtyPicks } from './_components/SpecialtyPicks'
import { VagaList } from './_components/VagaList'

type Props = {
  searchParams: Promise<Record<string, string | undefined>>
}

export default async function Page({ searchParams }: Props) {
  const params = await searchParams

  const [{ vagas, count }, { specialties, cities, states }, stats, specialtyCounts] =
    await Promise.all([
      fetchVagas({
        specialty: params.specialty,
        city: params.city ? params.city.split(',') : undefined,
        state: params.state,
        q: params.q,
        page: params.page ? Number(params.page) : undefined,
      }),
      fetchFilterOptions(),
      fetchStats(),
      fetchSpecialtyCounts(),
    ])

  return (
    <>
      <Hero stats={stats} />
      <SpecialtyPicks specialtyCounts={specialtyCounts} />
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

Changes: removed `createClient` import and the `supabase` variable. Functions are called without the supabase parameter.

**Step 2: Commit**

```
refactor: remove Supabase client from page.tsx
```

---

### Task 5: Convert client-side fetching to server-driven navigation

**Files:**
- Modify: `frontend/app/_components/VagaList.tsx`
- Delete: `frontend/app/_hooks/useFilteredCities.ts`

The current `VagaList` and `useFilteredCities` use the **browser-side Supabase client** to refetch data when filters change. Since queries now run through Drizzle (server-only), we replace client-side fetching with URL-driven re-renders.

This works because:
- `VagaList` already pushes filter changes to URL params via `router.push()`
- `page.tsx` already reads those params and fetches server-side
- Next.js re-renders the Server Component when URL params change

**Step 1: Rewrite `VagaList.tsx`**

Remove the `useEffect` that fetches client-side, remove `createClient` import, remove `useFilteredCities`. Keep `useTransition` to show loading state during server re-renders:

```tsx
'use client'

import { useCallback, useTransition } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { Vaga } from '@/lib/types'
import { VagaCard } from './VagaCard'
import { FilterBar } from './FilterBar'
import { Pagination } from './Pagination'
import { EmptyState } from './EmptyState'
import { LoadingSkeleton } from './LoadingSkeleton'

const PAGE_SIZE = 20

type Props = {
  initialVagas: Vaga[]
  initialCount: number
  specialties: string[]
  cities: string[]
  states: string[]
}

export function VagaList({
  initialVagas,
  initialCount,
  specialties,
  cities,
  states,
}: Props) {
  const router = useRouter()
  const searchParams = useSearchParams()
  const [isPending, startTransition] = useTransition()

  const specialty = searchParams.get('specialty') ?? null
  const cityParam = searchParams.get('city') ?? ''
  const state = searchParams.get('state') ?? null
  const q = searchParams.get('q') ?? ''
  const page = Number(searchParams.get('page') ?? '1')

  const city = cityParam ? cityParam.split(',') : []
  const totalPages = Math.ceil(initialCount / PAGE_SIZE)
  const hasFilters = specialty || cityParam || state || q

  const updateURL = useCallback(
    (params: Record<string, string | null>) => {
      const sp = new URLSearchParams(searchParams.toString())
      Object.entries(params).forEach(([k, v]) => {
        if (v) sp.set(k, v)
        else sp.delete(k)
      })
      if (!('page' in params)) sp.delete('page')
      startTransition(() => {
        router.push(`?${sp.toString()}`, { scroll: false })
      })
    },
    [router, searchParams],
  )

  return (
    <div className="mx-auto max-w-5xl px-6">
      <FilterBar
        specialties={specialties}
        cities={cities}
        states={states}
        specialty={specialty}
        city={city}
        state={state}
        q={q}
        onSpecialtyChange={(v) => updateURL({ specialty: v })}
        onCityChange={(v) => updateURL({ city: v.length > 0 ? v.join(',') : null })}
        onStateChange={(v) => updateURL({ state: v, city: null })}
        onSearchChange={(v) => updateURL({ q: v || null })}
      />

      <div className="mt-6 mb-4 flex items-baseline justify-between">
        <p className="text-[0.82rem] text-ink-muted">
          <span className="font-semibold tabular-nums text-ink">{initialCount.toLocaleString('pt-BR')}</span>{' '}
          {initialCount === 1 ? 'vaga encontrada' : 'vagas encontradas'}
          {hasFilters && (
            <button
              onClick={() => router.push('/')}
              className="ml-2 cursor-pointer text-primary hover:text-primary-dark"
            >
              Limpar filtros
            </button>
          )}
        </p>
      </div>

      {isPending ? (
        <LoadingSkeleton />
      ) : (
        <>
          <div className="flex flex-col gap-3">
            {initialVagas.length === 0 ? (
              <EmptyState />
            ) : (
              initialVagas.map((vaga, i) => (
                <VagaCard key={vaga.id} vaga={vaga} index={i} />
              ))
            )}
          </div>

          <Pagination
            page={page}
            totalPages={totalPages}
            onPageChange={(p) => updateURL({ page: String(p) })}
          />
        </>
      )}
    </div>
  )
}
```

Key changes:
- Removed `useState` for vagas/count — uses `initialVagas`/`initialCount` directly (server always provides fresh data)
- Removed `useEffect` that fetched client-side on param change
- Removed `createClient` and `fetchVagas` imports
- Removed `useFilteredCities` — cities are now passed from the server
- **Kept `useTransition` + `LoadingSkeleton`** — `router.push()` is wrapped in `startTransition()` so `isPending` is true while the server re-renders, preserving the loading skeleton UX

**Step 2: Update `page.tsx` to pass state-filtered cities**

Modify the `fetchFilterOptions` call in `page.tsx` to pass the state param:

```ts
fetchFilterOptions(params.state ? { state: params.state } : undefined),
```

This ensures that when a state is selected, only cities from that state are passed to VagaList.

**Step 3: Delete `useFilteredCities.ts`**

```bash
rm frontend/app/_hooks/useFilteredCities.ts
```

If the `_hooks/` directory is now empty, delete it too.

**Step 4: Verify build**

```bash
cd frontend && npx tsc --noEmit
```

Expected: no type errors.

**Step 5: Commit**

```
refactor: convert VagaList to server-driven rendering, remove client-side fetching
```

---

### Task 6: Remove Supabase packages and files

**Files:**
- Delete: `frontend/lib/supabase/client.ts`
- Delete: `frontend/lib/supabase/server.ts`
- Modify: `frontend/package.json`
- Modify: `frontend/.env.local`

**Step 1: Verify no remaining Supabase imports**

```bash
grep -r "supabase" frontend/app/ frontend/lib/ --include="*.ts" --include="*.tsx" | grep -v node_modules | grep -v ".next"
```

Expected: no results (or only references in plan docs).

**Step 2: Delete Supabase client files**

```bash
rm frontend/lib/supabase/client.ts frontend/lib/supabase/server.ts
rmdir frontend/lib/supabase
```

**Step 3: Uninstall Supabase packages**

```bash
cd frontend && npm uninstall @supabase/ssr @supabase/supabase-js
```

**Step 4: Clean up `.env.local`**

Remove the two `NEXT_PUBLIC_*` lines. The file should only contain:

```
DATABASE_URL=<same connection string from root .env>
```

Since `DATABASE_URL` is not prefixed with `NEXT_PUBLIC_`, it's never exposed to the browser.

**Step 5: Verify build**

```bash
cd frontend && npm run build
```

Expected: build succeeds with no errors.

**Step 6: Commit**

```
chore: remove Supabase JS client packages and config
```

---

### Task 7: Smoke test the full flow

**Step 1: Start dev server**

```bash
cd frontend && npm run dev
```

**Step 2: Test manually**

1. Load the home page — verify vagas load, stats display, specialty picks show
2. Click a specialty pick — verify URL updates, vagas filter
3. Select a state in the filter bar — verify cities dropdown updates to that state's cities
4. Type in the search box — verify accent-insensitive search works (e.g., "clinico" matches "Clínico")
5. Navigate pages — verify pagination works
6. Clear filters — verify all vagas return

**Step 3: Check the Network tab**

- Confirm there are **no requests to `supabase.co`** (PostgREST is gone)
- All data comes from the Next.js server render

**Step 4: Final commit if any adjustments needed**

```
fix: address smoke test findings
```
