# Frontend Redesign — Warm/Acolhedor Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Redesign the vagas-medicas frontend from a functional MVP to a warm, welcoming single-page experience with hero section, animated stats, specialty picks, state filtering, freshness tags, and improved cards/pagination.

**Architecture:** Server-side data fetching in `page.tsx` feeds Hero/SpecialtyPicks. Client-side `VagaList` owns filters (delegated to `FilterBar`), results, and pagination. New queries (`fetchStats`, `fetchSpecialtyCounts`) hit `vagas_public` view — no DB schema changes. Animations are pure CSS + IntersectionObserver. No new npm dependencies.

**Tech Stack:** Next.js 16 (App Router), React 19, Tailwind CSS 4, Supabase JS, Headless UI, Google Fonts via `next/font/google` (Fraunces + Source Sans 3).

---

## Current File Inventory

```
frontend/
  app/
    globals.css          ← modify
    layout.tsx           ← modify
    page.tsx             ← modify
    _components/
      Combobox.tsx       ← minor style tweaks
      Pagination.tsx     ← modify (numbered buttons)
      VagaCard.tsx       ← modify (redesign)
      VagaList.tsx       ← modify (delegate filters)
  lib/
    types.ts             ← modify (add SiteStats, SpecialtyCount)
    queries.ts           ← modify (add fetchStats, fetchSpecialtyCounts, state param)
    supabase/
      client.ts          ← keep
      server.ts          ← keep
```

---

## Task 1: Update CSS theme and animations

**Files:**
- Modify: `frontend/app/globals.css`

**Step 1: Replace the `@theme inline` block with the new warm palette**

Replace the entire content of `globals.css` with:

```css
@import "tailwindcss";

@theme inline {
  /* Backgrounds */
  --color-cream: #faf7f2;
  --color-cream-dark: #f0e9df;
  --color-surface: #ffffff;
  --color-surface-hover: #fefcf9;

  /* Primary — warm teal */
  --color-primary: #1a7a6d;
  --color-primary-light: #e8f5f0;
  --color-primary-dark: #115c52;

  /* Text — warm, not blue-shifted */
  --color-ink: #2d2a26;
  --color-ink-light: #4a4540;
  --color-ink-muted: #8a8278;
  --color-ink-faint: #b5ada3;

  /* Accent — terracota */
  --color-accent: #c4704b;
  --color-accent-light: #fdf3ee;

  /* Semantic */
  --color-fresh: #2d8a5e;
  --color-fresh-light: #edf7f1;
  --color-salary: #b8860b;
  --color-salary-light: #fdf8eb;

  /* Source badges */
  --color-source-indeed: #2557a7;
  --color-source-vagas: #e8590c;
  --color-source-bne: #7c3aed;
  --color-source-infojobs: #0891b2;
}

body {
  background: var(--color-cream);
  color: var(--color-ink);
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

/* Subtle noise texture on body */
body::before {
  content: '';
  position: fixed;
  inset: 0;
  pointer-events: none;
  z-index: 9999;
  opacity: 0.015;
  background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E");
}

/* Custom scrollbar */
::-webkit-scrollbar {
  width: 6px;
}

::-webkit-scrollbar-track {
  background: transparent;
}

::-webkit-scrollbar-thumb {
  background: var(--color-ink-muted);
  border-radius: 3px;
}

/* --- Animations --- */

@keyframes fadeSlideUp {
  from { opacity: 0; transform: translateY(12px); }
  to { opacity: 1; transform: translateY(0); }
}

.animate-fade-slide-up {
  animation: fadeSlideUp 0.5s ease-out both;
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

.animate-fade-in {
  animation: fadeIn 0.4s ease-out both;
}

@keyframes slideUp {
  from { opacity: 0; transform: translateY(16px); }
  to { opacity: 1; transform: translateY(0); }
}

.animate-slide-up {
  animation: slideUp 0.35s ease-out both;
}

@keyframes pulseSoft {
  0%, 100% { opacity: 0.4; }
  50% { opacity: 1; }
}

.animate-pulse-soft {
  animation: pulseSoft 1.5s ease-in-out infinite;
}

@keyframes livePulse {
  0%, 100% { transform: scale(1); opacity: 1; }
  50% { transform: scale(1.4); opacity: 0.6; }
}

.animate-live-pulse {
  animation: livePulse 2s ease-in-out infinite;
}

/* Card expand using CSS Grid rows trick */
.card-expand-grid {
  display: grid;
  grid-template-rows: 0fr;
  transition: grid-template-rows 0.3s ease-out;
}

.card-expand-grid[data-expanded="true"] {
  grid-template-rows: 1fr;
}

.card-expand-grid > div {
  overflow: hidden;
}

/* Sticky filter bar transition */
.filter-bar-sticky {
  transition: background-color 0.2s ease, backdrop-filter 0.2s ease, box-shadow 0.2s ease;
}

.filter-bar-sticky[data-stuck="true"] {
  background-color: rgb(250 247 242 / 0.95);
  backdrop-filter: blur(8px);
  box-shadow: 0 1px 3px rgb(0 0 0 / 0.06);
}
```

**Step 2: Verify build**

Run: `cd frontend && npm run build`
Expected: Build succeeds. **Note:** Removing `teal`/`emerald`/`amber`/`rose` tokens means existing components will render with broken colors until they are rewritten in later tasks. Tailwind 4 does not error on undefined utilities, so the build passes but the site is visually broken at dev time until Task 13. This is expected.

**Step 3: Commit**

```
feat(frontend): update CSS theme to warm palette + new animations
```

---

## Task 2: Update fonts and layout (header + footer)

**Files:**
- Modify: `frontend/app/layout.tsx`

**Step 1: Replace layout.tsx content**

Replace the entire content with:

