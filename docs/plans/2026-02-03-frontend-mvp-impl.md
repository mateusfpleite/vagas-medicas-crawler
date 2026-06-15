# Frontend MVP Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a public Next.js frontend for doctors to search medical job postings aggregated from Brazilian job boards, with SEO-friendly server rendering and interactive filters.

**Architecture:** Next.js 15 App Router with Server Components for initial SEO render, Client Components for interactive filtering. Data comes from Supabase PostgreSQL via `vagas_public` view (RLS configured, anon SELECT only). Text search uses `search_vagas` RPC with `unaccent` for accent-insensitive matching.

**Tech Stack:** Next.js 15, TypeScript, Tailwind CSS, @headlessui/react, @supabase/supabase-js, @supabase/ssr

**Design doc:** `docs/plans/2026-02-03-frontend-mvp.md`

---

### Task 1: Scaffold Next.js project

**Files:**
- Create: `frontend/` (via create-next-app)
- Create: `frontend/.env.local`

**Step 1: Create Next.js app**

Run from repo root:

```bash
npx create-next-app@latest frontend \
  --typescript \
  --tailwind \
  --eslint \
  --app \
  --src-dir=no \
  --import-alias="@/*" \
  --use-npm
```

Answer "No" to Turbopack if prompted.

**Step 2: Install dependencies**

```bash
cd frontend
npm install @supabase/supabase-js @supabase/ssr @headlessui/react
```

**Step 3: Create `.env.local`**

Create `frontend/.env.local` with the Supabase credentials (get URL and anon key from Supabase dashboard > Settings > API):

```
NEXT_PUBLIC_SUPABASE_URL=<your-supabase-url>
NEXT_PUBLIC_SUPABASE_ANON_KEY=<your-supabase-anon-key>
```

**Step 4: Verify dev server starts**

```bash
cd frontend && npm run dev
```

Expected: Next.js dev server running on localhost:3000, default page renders.

**Step 5: Commit**

```bash
git add frontend/
git commit -m "feat: scaffold Next.js 15 frontend with Tailwind and Supabase deps"
```

---

### Task 2: Supabase clients and types

**Files:**
- Create: `frontend/lib/supabase/server.ts`
- Create: `frontend/lib/supabase/client.ts`
- Create: `frontend/lib/types.ts`

**Step 1: Create the Vaga type**

Create `frontend/lib/types.ts`:

```ts
export type Vaga = {
  id: number
  title: string
  specialty: string | null
  company: string | null
  city: string | null
  state: string | null
  salary: string | null
  salary_min: number | null
  salary_max: number | null
  salary_period: string | null
  job_type: string | null
  source: string
  url: string
  description: string | null
  benefits: string[] | null
  effective_date: string
}
```

**Step 2: Create the browser Supabase client**

Create `frontend/lib/supabase/client.ts`:

```ts
import { createBrowserClient } from '@supabase/ssr'

export function createClient() {
  return createBrowserClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
  )
}
```

**Step 3: Create the server Supabase client**

Create `frontend/lib/supabase/server.ts`:

```ts
import { createServerClient } from '@supabase/ssr'
import { cookies } from 'next/headers'

export async function createClient() {
  const cookieStore = await cookies()
  return createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return cookieStore.getAll()
        },
        setAll(cookiesToSet) {
          try {
            cookiesToSet.forEach(({ name, value, options }) =>
              cookieStore.set(name, value, options),
            )
          } catch {
            // setAll called from Server Component — ignore
          }
        },
      },
    },
  )
}
```

**Step 4: Verify compilation**

```bash
cd frontend && npx tsc --noEmit
```

Expected: no type errors.

**Step 5: Commit**

```bash
git add frontend/lib/
git commit -m "feat: add Supabase clients (server + browser) and Vaga type"
```

---

### Task 3: Query layer

**Files:**
- Create: `frontend/lib/queries.ts`

**Step 1: Create the shared query functions**

Create `frontend/lib/queries.ts`:

