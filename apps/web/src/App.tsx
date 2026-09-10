import { useCallback, useEffect, useState } from 'react'
import {
  Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import DimensionsPage from './DimensionsPage'
import './App.css'

type Tab = 'dashboard' | 'dimensions'

type Filters = {
  sellers: string[]
  primary_jobs: string[]
  handoff_topologies: string[]
  trust_surfaces: string[]
  buying_triggers: string[]
}

type Meeting = {
  id: number
  nombre: string
  seller: string
  meeting_date: string
  closed: number
  primary_job: string | null
  handoff_topology: string | null
  trust_surface: string | null
  buying_trigger: string | null
  model: string | null
  prompt_version: string | null
}

type WinRate = { wins: number; total: number; win_rate: number }
type WinRateJob = WinRate & { job: string }
type WinRateHandoff = WinRate & { handoff: string }
type WinRateTrigger = WinRate & { trigger: string }
type GravityMix = { gravity: string; count: number; share: number }

const API = import.meta.env.DEV ? '/api' : ''

const CHART_COLORS = {
  job: 'var(--color-chart-1)',
  handoff: 'var(--color-chart-2)',
  trigger: 'var(--color-chart-3)',
  gravity: 'var(--color-chart-4)',
} as const

const CHARTS = [
  { title: 'Win rate by primary job', dataKey: 'byJob' as const, xKey: 'job' as const, color: CHART_COLORS.job, icon: 'chart__icon--blue', glyph: '▮' },
  { title: 'Win rate by handoff topology', dataKey: 'byHandoff' as const, xKey: 'handoff' as const, color: CHART_COLORS.handoff, icon: 'chart__icon--sky', glyph: '⇄' },
  { title: 'Win rate by buying trigger', dataKey: 'byTrigger' as const, xKey: 'trigger' as const, color: CHART_COLORS.trigger, icon: 'chart__icon--orange', glyph: '⚡' },
  { title: 'System gravity mix', dataKey: 'gravityMix' as const, xKey: 'gravity' as const, color: CHART_COLORS.gravity, icon: 'chart__icon--purple', glyph: '◎' },
] as const

function Chart({ title, data, xKey, fill, iconClass, glyph }: {
  title: string
  data: Record<string, unknown>[]
  xKey: string
  fill: string
  iconClass: string
  glyph: string
}) {
  const isGravity = xKey === 'gravity'

  return (
    <div className="chart">
      <div className="chart__header">
        <span className={`chart__icon ${iconClass}`} aria-hidden>{glyph}</span>
        <h2>{title}</h2>
      </div>
      <ResponsiveContainer width="100%" height={240}>
        <BarChart data={data} margin={{ bottom: 50 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
          <XAxis
            dataKey={xKey}
            angle={-30}
            textAnchor="end"
            interval={0}
            tick={{ fontSize: 10, fill: 'var(--color-text-muted)' }}
            axisLine={{ stroke: 'var(--color-border)' }}
            tickLine={{ stroke: 'var(--color-border)' }}
          />
          <YAxis
            unit={isGravity ? '' : '%'}
            domain={isGravity ? undefined : [0, 100]}
            tick={{ fontSize: 11, fill: 'var(--color-text-muted)' }}
            axisLine={{ stroke: 'var(--color-border)' }}
            tickLine={{ stroke: 'var(--color-border)' }}
          />
          <Tooltip
            formatter={(v) => [isGravity ? v : `${v ?? 0}%`, isGravity ? 'Count' : 'Win rate']}
            contentStyle={{
              borderRadius: 'var(--radius-lg)',
              border: '1px solid var(--color-border)',
              background: 'var(--color-surface)',
              fontFamily: 'var(--font-sans)',
              fontSize: '0.8125rem',
              boxShadow: 'var(--shadow-md)',
            }}
            labelStyle={{ fontWeight: 600, color: 'var(--color-text)' }}
          />
          <Bar
            dataKey={isGravity ? 'count' : 'win_rate'}
            fill={fill}
            radius={[6, 6, 0, 0]}
          />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

export default function App() {
  const [filters, setFilters] = useState<Filters | null>(null)
  const [meetings, setMeetings] = useState<Meeting[]>([])
  const [total, setTotal] = useState(0)
  const [byJob, setByJob] = useState<WinRateJob[]>([])
  const [byHandoff, setByHandoff] = useState<WinRateHandoff[]>([])
  const [byTrigger, setByTrigger] = useState<WinRateTrigger[]>([])
  const [gravityMix, setGravityMix] = useState<GravityMix[]>([])
  const [loading, setLoading] = useState(true)
  const [seller, setSeller] = useState('')
  const [closed, setClosed] = useState('')
  const [primaryJob, setPrimaryJob] = useState('')
  const [handoff, setHandoff] = useState('')
  const [trust, setTrust] = useState('')
  const [trigger, setTrigger] = useState('')
  const [q, setQ] = useState('')
  const [tab, setTab] = useState<Tab>('dashboard')

  const params = useCallback(() => {
    const p = new URLSearchParams()
    if (seller) p.set('seller', seller)
    if (closed !== '') p.set('closed', closed)
    if (primaryJob) p.set('primary_job', primaryJob)
    if (handoff) p.set('handoff_topology', handoff)
    if (trust) p.set('trust_surface', trust)
    if (trigger) p.set('buying_trigger', trigger)
    if (q) p.set('q', q)
    return p
  }, [seller, closed, primaryJob, handoff, trust, trigger, q])

  useEffect(() => {
    Promise.all([
      fetch(`${API}/filters`).then((r) => r.json()).then(setFilters),
      fetch(`${API}/metrics/win-rate-by-job`).then((r) => r.json()).then(setByJob),
      fetch(`${API}/metrics/win-rate-by-handoff`).then((r) => r.json()).then(setByHandoff),
      fetch(`${API}/metrics/win-rate-by-trigger`).then((r) => r.json()).then(setByTrigger),
      fetch(`${API}/metrics/system-gravity-mix`).then((r) => r.json()).then(setGravityMix),
    ]).finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    fetch(`${API}/meetings?${params()}`)
      .then((r) => r.json())
      .then((d) => { setMeetings(d.items); setTotal(d.total) })
  }, [params])

  const labeled = meetings.filter((m) => m.prompt_version).length
  const chartData = { byJob, byHandoff, byTrigger, gravityMix }

  if (loading) {
    return (
      <div className="app">
        <div className="loading">
          <span className="loading__spinner" aria-hidden />
          Loading dashboard…
        </div>
      </div>
    )
  }

  return (
    <div className="app">
      <header className="app-header">
        <div className="app-header__brand">
          <div className="app-header__logo" aria-hidden>V</div>
          <div>
            <h1 className="app-header__title">Vambe Dashboard</h1>
            <p className="app-header__subtitle">Sales meeting insights &amp; win-rate analytics</p>
          </div>
        </div>
        <div className="app-header__stats">
          <span className="stat-pill">{total.toLocaleString()} meetings</span>
          <span className="stat-pill stat-pill--neutral">{labeled} labeled in view</span>
        </div>
      </header>

      <nav className="tabs" aria-label="Main navigation">
        <button
          type="button"
          className={`tabs__btn${tab === 'dashboard' ? ' tabs__btn--active' : ''}`}
          aria-current={tab === 'dashboard' ? 'page' : undefined}
          onClick={() => setTab('dashboard')}
        >
          Dashboard
        </button>
        <button
          type="button"
          className={`tabs__btn${tab === 'dimensions' ? ' tabs__btn--active' : ''}`}
          aria-current={tab === 'dimensions' ? 'page' : undefined}
          onClick={() => setTab('dimensions')}
        >
          Dimensions
        </button>
      </nav>

      {tab === 'dimensions' ? (
        <DimensionsPage />
      ) : (
        <>
      <section className="filters" aria-label="Filters">
        <select value={seller} onChange={(e) => setSeller(e.target.value)} aria-label="Filter by seller">
          <option value="">All sellers</option>
          {filters?.sellers.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
        <select value={closed} onChange={(e) => setClosed(e.target.value)} aria-label="Filter by outcome">
          <option value="">All outcomes</option>
          <option value="1">Closed won</option>
          <option value="0">Open</option>
        </select>
        <select value={primaryJob} onChange={(e) => setPrimaryJob(e.target.value)} aria-label="Filter by primary job">
          <option value="">All jobs</option>
          {filters?.primary_jobs.map((j) => <option key={j} value={j}>{j}</option>)}
        </select>
        <select value={handoff} onChange={(e) => setHandoff(e.target.value)} aria-label="Filter by handoff">
          <option value="">All handoff</option>
          {filters?.handoff_topologies.map((h) => <option key={h} value={h}>{h}</option>)}
        </select>
        <select value={trust} onChange={(e) => setTrust(e.target.value)} aria-label="Filter by trust surface">
          <option value="">All trust</option>
          {filters?.trust_surfaces.map((t) => <option key={t} value={t}>{t}</option>)}
        </select>
        <select value={trigger} onChange={(e) => setTrigger(e.target.value)} aria-label="Filter by buying trigger">
          <option value="">All triggers</option>
          {filters?.buying_triggers.map((t) => <option key={t} value={t}>{t}</option>)}
        </select>
        <input
          placeholder="Search name or transcript…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          aria-label="Search meetings"
        />
      </section>

      <p className="section-heading">Performance metrics</p>
      <section className="charts">
        {CHARTS.map((c) => (
          <Chart
            key={c.xKey}
            title={c.title}
            data={chartData[c.dataKey] as Record<string, unknown>[]}
            xKey={c.xKey}
            fill={c.color}
            iconClass={c.icon}
            glyph={c.glyph}
          />
        ))}
      </section>

      <section className="table-section">
        <div className="table-section__header">
          <h2 className="table-section__title">Meetings</h2>
          <span className="table-section__count">{meetings.length} shown</span>
        </div>
        <div className="table-wrap">
          {meetings.length === 0 ? (
            <div className="empty-state">
              <div className="empty-state__icon" aria-hidden>∅</div>
              <p>No meetings match your filters.</p>
            </div>
          ) : (
            <table>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Seller</th>
                  <th>Date</th>
                  <th>Closed</th>
                  <th>Primary job</th>
                  <th>Handoff</th>
                  <th>Model</th>
                </tr>
              </thead>
              <tbody>
                {meetings.map((m) => (
                  <tr key={m.id}>
                    <td>{m.nombre}</td>
                    <td>{m.seller}</td>
                    <td>{m.meeting_date}</td>
                    <td>
                      <span className={`badge ${m.closed ? 'badge--won' : 'badge--open'}`}>
                        {m.closed ? 'Won' : 'Open'}
                      </span>
                    </td>
                    <td>{m.primary_job ?? '—'}</td>
                    <td>{m.handoff_topology ?? '—'}</td>
                    <td title={m.model ?? undefined}>{m.prompt_version ?? '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </section>
        </>
      )}
    </div>
  )
}