```tsx
import type { Metadata } from 'next'
import { Fraunces, Source_Sans_3 } from 'next/font/google'
import './globals.css'

const fraunces = Fraunces({
  subsets: ['latin'],
  variable: '--font-serif',
  display: 'swap',
})

const sourceSans = Source_Sans_3({
  subsets: ['latin', 'latin-ext'],
  variable: '--font-sans',
  display: 'swap',
})

export const metadata: Metadata = {
  title: 'Vagas Medicas — Oportunidades para medicos no Brasil',
  description:
    'Encontre vagas medicas agregadas dos principais sites de emprego do Brasil. Filtre por especialidade, cidade, estado e mais.',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="pt-BR" className={`${fraunces.variable} ${sourceSans.variable}`}>
      <body className="font-[family-name:var(--font-sans)]">
        <main>{children}</main>
        <footer className="border-t border-cream-dark bg-cream-dark/30 py-10">
          <div className="mx-auto max-w-5xl px-6">
            <div className="flex flex-col items-center gap-4 text-center">
              <p className="font-[family-name:var(--font-serif)] text-lg text-ink">
                Vagas Medicas
              </p>
              <div className="flex flex-wrap items-center justify-center gap-x-3 gap-y-1 text-xs text-ink-muted">
                <span>Fontes:</span>
                <span className="font-medium text-source-indeed">Indeed</span>
                <span>·</span>
                <span className="font-medium text-source-bne">BNE</span>
                <span>·</span>
                <span className="font-medium text-source-vagas">Vagas.com</span>
                <span>·</span>
                <span className="font-medium text-source-infojobs">InfoJobs</span>
              </div>
              <p className="text-xs text-ink-faint">
                Atualizado diariamente · Dados agregados automaticamente
              </p>
            </div>
          </div>
        </footer>
      </body>
    </html>
  )
}
```

Note: The old `<header>` is removed — the Hero component (Task 6) replaces it. The `<main>` no longer has padding/max-width since each section controls its own width.

**Step 2: Verify build**

Run: `cd frontend && npm run build`
Expected: Build succeeds.

**Step 3: Commit**

```
feat(frontend): switch fonts to Fraunces + Source Sans 3, expand footer
```

---

## Task 3: Add constants and utility functions

**Files:**
- Create: `frontend/lib/constants.ts`
- Create: `frontend/lib/utils.ts`

**Step 1: Create constants.ts with UF data**

```ts
export type UF = {
  sigla: string
  nome: string
  regiao: string
}

export const UFS: UF[] = [
  // Norte
  { sigla: 'AC', nome: 'Acre', regiao: 'Norte' },
  { sigla: 'AP', nome: 'Amapa', regiao: 'Norte' },
  { sigla: 'AM', nome: 'Amazonas', regiao: 'Norte' },
  { sigla: 'PA', nome: 'Para', regiao: 'Norte' },
  { sigla: 'RO', nome: 'Rondonia', regiao: 'Norte' },
  { sigla: 'RR', nome: 'Roraima', regiao: 'Norte' },
  { sigla: 'TO', nome: 'Tocantins', regiao: 'Norte' },
  // Nordeste
  { sigla: 'AL', nome: 'Alagoas', regiao: 'Nordeste' },
  { sigla: 'BA', nome: 'Bahia', regiao: 'Nordeste' },
  { sigla: 'CE', nome: 'Ceara', regiao: 'Nordeste' },
  { sigla: 'MA', nome: 'Maranhao', regiao: 'Nordeste' },
  { sigla: 'PB', nome: 'Paraiba', regiao: 'Nordeste' },
  { sigla: 'PE', nome: 'Pernambuco', regiao: 'Nordeste' },
  { sigla: 'PI', nome: 'Piaui', regiao: 'Nordeste' },
  { sigla: 'RN', nome: 'Rio Grande do Norte', regiao: 'Nordeste' },
  { sigla: 'SE', nome: 'Sergipe', regiao: 'Nordeste' },
  // Centro-Oeste
  { sigla: 'DF', nome: 'Distrito Federal', regiao: 'Centro-Oeste' },
  { sigla: 'GO', nome: 'Goias', regiao: 'Centro-Oeste' },
  { sigla: 'MT', nome: 'Mato Grosso', regiao: 'Centro-Oeste' },
  { sigla: 'MS', nome: 'Mato Grosso do Sul', regiao: 'Centro-Oeste' },
  // Sudeste
  { sigla: 'ES', nome: 'Espirito Santo', regiao: 'Sudeste' },
  { sigla: 'MG', nome: 'Minas Gerais', regiao: 'Sudeste' },
  { sigla: 'RJ', nome: 'Rio de Janeiro', regiao: 'Sudeste' },
  { sigla: 'SP', nome: 'Sao Paulo', regiao: 'Sudeste' },
  // Sul
  { sigla: 'PR', nome: 'Parana', regiao: 'Sul' },
  { sigla: 'RS', nome: 'Rio Grande do Sul', regiao: 'Sul' },
  { sigla: 'SC', nome: 'Santa Catarina', regiao: 'Sul' },
]

export const REGIOES = ['Norte', 'Nordeste', 'Centro-Oeste', 'Sudeste', 'Sul'] as const

export const PAGE_SIZE = 20
```

**Step 2: Create utils.ts with extracted helpers**

```ts
import { Vaga } from './types'

export function formatSalary(vaga: Vaga): string | null {
  if (vaga.salary) return vaga.salary
  if (vaga.salary_min == null && vaga.salary_max == null) return null

  const fmt = (n: number) =>
    n.toLocaleString('pt-BR', {
      style: 'currency',
      currency: 'BRL',
      maximumFractionDigits: 0,
    })

  const period =
    vaga.salary_period === 'HOURLY'
      ? '/h'
      : vaga.salary_period === 'YEARLY'
        ? '/ano'
        : '/mes'

  if (vaga.salary_min != null && vaga.salary_max != null) {
    return `${fmt(vaga.salary_min)} - ${fmt(vaga.salary_max)}${period}`
  }
  if (vaga.salary_min != null)
    return `A partir de ${fmt(vaga.salary_min)}${period}`
  return `Ate ${fmt(vaga.salary_max!)}${period}`
}

export function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime()
  const days = Math.floor(diff / 86400000)
  if (days === 0) return 'Hoje'
  if (days === 1) return 'Ontem'
  if (days < 30) return `${days}d`
  const months = Math.floor(days / 30)
  return `${months}m`
}

export function freshnessLevel(dateStr: string): 'today' | 'yesterday' | 'this-week' | 'older' {
  const diff = Date.now() - new Date(dateStr).getTime()
  const days = Math.floor(diff / 86400000)
  if (days === 0) return 'today'
  if (days === 1) return 'yesterday'
  if (days < 7) return 'this-week'
  return 'older'
}
```

**Step 3: Verify build**

Run: `cd frontend && npm run build`
Expected: Build succeeds (files are created but not yet imported).