```ts
import { SupabaseClient } from '@supabase/supabase-js'
import { Vaga } from './types'

const LISTING_COLUMNS =
  'id, title, specialty, company, city, state, salary, salary_min, salary_max, salary_period, job_type, source, url, effective_date, description, benefits'

const PAGE_SIZE = 20

export type FetchVagasParams = {
  specialty?: string
  city?: string
  q?: string
  page?: number
}

export type FetchVagasResult = {
  vagas: Vaga[]
  count: number
}

export async function fetchVagas(
  supabase: SupabaseClient,
  params: FetchVagasParams,
): Promise<FetchVagasResult> {
  const { specialty, city, q, page = 1 } = params
  const offset = (page - 1) * PAGE_SIZE

  if (q) {
    // Accent-insensitive search via RPC
    let query = supabase
      .rpc('search_vagas', { search_term: q }, { count: 'exact' })
      .select(LISTING_COLUMNS)
      .order('effective_date', { ascending: false })

    if (specialty) query = query.eq('specialty', specialty)
    if (city) query = query.eq('city', city)

    query = query.range(offset, offset + PAGE_SIZE - 1)

    const { data, count, error } = await query
    if (error) throw error
    return { vagas: (data ?? []) as Vaga[], count: count ?? 0 }
  }

  let query = supabase
    .from('vagas_public')
    .select(LISTING_COLUMNS, { count: 'exact' })
    .order('effective_date', { ascending: false })

  if (specialty) query = query.eq('specialty', specialty)
  if (city) query = query.eq('city', city)

  query = query.range(offset, offset + PAGE_SIZE - 1)

  const { data, count, error } = await query
  if (error) throw error
  return { vagas: (data ?? []) as Vaga[], count: count ?? 0 }
}

export async function fetchFilterOptions(supabase: SupabaseClient) {
  const [specialtiesRes, citiesRes] = await Promise.all([
    supabase
      .from('vagas_public')
      .select('specialty')
      .not('specialty', 'is', null)
      .order('specialty'),
    supabase
      .from('vagas_public')
      .select('city')
      .not('city', 'is', null)
      .order('city'),
  ])

  const specialties = [
    ...new Set((specialtiesRes.data ?? []).map((r) => r.specialty as string)),
  ]
  const cities = [
    ...new Set((citiesRes.data ?? []).map((r) => r.city as string)),
  ]

  return { specialties, cities }
}
```

**Step 2: Verify compilation**

```bash
cd frontend && npx tsc --noEmit
```

**Step 3: Commit**

```bash
git add frontend/lib/queries.ts
git commit -m "feat: add query layer with fetchVagas and fetchFilterOptions"
```

---

### Task 4: VagaCard component

**Files:**
- Create: `frontend/app/_components/VagaCard.tsx`

**Step 1: Create VagaCard**

Create `frontend/app/_components/VagaCard.tsx`:

```tsx
'use client'

import { useState } from 'react'
import { Vaga } from '@/lib/types'

const SOURCE_LABELS: Record<string, string> = {
  indeed: 'Indeed',
  vagas_com: 'Vagas.com',
  bne: 'BNE',
  infojobs: 'InfoJobs',
}

function formatSalary(vaga: Vaga): string | null {
  if (vaga.salary) return vaga.salary
  if (vaga.salary_min == null && vaga.salary_max == null) return null

  const fmt = (n: number) =>
    n.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 })

  const period = vaga.salary_period === 'HOURLY' ? '/h' : vaga.salary_period === 'YEARLY' ? '/ano' : '/mês'

  if (vaga.salary_min != null && vaga.salary_max != null) {
    return `${fmt(vaga.salary_min)} - ${fmt(vaga.salary_max)}${period}`
  }
  if (vaga.salary_min != null) return `A partir de ${fmt(vaga.salary_min)}${period}`
  return `Até ${fmt(vaga.salary_max!)}${period}`
}

function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime()
  const days = Math.floor(diff / 86400000)
  if (days === 0) return 'Hoje'
  if (days === 1) return 'Ontem'
  if (days < 30) return `Há ${days} dias`
  const months = Math.floor(days / 30)
  return months === 1 ? 'Há 1 mês' : `Há ${months} meses`
}

export function VagaCard({ vaga }: { vaga: Vaga }) {
  const [expanded, setExpanded] = useState(false)
  const salary = formatSalary(vaga)

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
      <div
        className="cursor-pointer"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0 flex-1">
            <h2 className="text-lg font-semibold text-gray-900">{vaga.title}</h2>
            <p className="text-sm text-gray-600">
              {vaga.company ?? 'Confidencial'}
            </p>
          </div>
          <div className="flex shrink-0 flex-col items-end gap-1">
            {vaga.specialty && (
              <span className="rounded-full bg-blue-100 px-2.5 py-0.5 text-xs font-medium text-blue-800">
                {vaga.specialty}
              </span>
            )}
            <span className="rounded-full bg-gray-100 px-2.5 py-0.5 text-xs font-medium text-gray-600">
              {SOURCE_LABELS[vaga.source] ?? vaga.source}
            </span>
          </div>
        </div>

        <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-gray-500">
          {(vaga.city || vaga.state) && (
            <span>{[vaga.city, vaga.state].filter(Boolean).join(', ')}</span>
          )}
          {salary && <span className="font-medium text-green-700">{salary}</span>}
          <span>{timeAgo(vaga.effective_date)}</span>
        </div>
      </div>

      {expanded && (
        <div className="mt-3 border-t border-gray-100 pt-3">
          {vaga.description && (
            <p className="whitespace-pre-line text-sm text-gray-700">
              {vaga.description.length > 500
                ? vaga.description.slice(0, 500) + '…'
                : vaga.description}
            </p>
          )}
          {vaga.benefits && vaga.benefits.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1">
              {vaga.benefits.map((b) => (
                <span
                  key={b}
                  className="rounded bg-green-50 px-2 py-0.5 text-xs text-green-700"
                >
                  {b}
                </span>
              ))}
            </div>
          )}
          <a
            href={vaga.url}
            target="_blank"
            rel="noopener noreferrer"
            className="mt-3 inline-block text-sm font-medium text-blue-600 hover:text-blue-800"
            onClick={(e) => e.stopPropagation()}
          >
            Ver vaga →
          </a>
        </div>
      )}

      {!expanded && (
        <div className="mt-2 flex justify-end">
          <a
            href={vaga.url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm font-medium text-blue-600 hover:text-blue-800"
          >
            Ver vaga →
          </a>
        </div>
      )}
    </div>
  )
}
```

