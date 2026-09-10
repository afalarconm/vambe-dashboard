import { Fragment, useCallback, useEffect, useState, type ReactNode } from 'react'
import {
  Bar, BarChart, CartesianGrid, Cell, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis,
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
  system_gravities: string[]
  volume_bands: string[]
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
type WinRateVolumeBand = WinRate & { volume_band: string }
type GravityMix = { gravity: string; count: number; share: number }
type HeatmapCell = WinRate & { job: string; handoff: string }
type JobHandoffHeatmap = {
  jobs: string[]
  handoffs: string[]
  cells: HeatmapCell[]
  min_sample: number
}

type Health = { ok: boolean; llm_labels: number; total_meetings: number }

const API = import.meta.env.DEV ? '/api' : ''

const CHART_COLORS = {
  job: 'var(--color-chart-1)',
  handoff: 'var(--color-chart-2)',
  trigger: 'var(--color-chart-3)',
  gravity: 'var(--color-chart-4)',
  volume: 'var(--color-chart-5)',
} as const

function shortModelName(model: string): string {
  const slash = model.lastIndexOf('/')
  return slash >= 0 ? model.slice(slash + 1) : model
}

type Metrics = {
  by_job: WinRateJob[]
  by_handoff: WinRateHandoff[]
  by_trigger: WinRateTrigger[]
  by_volume_band: WinRateVolumeBand[]
  gravity_mix: GravityMix[]
  job_handoff_heatmap: JobHandoffHeatmap
}

const BAR_CHARTS = [
  { title: 'Win rate by primary job', dataKey: 'by_job' as const, xKey: 'job' as const, color: CHART_COLORS.job, icon: 'chart__icon--blue', glyph: 'bars' as const },
  { title: 'Win rate by handoff topology', dataKey: 'by_handoff' as const, xKey: 'handoff' as const, color: CHART_COLORS.handoff, icon: 'chart__icon--sky', glyph: 'handoff' as const },
  { title: 'Win rate by buying trigger', dataKey: 'by_trigger' as const, xKey: 'trigger' as const, color: CHART_COLORS.trigger, icon: 'chart__icon--orange', glyph: 'trigger' as const },
  { title: 'System gravity mix', dataKey: 'gravity_mix' as const, xKey: 'gravity' as const, color: CHART_COLORS.gravity, icon: 'chart__icon--purple', glyph: 'gravity' as const },
  { title: 'Win rate by volume band', dataKey: 'by_volume_band' as const, xKey: 'volume_band' as const, color: CHART_COLORS.volume, icon: 'chart__icon--teal', glyph: 'volume' as const },
] as const

type Glyph = 'bars' | 'handoff' | 'trigger' | 'gravity' | 'volume' | 'grid'

function ChartGlyph({ name }: { name: Glyph }) {
  return (
    <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      {name === 'bars' && (
        <>
          <path d="M6 20V10" />
          <path d="M12 20V4" />
          <path d="M18 20v-6" />
        </>
      )}
      {name === 'handoff' && (
        <>
          <path d="M8 8H4v4" />
          <path d="M4 8l6 6" />
          <path d="M16 16h4v-4" />
          <path d="M20 16l-6-6" />
        </>
      )}
      {name === 'trigger' && <path d="M13 3L4 14h7l-1 7 9-11h-7l1-7z" />}
      {name === 'gravity' && (
        <>
          <circle cx="12" cy="12" r="3" />
          <circle cx="12" cy="12" r="8" />
        </>
      )}
      {name === 'volume' && (
        <>
          <rect x="4" y="4" width="7" height="7" rx="1" />
          <rect x="13" y="4" width="7" height="7" rx="1" />
          <rect x="4" y="13" width="7" height="7" rx="1" />
          <rect x="13" y="13" width="7" height="7" rx="1" />
        </>
      )}
      {name === 'grid' && (
        <>
          <rect x="3" y="3" width="18" height="18" rx="2" />
          <path d="M3 9h18M3 15h18M9 3v18M15 3v18" />
        </>
      )}
    </svg>
  )
}

function prettyLabel(value: unknown) {
  return String(value ?? '').replace(/_/g, ' ')
}

function barValue(d: unknown, xKey: string): string {
  if (!d || typeof d !== 'object') return ''
  const rec = d as Record<string, unknown>
  if (xKey in rec) return String(rec[xKey] ?? '')
  const payload = rec.payload
  if (payload && typeof payload === 'object' && xKey in payload) {
    return String((payload as Record<string, unknown>)[xKey] ?? '')
  }
  return ''
}

function FilterField({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="filter-field">
      <span className="filter-field__label">{label}</span>
      {children}
    </label>
  )
}

const TOOLTIP_STYLE = {
  borderRadius: 'var(--radius-lg)',
  border: '1px solid var(--color-border)',
  background: 'var(--color-surface)',
  fontFamily: 'var(--font-sans)',
  fontSize: '0.8125rem',
  boxShadow: 'var(--shadow-md)',
} as const

function Chart({ title, data, xKey, fill, iconClass, glyph, selected, onSelect }: {
  title: string
  data: Record<string, unknown>[]
  xKey: string
  fill: string
  iconClass: string
  glyph: Glyph
  selected: string
  onSelect: (value: string) => void
}) {
  const isGravity = xKey === 'gravity'
  const valueKey = isGravity ? 'count' : 'win_rate'
  const height = Math.max(128, data.length * 36 + 8)

  return (
    <figure className="chart">
      <div className="chart__header">
        <span className={`chart__icon ${iconClass}`} aria-hidden>
          <ChartGlyph name={glyph} />
        </span>
        <h2>{title}</h2>
      </div>
      {data.length === 0 ? (
        <p className="chart__empty">No labeled rows in this filter.</p>
      ) : (
        <ResponsiveContainer width="100%" height={height}>
          <BarChart data={data} layout="vertical" margin={{ top: 4, right: 44, bottom: 4, left: 4 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" horizontal={false} />
            <XAxis
              type="number"
              domain={isGravity ? [0, 'auto'] : [0, 100]}
              hide
            />
            <YAxis
              type="category"
              dataKey={xKey}
              width={148}
              tickFormatter={prettyLabel}
              tick={{ fontSize: 11, fill: 'var(--color-text-muted)' }}
              axisLine={false}
              tickLine={false}
            />
            <Tooltip
              formatter={(v) => [isGravity ? v : `${v ?? 0}%`, isGravity ? 'Count' : 'Win rate']}
              labelFormatter={prettyLabel}
              contentStyle={TOOLTIP_STYLE}
              labelStyle={{ fontWeight: 600, color: 'var(--color-text)' }}
            />
            <Bar
              dataKey={valueKey}
              fill={fill}
              radius={[0, 4, 4, 0]}
              maxBarSize={18}
              cursor="pointer"
              onClick={(d) => {
                const value = barValue(d, xKey)
                if (value) onSelect(value)
              }}
            >
              {data.map((row) => {
                const value = String(row[xKey] ?? '')
                const dimmed = Boolean(selected) && selected !== value
                return <Cell key={value} fill={fill} opacity={dimmed ? 0.35 : 1} />
              })}
              <LabelList
                dataKey={valueKey}
                position="right"
                formatter={(v) => (isGravity ? String(v ?? '') : `${v ?? 0}%`)}
                style={{ fontSize: 11, fill: 'var(--color-text-muted)' }}
              />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      )}
    </figure>
  )
}

function heatColor(winRate: number): string {
  const t = Math.max(0, Math.min(100, winRate)) / 100
  const r = Math.round(242 - t * 180)
  const g = Math.round(246 - t * 90)
  const b = Math.round(254 - t * 20)
  return `rgb(${r}, ${g}, ${b})`
}

function Heatmap({ data, selectedJob, selectedHandoff, onSelect }: {
  data: JobHandoffHeatmap
  selectedJob: string
  selectedHandoff: string
  onSelect: (job: string, handoff: string) => void
}) {
  const lookup = new Map(
    data.cells.map((c) => [`${c.job}|${c.handoff}`, c]),
  )

  return (
    <figure className="chart chart--heatmap">
      <div className="chart__header">
        <span className="chart__icon chart__icon--green" aria-hidden>
          <ChartGlyph name="grid" />
        </span>
        <h2>Win rate: job × handoff</h2>
      </div>
      <div className="heatmap-wrap">
        <div
          className="heatmap"
          style={{ gridTemplateColumns: `minmax(8.5rem, 11rem) repeat(${data.handoffs.length}, 1fr)` }}
        >
          <div className="heatmap__corner" />
          {data.handoffs.map((h) => (
            <div key={h} className="heatmap__col-label" title={prettyLabel(h)}>{prettyLabel(h)}</div>
          ))}
          {data.jobs.map((job) => (
            <Fragment key={job}>
              <div className="heatmap__row-label" title={prettyLabel(job)}>{prettyLabel(job)}</div>
              {data.handoffs.map((handoff) => {
                const cell = lookup.get(`${job}|${handoff}`)
                const thin = !cell || cell.total < data.min_sample
                const active = selectedJob === job && selectedHandoff === handoff
                const label = cell
                  ? `${prettyLabel(job)} × ${prettyLabel(handoff)}: ${cell.win_rate}% (${cell.wins}/${cell.total})`
                  : `${prettyLabel(job)} × ${prettyLabel(handoff)}: no data`
                return (
                  <button
                    key={`${job}|${handoff}`}
                    type="button"
                    className={`heatmap__cell${thin ? ' heatmap__cell--thin' : ''}${active ? ' heatmap__cell--active' : ''}`}
                    style={thin || !cell ? undefined : { background: heatColor(cell.win_rate) }}
                    title={label}
                    aria-pressed={active}
                    aria-label={label}
                    disabled={!cell}
                    onClick={() => onSelect(job, handoff)}
                  >
                    {cell ? (
                      thin ? <span className="heatmap__n">n={cell.total}</span> : (
                        <>
                          <span className="heatmap__rate">{cell.win_rate}%</span>
                          <span className="heatmap__n">n={cell.total}</span>
                        </>
                      )
                    ) : '—'}
                  </button>
                )
              })}
            </Fragment>
          ))}
        </div>
      </div>
      <div className="heatmap__legend">
        <span>Click a cell to filter by job and handoff. Cells with n &lt; {data.min_sample} are greyed out.</span>
        <span className="heatmap__scale" aria-hidden>
          <span>0%</span>
          <span className="heatmap__scale-bar" />
          <span>100%</span>
        </span>
      </div>
    </figure>
  )
}

export default function App() {
  const [filters, setFilters] = useState<Filters | null>(null)
  const [meetings, setMeetings] = useState<Meeting[]>([])
  const [total, setTotal] = useState(0)
  const [metrics, setMetrics] = useState<Metrics | null>(null)
  const [health, setHealth] = useState<Health | null>(null)
  const [loading, setLoading] = useState(true)
  const [labeledOnly, setLabeledOnly] = useState(true)
  const [seller, setSeller] = useState('')
  const [closed, setClosed] = useState('')
  const [primaryJob, setPrimaryJob] = useState('')
  const [handoff, setHandoff] = useState('')
  const [trust, setTrust] = useState('')
  const [trigger, setTrigger] = useState('')
  const [gravity, setGravity] = useState('')
  const [volumeBand, setVolumeBand] = useState('')
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
    if (gravity) p.set('system_gravity', gravity)
    if (volumeBand) p.set('volume_band', volumeBand)
    if (q) p.set('q', q)
    if (labeledOnly) p.set('labeled_only', 'true')
    return p
  }, [seller, closed, primaryJob, handoff, trust, trigger, gravity, volumeBand, q, labeledOnly])

  useEffect(() => {
    fetch(`${API}/health`).then((r) => r.json()).then(setHealth)
    fetch(`${API}/filters`).then((r) => r.json()).then(setFilters)
  }, [])

  useEffect(() => {
    const p = params()
    let cancelled = false
    Promise.all([
      fetch(`${API}/meetings?${p}`).then((r) => r.json()),
      fetch(`${API}/metrics?${p}`).then((r) => r.json()),
    ]).then(([meetingsRes, metricsRes]: [{ items: Meeting[]; total: number }, Metrics]) => {
      if (cancelled) return
      setMeetings(meetingsRes.items)
      setTotal(meetingsRes.total)
      setMetrics(metricsRes)
      setLoading(false)
    })
    return () => { cancelled = true }
  }, [params])

  const filtersActive = !labeledOnly || Boolean(
    seller || closed !== '' || primaryJob || handoff || trust || trigger || gravity || volumeBand || q,
  )

  const chartSelected: Record<string, string> = {
    job: primaryJob,
    handoff,
    trigger,
    gravity,
    volume_band: volumeBand,
  }

  const selectChart = (xKey: string, value: string) => {
    const toggle = (current: string, set: (v: string) => void) => set(current === value ? '' : value)
    if (xKey === 'job') toggle(primaryJob, setPrimaryJob)
    else if (xKey === 'handoff') toggle(handoff, setHandoff)
    else if (xKey === 'trigger') toggle(trigger, setTrigger)
    else if (xKey === 'gravity') toggle(gravity, setGravity)
    else if (xKey === 'volume_band') toggle(volumeBand, setVolumeBand)
  }

  const chips = [
    primaryJob && { key: 'job', label: 'Job', value: primaryJob, clear: () => setPrimaryJob('') },
    handoff && { key: 'handoff', label: 'Handoff', value: handoff, clear: () => setHandoff('') },
    trust && { key: 'trust', label: 'Trust', value: trust, clear: () => setTrust('') },
    trigger && { key: 'trigger', label: 'Trigger', value: trigger, clear: () => setTrigger('') },
    gravity && { key: 'gravity', label: 'Gravity', value: gravity, clear: () => setGravity('') },
    volumeBand && { key: 'volume', label: 'Volume', value: volumeBand, clear: () => setVolumeBand('') },
  ].filter(Boolean) as { key: string; label: string; value: string; clear: () => void }[]

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
      <a className="skip-link" href="#main">Skip to content</a>
      <header className="app-header">
        <div className="app-header__brand">
          <div className="app-header__logo" aria-hidden>V</div>
          <div>
            <h1 className="app-header__title">Vambe Dashboard</h1>
            <p className="app-header__subtitle">Sales meeting insights &amp; win-rate analytics</p>
          </div>
        </div>
        <div className="app-header__stats">
          {health && (
            <span className="stat-pill">
              {health.llm_labels.toLocaleString()} labeled · {health.total_meetings.toLocaleString()} total
            </span>
          )}
          {filtersActive && (
            <span className="stat-pill stat-pill--neutral">{total.toLocaleString()} in view</span>
          )}
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

      <main id="main">
      {tab === 'dimensions' ? (
        <DimensionsPage />
      ) : (
        <>
      <section className="filters" aria-label="Filters">
        <FilterField label="Coverage">
          <select
            value={labeledOnly ? 'labeled' : 'all'}
            onChange={(e) => setLabeledOnly(e.target.value === 'labeled')}
          >
            <option value="labeled">Labeled</option>
            <option value="all">All meetings</option>
          </select>
        </FilterField>
        <FilterField label="Seller">
          <select value={seller} onChange={(e) => setSeller(e.target.value)}>
            <option value="">All</option>
            {filters?.sellers.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </FilterField>
        <FilterField label="Outcome">
          <select value={closed} onChange={(e) => setClosed(e.target.value)}>
            <option value="">All</option>
            <option value="1">Closed won</option>
            <option value="0">Open</option>
          </select>
        </FilterField>
        <FilterField label="Primary job">
          <select value={primaryJob} onChange={(e) => setPrimaryJob(e.target.value)}>
            <option value="">All</option>
            {filters?.primary_jobs.map((j) => <option key={j} value={j}>{j.replace(/_/g, ' ')}</option>)}
          </select>
        </FilterField>
        <FilterField label="Handoff">
          <select value={handoff} onChange={(e) => setHandoff(e.target.value)}>
            <option value="">All</option>
            {filters?.handoff_topologies.map((h) => <option key={h} value={h}>{h.replace(/_/g, ' ')}</option>)}
          </select>
        </FilterField>
        <FilterField label="Trust">
          <select value={trust} onChange={(e) => setTrust(e.target.value)}>
            <option value="">All</option>
            {filters?.trust_surfaces.map((t) => <option key={t} value={t}>{t.replace(/_/g, ' ')}</option>)}
          </select>
        </FilterField>
        <FilterField label="Trigger">
          <select value={trigger} onChange={(e) => setTrigger(e.target.value)}>
            <option value="">All</option>
            {filters?.buying_triggers.map((t) => <option key={t} value={t}>{t.replace(/_/g, ' ')}</option>)}
          </select>
        </FilterField>
        <FilterField label="Gravity">
          <select value={gravity} onChange={(e) => setGravity(e.target.value)}>
            <option value="">All</option>
            {filters?.system_gravities.map((g) => <option key={g} value={g}>{g.replace(/_/g, ' ')}</option>)}
          </select>
        </FilterField>
        <FilterField label="Volume">
          <select value={volumeBand} onChange={(e) => setVolumeBand(e.target.value)}>
            <option value="">All</option>
            {filters?.volume_bands.map((v) => <option key={v} value={v}>{v.replace(/_/g, ' ')}</option>)}
          </select>
        </FilterField>
        <FilterField label="Search">
          <input
            placeholder="Name or transcript…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
        </FilterField>
      </section>

      <p className="section-heading">Performance metrics</p>
      <p className="chart-hint">Click a bar or heatmap cell to filter. Click again to clear.</p>
      {chips.length > 0 && (
        <div className="chips" aria-label="Active chart filters">
          {chips.map((chip) => (
            <button key={chip.key} type="button" className="chip" onClick={chip.clear}>
              {chip.label}: {prettyLabel(chip.value)}
              <span aria-hidden>×</span>
            </button>
          ))}
        </div>
      )}
      <section className="charts">
        {BAR_CHARTS.map((c) => (
          <Chart
            key={c.xKey}
            title={c.title}
            data={(metrics?.[c.dataKey] ?? []) as Record<string, unknown>[]}
            xKey={c.xKey}
            fill={c.color}
            iconClass={c.icon}
            glyph={c.glyph}
            selected={chartSelected[c.xKey]}
            onSelect={(value) => selectChart(c.xKey, value)}
          />
        ))}
      </section>
      {metrics?.job_handoff_heatmap.handoffs.length ? (
        <Heatmap
          data={metrics.job_handoff_heatmap}
          selectedJob={primaryJob}
          selectedHandoff={handoff}
          onSelect={(job, nextHandoff) => {
            if (primaryJob === job && handoff === nextHandoff) {
              setPrimaryJob('')
              setHandoff('')
            } else {
              setPrimaryJob(job)
              setHandoff(nextHandoff)
            }
          }}
        />
      ) : null}

      <section className="table-section">
        <div className="table-section__header">
          <h2 className="table-section__title">Meetings</h2>
          <span className="table-section__count">
            {meetings.length} shown{total > meetings.length ? ` · ${total.toLocaleString()} match` : ''}
          </span>
        </div>
        <div className="table-wrap">
          {meetings.length === 0 ? (
            <div className="empty-state">
              <div className="empty-state__icon" aria-hidden>
                <ChartGlyph name="bars" />
              </div>
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
                    <td>{m.primary_job ? prettyLabel(m.primary_job) : '—'}</td>
                    <td>{m.handoff_topology ? prettyLabel(m.handoff_topology) : '—'}</td>
                    <td>
                      {m.model ? (
                        <span className="model-cell">
                          <span title={m.model}>{shortModelName(m.model)}</span>
                          {m.prompt_version && (
                            <span className="badge badge--version" title="Prompt version">
                              {m.prompt_version}
                            </span>
                          )}
                        </span>
                      ) : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </section>
        </>
      )}
      </main>
    </div>
  )
}