**Step 4: Commit**

```
feat(frontend): add UF constants and shared utility functions
```

---

## Task 4: Add new types

**Files:**
- Modify: `frontend/lib/types.ts`

**Step 1: Add SiteStats and SpecialtyCount types**

Append to the end of `types.ts` (after the `Vaga` type):

```ts

export type SiteStats = {
  totalVagas: number
  newToday: number
  newThisWeek: number
  totalCities: number
  totalStates: number
}

export type SpecialtyCount = {
  specialty: string
  count: number
}
```

**Step 2: Verify build**

Run: `cd frontend && npm run build`
Expected: Build succeeds.

**Step 3: Commit**

```
feat(frontend): add SiteStats and SpecialtyCount types
```

---

## Task 5: Add new queries (fetchStats, fetchSpecialtyCounts, state filter)

**Files:**
- Modify: `frontend/lib/queries.ts`

**Step 1: Add `state` parameter to `FetchVagasParams` and the query**

In the `FetchVagasParams` type, add `state?: string`.

In `fetchVagas`, update the destructuring from `const { specialty, city, q, page = 1 } = params` to `const { specialty, city, state, q, page = 1 } = params`.

Then, after each `if (city)` line, add: `if (state) query = query.eq('state', state)` — in both the RPC branch and the regular branch.

**Step 2: Add `fetchStats` function**

Append after `fetchFilterOptions`:

```ts
export async function fetchStats(
  supabase: SupabaseClient,
): Promise<SiteStats> {
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const todayISO = today.toISOString()

  const weekAgo = new Date(today)
  weekAgo.setDate(weekAgo.getDate() - 7)
  const weekAgoISO = weekAgo.toISOString()

  const [totalRes, todayRes, weekRes, citiesRes, statesRes] = await Promise.all([
    supabase.from('vagas_public').select('id', { count: 'exact', head: true }),
    supabase.from('vagas_public').select('id', { count: 'exact', head: true }).gte('effective_date', todayISO),
    supabase.from('vagas_public').select('id', { count: 'exact', head: true }).gte('effective_date', weekAgoISO),
    supabase.from('vagas_public').select('city').not('city', 'is', null).limit(10000),
    supabase.from('vagas_public').select('state').not('state', 'is', null).limit(10000),
  ])

  const totalCities = new Set((citiesRes.data ?? []).map((r) => r.city as string)).size
  const totalStates = new Set((statesRes.data ?? []).map((r) => r.state as string)).size

  return {
    totalVagas: totalRes.count ?? 0,
    newToday: todayRes.count ?? 0,
    newThisWeek: weekRes.count ?? 0,
    totalCities,
    totalStates,
  }
}
```

**Step 3: Add `fetchSpecialtyCounts` function**

```ts
export async function fetchSpecialtyCounts(
  supabase: SupabaseClient,
): Promise<SpecialtyCount[]> {
  const { data } = await supabase
    .from('vagas_public')
    .select('specialty')
    .not('specialty', 'is', null)
    .limit(10000)

  const counts = new Map<string, number>()
  for (const row of data ?? []) {
    const s = row.specialty as string
    counts.set(s, (counts.get(s) ?? 0) + 1)
  }

  return [...counts.entries()]
    .map(([specialty, count]) => ({ specialty, count }))
    .sort((a, b) => b.count - a.count)
    .slice(0, 10)
}
```

**Step 4: Add `state` parameter to `fetchFilterOptions`**

Modify `fetchFilterOptions` to accept an optional `state` param that filters cities:

```ts
export async function fetchFilterOptions(
  supabase: SupabaseClient,
  params?: { state?: string },
) {
  const [specialtiesRes, citiesRes, statesRes] = await Promise.all([
    supabase
      .from('vagas_public')
      .select('specialty')
      .not('specialty', 'is', null)
      .order('specialty')
      .limit(10000),
    (() => {
      let q = supabase
        .from('vagas_public')
        .select('city')
        .not('city', 'is', null)
        .order('city')
        .limit(10000)
      if (params?.state) q = q.eq('state', params.state)
      return q
    })(),
    supabase
      .from('vagas_public')
      .select('state')
      .not('state', 'is', null)
      .order('state')
      .limit(10000),
  ])

  const specialties = [
    ...new Set((specialtiesRes.data ?? []).map((r) => r.specialty as string)),
  ]
  const cities = [
    ...new Set((citiesRes.data ?? []).map((r) => r.city as string)),
  ]
  const states = [
    ...new Set((statesRes.data ?? []).map((r) => r.state as string)),
  ]

  return { specialties, cities, states }
}
```

**Step 5: Add import for new types at top of queries.ts**

Update the import to: `import { Vaga, SiteStats, SpecialtyCount } from './types'`

**Step 6: Verify build**

Run: `cd frontend && npm run build`
Expected: Build succeeds.

**Step 7: Commit**

```
feat(frontend): add fetchStats, fetchSpecialtyCounts, state filter to queries
```

---

## Task 6: Create Hero and StatsBar components

**Files:**
- Create: `frontend/app/_components/Hero.tsx`
- Create: `frontend/app/_components/StatsBar.tsx`

**Step 1: Create StatsBar.tsx (client component with animated counters)**

```tsx
'use client'

import { useEffect, useRef, useState } from 'react'
import { SiteStats } from '@/lib/types'

function AnimatedNumber({ target, duration = 800 }: { target: number; duration?: number }) {
  const [value, setValue] = useState(0)
  const ref = useRef<HTMLSpanElement>(null)
  const hasAnimated = useRef(false)

  useEffect(() => {
    if (!ref.current || hasAnimated.current) return

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting && !hasAnimated.current) {
          hasAnimated.current = true
          const start = performance.now()
          const animate = (now: number) => {
            const elapsed = now - start
            const progress = Math.min(elapsed / duration, 1)
            const eased = 1 - Math.pow(1 - progress, 3)
            setValue(Math.round(eased * target))
            if (progress < 1) requestAnimationFrame(animate)
          }
          requestAnimationFrame(animate)
          observer.disconnect()
        }
      },
      { threshold: 0.1 },
    )

    observer.observe(ref.current)
    return () => observer.disconnect()
  }, [target, duration])

  return <span ref={ref} className="tabular-nums">{value.toLocaleString('pt-BR')}</span>
}

export function StatsBar({ stats }: { stats: SiteStats }) {
  return (
    <div className="mt-8 flex flex-wrap items-center justify-center gap-x-8 gap-y-3">
      <div className="flex items-center gap-2 text-sm text-ink-light">
        <span className="text-2xl font-bold text-primary">
          <AnimatedNumber target={stats.totalVagas} />
        </span>
        <span>vagas</span>
      </div>
      <div className="flex items-center gap-2 text-sm text-ink-light">
        <span className="text-2xl font-bold text-primary">
          <AnimatedNumber target={stats.totalCities} />
        </span>
        <span>cidades</span>
      </div>
      {stats.newToday > 0 && (
        <div className="flex items-center gap-2 text-sm text-ink-light">
          <span className="inline-flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full bg-fresh animate-live-pulse" />
            <span className="text-2xl font-bold text-fresh">
              <AnimatedNumber target={stats.newToday} />
            </span>
          </span>
          <span>novas hoje</span>
        </div>
      )}
    </div>
  )
}
```