**Step 2: Verify compilation**

```bash
cd frontend && npx tsc --noEmit
```

**Step 3: Commit**

```bash
git add frontend/app/_components/VagaCard.tsx
git commit -m "feat: add expandable VagaCard component"
```

---

### Task 5: Combobox component

**Files:**
- Create: `frontend/app/_components/Combobox.tsx`

**Step 1: Create Combobox wrapper**

Create `frontend/app/_components/Combobox.tsx`:

```tsx
'use client'

import { useState } from 'react'
import {
  Combobox as HeadlessCombobox,
  ComboboxButton,
  ComboboxInput,
  ComboboxOption,
  ComboboxOptions,
} from '@headlessui/react'

type Props = {
  label: string
  options: string[]
  value: string | null
  onChange: (value: string | null) => void
  placeholder?: string
}

export function Combobox({ label, options, value, onChange, placeholder }: Props) {
  const [query, setQuery] = useState('')

  const filtered =
    query === ''
      ? options
      : options.filter((o) =>
          o.toLowerCase().includes(query.toLowerCase()),
        )

  return (
    <HeadlessCombobox
      value={value}
      onChange={(val) => {
        onChange(val)
        setQuery('')
      }}
      onClose={() => setQuery('')}
    >
      <div className="relative">
        <label className="mb-1 block text-xs font-medium text-gray-500">
          {label}
        </label>
        <div className="relative">
          <ComboboxInput
            className="w-full rounded-md border border-gray-300 bg-white py-2 pl-3 pr-8 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            displayValue={(v: string | null) => v ?? ''}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={placeholder}
          />
          {value && (
            <button
              type="button"
              className="absolute inset-y-0 right-6 flex items-center px-1 text-gray-400 hover:text-gray-600"
              onClick={(e) => {
                e.stopPropagation()
                onChange(null)
                setQuery('')
              }}
            >
              ✕
            </button>
          )}
          <ComboboxButton className="absolute inset-y-0 right-0 flex items-center px-2 text-gray-400">
            ▼
          </ComboboxButton>
        </div>
        <ComboboxOptions className="absolute z-10 mt-1 max-h-60 w-full overflow-auto rounded-md bg-white py-1 text-sm shadow-lg ring-1 ring-black/5">
          {filtered.length === 0 ? (
            <div className="px-3 py-2 text-gray-500">Nenhum resultado</div>
          ) : (
            filtered.map((option) => (
              <ComboboxOption
                key={option}
                value={option}
                className="cursor-pointer select-none px-3 py-2 data-[focus]:bg-blue-50 data-[selected]:font-medium"
              >
                {option}
              </ComboboxOption>
            ))
          )}
        </ComboboxOptions>
      </div>
    </HeadlessCombobox>
  )
}
```

**Step 2: Verify compilation**

```bash
cd frontend && npx tsc --noEmit
```

**Step 3: Commit**

```bash
git add frontend/app/_components/Combobox.tsx
git commit -m "feat: add searchable Combobox using Headless UI"
```

---

### Task 6: Pagination component

**Files:**
- Create: `frontend/app/_components/Pagination.tsx`

**Step 1: Create Pagination**

Create `frontend/app/_components/Pagination.tsx`:

```tsx
'use client'

type Props = {
  page: number
  totalPages: number
  onPageChange: (page: number) => void
}

export function Pagination({ page, totalPages, onPageChange }: Props) {
  if (totalPages <= 1) return null

  return (
    <div className="flex items-center justify-center gap-4 py-4">
      <button
        onClick={() => onPageChange(page - 1)}
        disabled={page <= 1}
        className="rounded-md border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
      >
        ← Anterior
      </button>
      <span className="text-sm text-gray-600">
        Página {page} de {totalPages}
      </span>
      <button
        onClick={() => onPageChange(page + 1)}
        disabled={page >= totalPages}
        className="rounded-md border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
      >
        Próxima →
      </button>
    </div>
  )
}
```

**Step 2: Verify compilation**

```bash
cd frontend && npx tsc --noEmit
```

**Step 3: Commit**

```bash
git add frontend/app/_components/Pagination.tsx
git commit -m "feat: add Pagination component"
```

---

### Task 7: VagaList — main Client Component

**Files:**
- Create: `frontend/app/_components/VagaList.tsx`

**Step 1: Create VagaList**

Create `frontend/app/_components/VagaList.tsx`:

```tsx
'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { createClient } from '@/lib/supabase/client'
import { fetchVagas } from '@/lib/queries'
import { Vaga } from '@/lib/types'
import { VagaCard } from './VagaCard'
import { Combobox } from './Combobox'
import { Pagination } from './Pagination'

const PAGE_SIZE = 20

type Props = {
  initialVagas: Vaga[]
  initialCount: number
  specialties: string[]
  cities: string[]
}

export function VagaList({ initialVagas, initialCount, specialties, cities }: Props) {
  const router = useRouter()
  const searchParams = useSearchParams()

  const specialty = searchParams.get('specialty') ?? null
  const city = searchParams.get('city') ?? null
  const q = searchParams.get('q') ?? ''
  const page = Number(searchParams.get('page') ?? '1')

  const [vagas, setVagas] = useState(initialVagas)
  const [count, setCount] = useState(initialCount)
  const [loading, setLoading] = useState(false)

  const isInitialMount = useRef(true)
  const debounceRef = useRef<ReturnType<typeof setTimeout>>()

  const totalPages = Math.ceil(count / PAGE_SIZE)

  const updateURL = useCallback(
    (params: Record<string, string | null>) => {
      const sp = new URLSearchParams(searchParams.toString())
      Object.entries(params).forEach(([k, v]) => {
        if (v) sp.set(k, v)
        else sp.delete(k)
      })
      // Reset page when filters change (unless page itself is being set)
      if (!('page' in params)) sp.delete('page')
      router.push(`?${sp.toString()}`, { scroll: false })
    },
    [router, searchParams],
  )

  useEffect(() => {
    if (isInitialMount.current) {
      isInitialMount.current = false
      return
    }

    setLoading(true)
    const supabase = createClient()
    fetchVagas(supabase, {
      specialty: specialty ?? undefined,
      city: city ?? undefined,
      q: q || undefined,
      page,
    })
      .then(({ vagas, count }) => {
        setVagas(vagas)
        setCount(count)
      })
      .finally(() => setLoading(false))
  }, [specialty, city, q, page])

  const handleSearch = (value: string) => {
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => {
      updateURL({ q: value || null })
    }, 300)
  }

  return (
    <div>
      {/* Filters */}
      <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-end">
        <div className="w-full sm:w-56">
          <Combobox
            label="Especialidade"
            options={specialties}
            value={specialty}
            onChange={(v) => updateURL({ specialty: v })}
            placeholder="Todas"
          />
        </div>
        <div className="w-full sm:w-56">
          <Combobox
            label="Cidade"
            options={cities}
            value={city}
            onChange={(v) => updateURL({ city: v })}
            placeholder="Todas"
          />
        </div>
        <div className="w-full sm:flex-1">
          <label className="mb-1 block text-xs font-medium text-gray-500">
            Buscar
          </label>
          <input
            type="text"
            defaultValue={q}
            onChange={(e) => handleSearch(e.target.value)}
            placeholder="Buscar no título..."
            className="w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
        </div>
      </div>

      {/* Results count */}
      <p className="mb-4 text-sm text-gray-500">
        {count} {count === 1 ? 'vaga encontrada' : 'vagas encontradas'}
      </p>

      {/* Loading */}
      {loading && (
        <div className="py-8 text-center text-sm text-gray-400">
          Carregando...
        </div>
      )}

      {/* Vaga list */}
      {!loading && (
        <div className="flex flex-col gap-3">
          {vagas.length === 0 ? (
            <p className="py-8 text-center text-gray-500">
              Nenhuma vaga encontrada com esses filtros.
            </p>
          ) : (
            vagas.map((vaga) => <VagaCard key={vaga.id} vaga={vaga} />)
          )}
        </div>
      )}

      {/* Pagination */}
      {!loading && (
        <Pagination
          page={page}
          totalPages={totalPages}
          onPageChange={(p) => updateURL({ page: String(p) })}
        />
      )}
    </div>
  )
}
```