**Step 2: Create Hero.tsx (server component)**

```tsx
import { SiteStats } from '@/lib/types'
import { StatsBar } from './StatsBar'

export function Hero({ stats }: { stats: SiteStats }) {
  return (
    <section className="relative overflow-hidden border-b border-cream-dark bg-gradient-to-b from-white to-cream">
      <div className="absolute inset-0 bg-gradient-to-r from-primary/5 via-transparent to-accent/5" />
      <div className="relative mx-auto max-w-5xl px-6 py-16 text-center sm:py-20">
        <h1
          className="animate-fade-slide-up font-[family-name:var(--font-serif)] text-4xl font-bold tracking-tight text-ink sm:text-5xl"
        >
          Todas as vagas medicas do Brasil.
          <br />
          <span className="text-primary">Em um so lugar.</span>
        </h1>
        <p
          className="animate-fade-slide-up mx-auto mt-4 max-w-lg text-ink-muted"
          style={{ animationDelay: '100ms' }}
        >
          Agregamos vagas de Indeed, BNE, Vagas.com e InfoJobs para voce nao precisar procurar em cada site.
        </p>
        <div className="animate-fade-slide-up" style={{ animationDelay: '200ms' }}>
          <StatsBar stats={stats} />
        </div>
      </div>
    </section>
  )
}
```

**Step 3: Verify build**

Run: `cd frontend && npm run build`
Expected: Build succeeds (components created but not yet used in page.tsx).

**Step 4: Commit**

```
feat(frontend): create Hero and StatsBar components
```

---

## Task 7: Create SpecialtyPicks component

**Files:**
- Create: `frontend/app/_components/SpecialtyPicks.tsx`

**Step 1: Create the component**

```tsx
'use client'

import { useRouter, useSearchParams } from 'next/navigation'
import { SpecialtyCount } from '@/lib/types'

export function SpecialtyPicks({ specialtyCounts }: { specialtyCounts: SpecialtyCount[] }) {
  const router = useRouter()
  const searchParams = useSearchParams()
  const activeSpecialty = searchParams.get('specialty')

  if (specialtyCounts.length === 0) return null

  function handleClick(specialty: string) {
    const sp = new URLSearchParams(searchParams.toString())
    if (sp.get('specialty') === specialty) {
      sp.delete('specialty')
    } else {
      sp.set('specialty', specialty)
    }
    sp.delete('page')
    router.push(`?${sp.toString()}`, { scroll: false })
  }

  return (
    <section className="border-b border-cream-dark bg-white/60 py-6">
      <div className="mx-auto max-w-5xl px-6">
        <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-ink-muted">
          Especialidades mais procuradas
        </p>
        <div className="flex flex-wrap gap-2">
          {specialtyCounts.map((sc, i) => {
            const isActive = activeSpecialty === sc.specialty
            return (
              <button
                key={sc.specialty}
                onClick={() => handleClick(sc.specialty)}
                className={`animate-fade-in inline-flex items-center gap-1.5 rounded-full px-3.5 py-1.5 text-sm font-medium transition-all ${
                  isActive
                    ? 'bg-primary text-white shadow-sm'
                    : 'bg-cream-dark/60 text-ink-light hover:bg-primary-light hover:text-primary-dark'
                }`}
                style={{ animationDelay: `${300 + i * 40}ms` }}
              >
                {sc.specialty}
                <span className={`text-xs ${isActive ? 'text-white/70' : 'text-ink-faint'}`}>
                  {sc.count}
                </span>
              </button>
            )
          })}
        </div>
      </div>
    </section>
  )
}
```

**Step 2: Verify build**

Run: `cd frontend && npm run build`
Expected: Build succeeds.

**Step 3: Commit**

```
feat(frontend): create SpecialtyPicks component
```

---

## Task 8: Create small reusable components (FreshnessTag, SourceBadge, EmptyState, LoadingSkeleton)

**Files:**
- Create: `frontend/app/_components/FreshnessTag.tsx`
- Create: `frontend/app/_components/SourceBadge.tsx`
- Create: `frontend/app/_components/EmptyState.tsx`
- Create: `frontend/app/_components/LoadingSkeleton.tsx`

**Step 1: Create FreshnessTag.tsx**

```tsx
import { freshnessLevel, timeAgo } from '@/lib/utils'

const STYLES = {
  today: 'bg-fresh-light text-fresh font-medium',
  yesterday: 'bg-fresh-light/60 text-fresh/80',
  'this-week': 'bg-cream-dark text-ink-muted',
  older: 'text-ink-faint',
} as const

export function FreshnessTag({ date }: { date: string }) {
  const level = freshnessLevel(date)
  const label = timeAgo(date)

  if (level === 'older') {
    return <span className={`text-xs ${STYLES.older}`}>{label}</span>
  }

  return (
    <span className={`inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-xs ${STYLES[level]}`}>
      {level === 'today' && (
        <span className="h-1.5 w-1.5 rounded-full bg-fresh animate-live-pulse" />
      )}
      {label}
    </span>
  )
}
```

**Step 2: Create SourceBadge.tsx**