**Step 2: Verify compilation**

```bash
cd frontend && npx tsc --noEmit
```

**Step 3: Commit**

```bash
git add frontend/app/_components/VagaList.tsx
git commit -m "feat: add VagaList with filters, pagination, and URL sync"
```

---

### Task 8: Layout and Page (Server Components)

**Files:**
- Modify: `frontend/app/layout.tsx`
- Modify: `frontend/app/page.tsx`

**Step 1: Update layout.tsx**

Replace the contents of `frontend/app/layout.tsx`:

```tsx
import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'

const inter = Inter({ subsets: ['latin'] })

export const metadata: Metadata = {
  title: 'Vagas Médicas — Oportunidades para médicos no Brasil',
  description:
    'Encontre vagas médicas agregadas dos principais sites de emprego do Brasil. Filtre por especialidade, cidade e mais.',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="pt-BR">
      <body className={`${inter.className} bg-gray-50 text-gray-900 antialiased`}>
        <header className="border-b border-gray-200 bg-white">
          <div className="mx-auto max-w-4xl px-4 py-6">
            <h1 className="text-2xl font-bold text-gray-900">Vagas Médicas</h1>
            <p className="text-sm text-gray-500">
              Oportunidades para médicos em todo o Brasil
            </p>
          </div>
        </header>
        <main className="mx-auto max-w-4xl px-4 py-6">{children}</main>
      </body>
    </html>
  )
}
```

**Step 2: Update page.tsx**

Replace the contents of `frontend/app/page.tsx`:

```tsx
import { createClient } from '@/lib/supabase/server'
import { fetchVagas, fetchFilterOptions } from '@/lib/queries'
import { VagaList } from './_components/VagaList'

type Props = {
  searchParams: Promise<Record<string, string | undefined>>
}

export default async function Page({ searchParams }: Props) {
  const params = await searchParams
  const supabase = await createClient()

  const [{ vagas, count }, { specialties, cities }] = await Promise.all([
    fetchVagas(supabase, {
      specialty: params.specialty,
      city: params.city,
      q: params.q,
      page: params.page ? Number(params.page) : undefined,
    }),
    fetchFilterOptions(supabase),
  ])

  return (
    <VagaList
      initialVagas={vagas}
      initialCount={count}
      specialties={specialties}
      cities={cities}
    />
  )
}
```

**Step 3: Verify dev server renders the page**

```bash
cd frontend && npm run dev
```

Open http://localhost:3000 — should show the header, filters, and vagas loaded from Supabase.

**Step 4: Commit**

```bash
git add frontend/app/layout.tsx frontend/app/page.tsx
git commit -m "feat: add layout and server-rendered page with SSR filtering"
```

---

### Task 9: Smoke test and polish

**Step 1: Test filters**

Open http://localhost:3000 and verify:
- Specialty combobox shows options and filters
- City combobox shows options and filters
- Text search works (with and without accents)
- URL updates with query params
- Pagination works
- Cards expand to show description and benefits
- "Ver vaga" link opens original URL in new tab

**Step 2: Test SSR**

Verify SEO rendering:

```bash
curl -s http://localhost:3000 | grep -c '<h2'
```

Expected: should output a number > 0 (vaga titles in HTML source).

Test filtered SSR:

```bash
curl -s "http://localhost:3000/?specialty=Cardiologista" | grep -ci "cardiologista"
```

Expected: should output a number > 0.

**Step 3: Fix any issues found during testing**

Address any visual or functional issues.

**Step 4: Commit**

```bash
git add -A
git commit -m "fix: polish and fixes from smoke testing"
```

---

### Task 10: Production build verification

**Step 1: Run production build**

```bash
cd frontend && npm run build
```

Expected: build succeeds with no errors.

**Step 2: Test production server**

```bash
cd frontend && npm start
```

Open http://localhost:3000 — verify everything works as in dev.

**Step 3: Final commit**

```bash
git add -A
git commit -m "chore: verify production build"
```