```tsx
const SOURCE_CONFIG: Record<string, { label: string; color: string; bg: string }> = {
  indeed: { label: 'Indeed', color: 'text-source-indeed', bg: 'bg-source-indeed/8' },
  vagas_com: { label: 'Vagas.com', color: 'text-source-vagas', bg: 'bg-source-vagas/8' },
  bne: { label: 'BNE', color: 'text-source-bne', bg: 'bg-source-bne/8' },
  infojobs: { label: 'InfoJobs', color: 'text-source-infojobs', bg: 'bg-source-infojobs/8' },
}

export function SourceBadge({ source }: { source: string }) {
  const config = SOURCE_CONFIG[source] ?? {
    label: source,
    color: 'text-ink-muted',
    bg: 'bg-ink/5',
  }

  return (
    <span className={`rounded-md px-2 py-0.5 text-[0.72rem] font-medium ${config.bg} ${config.color}`}>
      {config.label}
    </span>
  )
}
```

**Step 3: Create EmptyState.tsx**

```tsx
'use client'

import { useRouter } from 'next/navigation'

export function EmptyState() {
  const router = useRouter()

  return (
    <div className="py-20 text-center">
      <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-accent-light">
        <svg className="h-8 w-8 text-accent" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
        </svg>
      </div>
      <p className="font-[family-name:var(--font-serif)] text-xl text-ink">
        Nenhuma vaga encontrada
      </p>
      <p className="mt-2 text-sm text-ink-muted">
        Tente ajustar os filtros ou termos de busca.
      </p>
      <button
        onClick={() => router.push('/')}
        className="mt-4 rounded-lg bg-primary px-5 py-2 text-sm font-medium text-white transition-colors hover:bg-primary-dark"
      >
        Limpar filtros
      </button>
    </div>
  )
}
```

**Step 4: Create LoadingSkeleton.tsx**

```tsx
export function LoadingSkeleton({ count = 5 }: { count?: number }) {
  return (
    <div className="flex flex-col gap-3">
      {[...Array(count)].map((_, i) => (
        <div
          key={i}
          className="animate-pulse-soft rounded-lg border border-cream-dark/60 bg-white p-5"
          style={{ animationDelay: `${i * 100}ms` }}
        >
          <div className="h-4 w-2/3 rounded bg-cream-dark" />
          <div className="mt-2 h-3 w-1/3 rounded bg-cream-dark/60" />
          <div className="mt-3 flex gap-2">
            <div className="h-5 w-20 rounded-md bg-cream-dark/40" />
            <div className="h-5 w-16 rounded-md bg-cream-dark/40" />
          </div>
        </div>
      ))}
    </div>
  )
}
```

**Step 5: Verify build**

Run: `cd frontend && npm run build`
Expected: Build succeeds.

**Step 6: Commit**

```
feat(frontend): create FreshnessTag, SourceBadge, EmptyState, LoadingSkeleton
```

---

## Task 9: Create StateCombobox and FilterBar components

**Files:**
- Create: `frontend/app/_components/StateCombobox.tsx`
- Create: `frontend/app/_components/FilterBar.tsx`

**Step 1: Create StateCombobox.tsx**

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
import { UFS, REGIOES } from '@/lib/constants'

type Props = {
  value: string | null
  onChange: (value: string | null) => void
  availableStates?: string[]
}

export function StateCombobox({ value, onChange, availableStates }: Props) {
  const [query, setQuery] = useState('')

  const filteredUFs = UFS.filter((uf) => {
    if (availableStates && !availableStates.includes(uf.sigla)) return false
    if (!query) return true
    const q = query.toLowerCase()
    return uf.sigla.toLowerCase().includes(q) || uf.nome.toLowerCase().includes(q)
  })

  const grouped = REGIOES.map((regiao) => ({
    regiao,
    ufs: filteredUFs.filter((uf) => uf.regiao === regiao),
  })).filter((g) => g.ufs.length > 0)

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
        <label className="mb-1.5 block text-[0.72rem] font-semibold uppercase tracking-wider text-ink-muted">
          Estado
        </label>
        <div className="relative">
          <ComboboxInput
            className="w-full rounded-lg border border-cream-dark bg-white py-2.5 pl-3.5 pr-16 text-sm text-ink shadow-[0_1px_2px_rgba(0,0,0,0.04)] transition-all focus:border-primary/40 focus:outline-none focus:ring-2 focus:ring-primary/10"
            displayValue={(v: string | null) => {
              if (!v) return ''
              const uf = UFS.find((u) => u.sigla === v)
              return uf ? `${uf.nome} (${uf.sigla})` : v
            }}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Todos"
          />
          {value && (
            <button
              type="button"
              className="absolute inset-y-0 right-8 flex items-center px-1.5 text-ink-muted/50 transition-colors hover:text-ink-muted"
              onClick={(e) => {
                e.stopPropagation()
                onChange(null)
                setQuery('')
              }}
            >
              <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          )}
          <ComboboxButton className="absolute inset-y-0 right-0 flex items-center px-3 text-ink-muted/40">
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 15L12 18.75 15.75 15m-7.5-6L12 5.25 15.75 9" />
            </svg>
          </ComboboxButton>
        </div>
        <ComboboxOptions className="absolute z-20 mt-1.5 max-h-60 w-full overflow-auto rounded-lg border border-cream-dark bg-white py-1 text-sm shadow-lg shadow-ink/5">
          {grouped.length === 0 ? (
            <div className="px-3.5 py-2.5 text-ink-muted">Nenhum resultado</div>
          ) : (
            grouped.map((group) => (
              <div key={group.regiao}>
                <div className="px-3.5 py-1.5 text-[0.68rem] font-semibold uppercase tracking-wider text-ink-faint">
                  {group.regiao}
                </div>
                {group.ufs.map((uf) => (
                  <ComboboxOption
                    key={uf.sigla}
                    value={uf.sigla}
                    className="cursor-pointer select-none px-3.5 py-2 text-ink-light transition-colors data-[focus]:bg-primary-light data-[focus]:text-primary-dark data-[selected]:font-medium"
                  >
                    {uf.nome}
                    <span className="ml-1.5 text-ink-faint">({uf.sigla})</span>
                  </ComboboxOption>
                ))}
              </div>
            ))
          )}
        </ComboboxOptions>
      </div>
    </HeadlessCombobox>
  )
}
```

**Step 2: Create FilterBar.tsx**

```tsx
'use client'

import { useEffect, useRef, useState } from 'react'
import { Combobox } from './Combobox'
import { StateCombobox } from './StateCombobox'

type Props = {
  specialties: string[]
  cities: string[]
  states: string[]
  specialty: string | null
  city: string | null
  state: string | null
  q: string
  onSpecialtyChange: (v: string | null) => void
  onCityChange: (v: string | null) => void
  onStateChange: (v: string | null) => void
  onSearchChange: (v: string) => void
}

export function FilterBar({
  specialties,
  cities,
  states,
  specialty,
  city,
  state,
  q,
  onSpecialtyChange,
  onCityChange,
  onStateChange,
  onSearchChange,
}: Props) {
  const ref = useRef<HTMLDivElement>(null)
  const [stuck, setStuck] = useState(false)
  const debounceRef = useRef<ReturnType<typeof setTimeout>>(undefined)

  useEffect(() => {
    const el = ref.current
    if (!el) return

    const observer = new IntersectionObserver(
      ([entry]) => setStuck(!entry.isIntersecting),
      { threshold: 0, rootMargin: '-1px 0px 0px 0px' },
    )

    const sentinel = document.createElement('div')
    sentinel.style.height = '1px'
    el.parentElement?.insertBefore(sentinel, el)
    observer.observe(sentinel)

    return () => {
      observer.disconnect()
      sentinel.remove()
    }
  }, [])

  function handleSearch(value: string) {
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => onSearchChange(value), 300)
  }

  return (
    <div
      ref={ref}
      data-stuck={stuck}
      className="filter-bar-sticky sticky top-0 z-10 -mx-6 px-6 py-4"
    >
      <div className="rounded-xl border border-cream-dark/80 bg-white p-5 shadow-[0_1px_3px_rgba(0,0,0,0.03)]">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-end">
          <div className="w-full sm:w-44">
            <Combobox
              label="Especialidade"
              options={specialties}
              value={specialty}
              onChange={onSpecialtyChange}
              placeholder="Todas"
            />
          </div>
          <div className="w-full sm:w-40">
            <StateCombobox
              value={state}
              onChange={onStateChange}
              availableStates={states}
            />
          </div>
          <div className="w-full sm:w-44">
            <Combobox
              label="Cidade"
              options={cities}
              value={city}
              onChange={onCityChange}
              placeholder="Todas"
            />
          </div>
          <div className="w-full sm:flex-1">
            <label className="mb-1.5 block text-[0.72rem] font-semibold uppercase tracking-wider text-ink-muted">
              Buscar
            </label>
            <input
              type="text"
              defaultValue={q}
              onChange={(e) => handleSearch(e.target.value)}
              placeholder="Buscar no titulo..."
              className="w-full rounded-lg border border-cream-dark bg-white py-2.5 pl-3.5 pr-4 text-sm text-ink shadow-[0_1px_2px_rgba(0,0,0,0.04)] transition-all focus:border-primary/40 focus:outline-none focus:ring-2 focus:ring-primary/10"
            />
          </div>
        </div>
      </div>
    </div>
  )
}
```

**Step 3: Verify build**

Run: `cd frontend && npm run build`
Expected: Build succeeds.

**Step 4: Commit**

```
feat(frontend): create StateCombobox and FilterBar components
```

---

## Task 10: Redesign VagaCard

**Files:**
- Modify: `frontend/app/_components/VagaCard.tsx`

**Step 1: Replace VagaCard.tsx entirely**

```tsx
'use client'

import { useState } from 'react'
import { Vaga } from '@/lib/types'
import { formatSalary } from '@/lib/utils'
import { FreshnessTag } from './FreshnessTag'
import { SourceBadge } from './SourceBadge'

const SOURCE_BORDER: Record<string, string> = {
  indeed: 'border-l-source-indeed',
  vagas_com: 'border-l-source-vagas',
  bne: 'border-l-source-bne',
  infojobs: 'border-l-source-infojobs',
}

export function VagaCard({ vaga, index }: { vaga: Vaga; index: number }) {
  const [expanded, setExpanded] = useState(false)
  const salary = formatSalary(vaga)
  const borderColor = SOURCE_BORDER[vaga.source] ?? 'border-l-ink-muted'

  return (
    <article
      className={`animate-slide-up group rounded-lg border border-cream-dark/80 border-l-[3px] ${borderColor} bg-white shadow-[0_1px_3px_rgba(0,0,0,0.04)] transition-all duration-200 hover:-translate-y-px hover:shadow-[0_4px_12px_rgba(0,0,0,0.06)]`}
      style={{ animationDelay: `${index * 40}ms` }}
    >
      <div
        className="cursor-pointer px-5 py-4"
        onClick={() => setExpanded(!expanded)}
      >
        {/* Top row */}
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 flex-1">
            <h2 className="font-[family-name:var(--font-serif)] text-[1.1rem] font-semibold leading-snug text-ink">
              {vaga.title}
            </h2>
            <p className="mt-0.5 text-[0.8rem] text-ink-muted">
              {vaga.company ?? 'Confidencial'}
            </p>
          </div>

          <div className="flex shrink-0 items-center gap-2">
            <FreshnessTag date={vaga.effective_date} />
            <svg
              className={`h-4 w-4 text-ink-muted/40 transition-transform duration-200 ${expanded ? 'rotate-180' : ''}`}
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
            </svg>
          </div>
        </div>

        {/* Meta row */}
        <div className="mt-2.5 flex flex-wrap items-center gap-2 text-[0.78rem]">
          {(vaga.city || vaga.state) && (
            <span className="flex items-center gap-1 text-ink-light">
              <svg className="h-3.5 w-3.5 text-ink-muted/60" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M15 10.5a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z" />
                <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 10.5c0 7.142-7.5 11.25-7.5 11.25S4.5 17.642 4.5 10.5a7.5 7.5 0 1 1 15 0Z" />
              </svg>
              {[vaga.city, vaga.state].filter(Boolean).join(', ')}
            </span>
          )}

          {salary && (
            <span className="rounded-md bg-salary-light px-2 py-0.5 font-medium text-salary">
              {salary}
            </span>
          )}

          {vaga.specialty && (
            <span className="rounded-md bg-primary-light px-2 py-0.5 font-medium text-primary">
              {vaga.specialty}
            </span>
          )}

          <SourceBadge source={vaga.source} />
        </div>
      </div>

      {/* Expandable content with CSS Grid transition */}
      <div
        className="card-expand-grid"
        data-expanded={expanded}
      >
        <div>
          <div className="border-t border-cream-dark/60 px-5 py-4">
            {vaga.description && (
              <p className="text-[0.82rem] leading-relaxed text-ink-light whitespace-pre-line">
                {vaga.description.length > 500
                  ? vaga.description.slice(0, 500) + '...'
                  : vaga.description}
              </p>
            )}

            {vaga.benefits && vaga.benefits.length > 0 && (
              <div className="mt-3 flex flex-wrap gap-1.5">
                {vaga.benefits.map((b) => (
                  <span
                    key={b}
                    className="rounded-full bg-accent-light px-2.5 py-0.5 text-[0.72rem] font-medium text-accent"
                  >
                    {b}
                  </span>
                ))}
              </div>
            )}

            <div className="mt-4 flex items-center justify-end">
              <a
                href={vaga.url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-4 py-2 text-[0.8rem] font-medium text-white transition-colors hover:bg-primary-dark"
                onClick={(e) => e.stopPropagation()}
              >
                Ver vaga
                <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 6H5.25A2.25 2.25 0 0 0 3 8.25v10.5A2.25 2.25 0 0 0 5.25 21h10.5A2.25 2.25 0 0 0 18 18.75V10.5m-10.5 6L21 3m0 0h-5.25M21 3v5.25" />
                </svg>
              </a>
            </div>
          </div>
        </div>
      </div>
    </article>
  )
}
```

**Step 2: Verify build**

Run: `cd frontend && npm run build`
Expected: Build succeeds.

**Step 3: Commit**

```
feat(frontend): redesign VagaCard with FreshnessTag, SourceBadge, CSS Grid expand
```

---

## Task 11: Redesign Pagination with numbered buttons

**Files:**
- Modify: `frontend/app/_components/Pagination.tsx`

**Step 1: Replace Pagination.tsx entirely**

```tsx
'use client'

type Props = {
  page: number
  totalPages: number
  onPageChange: (page: number) => void
}

function getVisiblePages(current: number, total: number): (number | 'ellipsis')[] {
  if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1)

  const pages: (number | 'ellipsis')[] = []

  if (current <= 4) {
    pages.push(1, 2, 3, 4, 5, 'ellipsis', total)
  } else if (current >= total - 3) {
    pages.push(1, 'ellipsis', total - 4, total - 3, total - 2, total - 1, total)
  } else {
    pages.push(1, 'ellipsis', current - 1, current, current + 1, 'ellipsis', total)
  }

  return pages
}

export function Pagination({ page, totalPages, onPageChange }: Props) {
  if (totalPages <= 1) return null

  const visible = getVisiblePages(page, totalPages)

  return (
    <div className="mt-8 flex items-center justify-center gap-1.5">
      <button
        onClick={() => onPageChange(page - 1)}
        disabled={page <= 1}
        className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-cream-dark bg-white text-ink-light shadow-[0_1px_2px_rgba(0,0,0,0.04)] transition-all hover:border-primary/30 hover:text-primary disabled:cursor-not-allowed disabled:opacity-40"
        aria-label="Pagina anterior"
      >
        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" />
        </svg>
      </button>

      {visible.map((item, i) =>
        item === 'ellipsis' ? (
          <span key={`e-${i}`} className="flex h-9 w-9 items-center justify-center text-sm text-ink-faint">
            ...
          </span>
        ) : (
          <button
            key={item}
            onClick={() => onPageChange(item)}
            className={`inline-flex h-9 w-9 items-center justify-center rounded-lg text-sm font-medium tabular-nums transition-all ${
              item === page
                ? 'bg-primary text-white shadow-sm'
                : 'border border-cream-dark bg-white text-ink-light shadow-[0_1px_2px_rgba(0,0,0,0.04)] hover:border-primary/30 hover:text-primary'
            }`}
          >
            {item}
          </button>
        ),
      )}

      <button
        onClick={() => onPageChange(page + 1)}
        disabled={page >= totalPages}
        className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-cream-dark bg-white text-ink-light shadow-[0_1px_2px_rgba(0,0,0,0.04)] transition-all hover:border-primary/30 hover:text-primary disabled:cursor-not-allowed disabled:opacity-40"
        aria-label="Proxima pagina"
      >
        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
        </svg>
      </button>
    </div>
  )
}
```

**Step 2: Verify build**

Run: `cd frontend && npm run build`
Expected: Build succeeds.

**Step 3: Commit**

```
feat(frontend): redesign Pagination with numbered buttons and ellipsis
```

---

## Task 12: Refactor VagaList to use FilterBar and support state filter

**Files:**
- Modify: `frontend/app/_components/VagaList.tsx`

**Step 1: Replace VagaList.tsx entirely**

```tsx
'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { createClient } from '@/lib/supabase/client'
import { fetchVagas, fetchFilterOptions } from '@/lib/queries'
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
  newToday: number
}

export function VagaList({
  initialVagas,
  initialCount,
  specialties: initialSpecialties,
  cities: initialCities,
  states: initialStates,
  newToday,
}: Props) {
  const router = useRouter()
  const searchParams = useSearchParams()

  const specialty = searchParams.get('specialty') ?? null
  const city = searchParams.get('city') ?? null
  const state = searchParams.get('state') ?? null
  const q = searchParams.get('q') ?? ''
  const page = Number(searchParams.get('page') ?? '1')

  const [vagas, setVagas] = useState(initialVagas)
  const [count, setCount] = useState(initialCount)
  const [loading, setLoading] = useState(false)
  const [cities, setCities] = useState(initialCities)

  const isInitialMount = useRef(true)
  const totalPages = Math.ceil(count / PAGE_SIZE)
  const hasFilters = specialty || city || state || q

  const updateURL = useCallback(
    (params: Record<string, string | null>) => {
      const sp = new URLSearchParams(searchParams.toString())
      Object.entries(params).forEach(([k, v]) => {
        if (v) sp.set(k, v)
        else sp.delete(k)
      })
      if (!('page' in params)) sp.delete('page')
      router.push(`?${sp.toString()}`, { scroll: false })
    },
    [router, searchParams],
  )

  // Fetch vagas when filters change
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
      state: state ?? undefined,
      q: q || undefined,
      page,
    })
      .then(({ vagas, count }) => {
        setVagas(vagas)
        setCount(count)
      })
      .finally(() => setLoading(false))
  }, [specialty, city, state, q, page])

  // Cascade cities when state changes
  useEffect(() => {
    if (state) {
      const supabase = createClient()
      fetchFilterOptions(supabase, { state }).then(({ cities }) => {
        setCities(cities)
      })
    } else {
      setCities(initialCities)
    }
  }, [state, initialCities])

  function handleStateChange(v: string | null) {
    updateURL({ state: v, city: null })
  }

  return (
    <div className="mx-auto max-w-5xl px-6">
      <FilterBar
        specialties={initialSpecialties}
        cities={cities}
        states={initialStates}
        specialty={specialty}
        city={city}
        state={state}
        q={q}
        onSpecialtyChange={(v) => updateURL({ specialty: v })}
        onCityChange={(v) => updateURL({ city: v })}
        onStateChange={handleStateChange}
        onSearchChange={(v) => updateURL({ q: v || null })}
      />

      {/* Results header */}
      <div className="mt-6 mb-4 flex items-baseline justify-between">
        <p className="text-[0.82rem] text-ink-muted">
          <span className="font-semibold tabular-nums text-ink">{count.toLocaleString('pt-BR')}</span>{' '}
          {count === 1 ? 'vaga encontrada' : 'vagas encontradas'}
          {newToday > 0 && !hasFilters && (
            <span className="ml-2 text-fresh">
              — {newToday} {newToday === 1 ? 'nova' : 'novas'} hoje
            </span>
          )}
          {hasFilters && (
            <button
              onClick={() => router.push('/')}
              className="ml-2 text-primary hover:text-primary-dark"
            >
              Limpar filtros
            </button>
          )}
        </p>
      </div>

      {/* Loading */}
      {loading && <LoadingSkeleton />}

      {/* Vaga list */}
      {!loading && (
        <div className="flex flex-col gap-3">
          {vagas.length === 0 ? (
            <EmptyState />
          ) : (
            vagas.map((vaga, i) => (
              <VagaCard key={vaga.id} vaga={vaga} index={i} />
            ))
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

**Step 2: Update page.tsx to pass new props (must be done together to avoid build breakage)**

**File:** `frontend/app/page.tsx`

```tsx
import { createClient } from '@/lib/supabase/server'
import { fetchVagas, fetchFilterOptions, fetchStats, fetchSpecialtyCounts } from '@/lib/queries'
import { Hero } from './_components/Hero'
import { SpecialtyPicks } from './_components/SpecialtyPicks'
import { VagaList } from './_components/VagaList'

type Props = {
  searchParams: Promise<Record<string, string | undefined>>
}

export default async function Page({ searchParams }: Props) {
  const params = await searchParams
  const supabase = await createClient()

  const [{ vagas, count }, { specialties, cities, states }, stats, specialtyCounts] =
    await Promise.all([
      fetchVagas(supabase, {
        specialty: params.specialty,
        city: params.city,
        state: params.state,
        q: params.q,
        page: params.page ? Number(params.page) : undefined,
      }),
      fetchFilterOptions(supabase),
      fetchStats(supabase),
      fetchSpecialtyCounts(supabase),
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
        newToday={stats.newToday}
      />
    </>
  )
}
```

**Step 3: Verify build**

Run: `cd frontend && npm run build`
Expected: Build succeeds with no errors.

**Step 4: Commit**

```
feat(frontend): refactor VagaList + integrate Hero, SpecialtyPicks, new data in page.tsx
```

---

## Task 13: Update Combobox styles for new color tokens

**Files:**
- Modify: `frontend/app/_components/Combobox.tsx`

**Step 1: Replace `teal` with `primary` in class names**

In `Combobox.tsx`, do a find-and-replace:
- `focus:border-teal/40` → `focus:border-primary/40`
- `focus:ring-teal/10` → `focus:ring-primary/10`
- `data-[focus]:bg-teal-light` → `data-[focus]:bg-primary-light`
- `data-[focus]:text-teal-dark` → `data-[focus]:text-primary-dark`

These are 4 occurrences total. No other changes needed.

**Step 2: Verify build**

Run: `cd frontend && npm run build`
Expected: Build succeeds.

**Step 3: Commit**

```
style(frontend): update Combobox color tokens from teal to primary
```

---

## Task 14: Final build verification and polish

**Step 1: Full build**

Run: `cd frontend && npm run build`
Expected: Build succeeds with zero errors.

**Step 2: Run lint**

Run: `cd frontend && npm run lint`
Expected: No errors (warnings OK).

**Step 3: Commit any remaining fixes**

If lint/build finds issues, fix them and commit:

```
fix(frontend): address lint/build issues from redesign
```

---

## Summary of all files

### Created (11)
1. `frontend/lib/constants.ts` — UF data, regions, PAGE_SIZE
2. `frontend/lib/utils.ts` — formatSalary, timeAgo, freshnessLevel
3. `frontend/app/_components/Hero.tsx` — Hero section with value prop
4. `frontend/app/_components/StatsBar.tsx` — Animated stat counters
5. `frontend/app/_components/SpecialtyPicks.tsx` — Clickable specialty chips
6. `frontend/app/_components/FilterBar.tsx` — Sticky filter bar
7. `frontend/app/_components/StateCombobox.tsx` — UF combobox grouped by region
8. `frontend/app/_components/FreshnessTag.tsx` — Color-coded freshness
9. `frontend/app/_components/SourceBadge.tsx` — Source badge extracted
10. `frontend/app/_components/EmptyState.tsx` — Warm empty state
11. `frontend/app/_components/LoadingSkeleton.tsx` — Skeleton loading cards

### Modified (9)
1. `frontend/app/globals.css` — New warm palette + animations
2. `frontend/app/layout.tsx` — Fraunces + Source Sans 3, new footer
3. `frontend/lib/types.ts` — SiteStats, SpecialtyCount types
4. `frontend/lib/queries.ts` — fetchStats, fetchSpecialtyCounts, state filter
5. `frontend/app/page.tsx` — Hero, SpecialtyPicks, new data fetching
6. `frontend/app/_components/VagaList.tsx` — FilterBar delegation, state support
7. `frontend/app/_components/VagaCard.tsx` — Redesigned with FreshnessTag, SourceBadge, CSS Grid expand
8. `frontend/app/_components/Pagination.tsx` — Numbered buttons with ellipsis
9. `frontend/app/_components/Combobox.tsx` — Color token updates (teal→primary)
