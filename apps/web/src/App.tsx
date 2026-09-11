import { Fragment, useCallback, useEffect, useState, type ReactNode } from 'react'
import {
  Bar, BarChart, CartesianGrid, Cell, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import DimensionsPage from './DimensionsPage'
import { DIMENSIONS } from './dimensions'
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
  email: string
  seller: string
  meeting_date: string
  closed: number
  transcript: string | null
  primary_job: string | null
  handoff_topology: string | null
  system_gravity: string | null
  trust_surface: string | null
  buying_trigger: string | null
  volume_band: string | null
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
  summary: { labeled: number; wins: number; win_rate: number }
}

const MIN_SAMPLE = 5
const CHART_HEIGHT = 240
const MIX_CHART_HEIGHT = 160

// Win-rate small multiples — same shape, same fixed height, laid out as a 2x2 grid.
const BAR_CHARTS = [
  { title: 'Tasa de conversión por trabajo principal', dataKey: 'by_job' as const, xKey: 'job' as const, dimensionKey: 'primary_job', color: CHART_COLORS.job, icon: 'chart__icon--blue', glyph: 'bars' as const },
  { title: 'Tasa de conversión por topología de transferencia', dataKey: 'by_handoff' as const, xKey: 'handoff' as const, dimensionKey: 'handoff_topology', color: CHART_COLORS.handoff, icon: 'chart__icon--sky', glyph: 'handoff' as const },
  { title: 'Tasa de conversión por motivo de compra', dataKey: 'by_trigger' as const, xKey: 'trigger' as const, dimensionKey: 'buying_trigger', color: CHART_COLORS.trigger, icon: 'chart__icon--orange', glyph: 'trigger' as const },
  { title: 'Tasa de conversión por banda de volumen', dataKey: 'by_volume_band' as const, xKey: 'volume_band' as const, dimensionKey: 'volume_band', color: CHART_COLORS.volume, icon: 'chart__icon--teal', glyph: 'volume' as const },
] as const

// Composition, not a rate — kept out of the win-rate grid so it can't be misread as a fifth conversion chart.
const MIX_CHART = {
  title: 'Mezcla de gravedad del sistema', dataKey: 'gravity_mix' as const, xKey: 'gravity' as const, dimensionKey: 'system_gravity', color: CHART_COLORS.gravity, icon: 'chart__icon--purple', glyph: 'gravity' as const,
} as const

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

const LABEL_BY_KEY: Record<string, Record<string, string>> = Object.fromEntries(
  DIMENSIONS.map((d) => [d.key, Object.fromEntries(d.enums.map((e) => [e.key, e.label]))]),
)

function dimLabel(dimensionKey: string, value: unknown): string {
  const v = String(value ?? '')
  return LABEL_BY_KEY[dimensionKey]?.[v] ?? prettyLabel(v)
}

const CHIP_DIM_KEY: Record<string, string> = {
  job: 'primary_job',
  handoff: 'handoff_topology',
  trust: 'trust_surface',
  trigger: 'buying_trigger',
  gravity: 'system_gravity',
  volume: 'volume_band',
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

function Chart({ title, data, xKey, dimensionKey, fill, iconClass, glyph, selected, onSelect, height }: {
  title: string
  data: Record<string, unknown>[]
  xKey: string
  dimensionKey: string
  fill: string
  iconClass: string
  glyph: Glyph
  selected: string
  onSelect: (value: string) => void
  height: number
}) {
  const isGravity = xKey === 'gravity'
  const valueKey = isGravity ? 'count' : 'win_rate'
  const plotData: Record<string, unknown>[] = data.map((row) => ({
    ...row,
    _label: isGravity ? String(row[valueKey] ?? '') : `${row.win_rate ?? 0}% · n=${row.total ?? '?'}`,
  }))

  return (
    <figure className="chart">
      <div className="chart__header">
        <span className={`chart__icon ${iconClass}`} aria-hidden>
          <ChartGlyph name={glyph} />
        </span>
        <h2>{title}</h2>
      </div>
      {data.length === 0 ? (
        <p className="chart__empty">No hay filas etiquetadas en este filtro.</p>
      ) : (
        <ResponsiveContainer width="100%" height={height}>
          <BarChart data={plotData} layout="vertical" margin={{ top: 4, right: 68, bottom: 4, left: 4 }}>
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
              tickFormatter={(v) => dimLabel(dimensionKey, v)}
              tick={{ fontSize: 11, fill: 'var(--color-text-muted)' }}
              axisLine={false}
              tickLine={false}
            />
            <Tooltip
              formatter={(_v, _name, entry) => {
                const row = entry?.payload as Record<string, unknown> | undefined
                return [String(row?._label ?? ''), isGravity ? 'Cantidad' : 'Tasa de conversión']
              }}
              labelFormatter={(v) => dimLabel(dimensionKey, v)}
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
              {plotData.map((row) => {
                const value = String(row[xKey] ?? '')
                const dimmed = Boolean(selected) && selected !== value
                const thin = !isGravity && Number(row.total ?? 0) < MIN_SAMPLE
                return (
                  <Cell
                    key={value}
                    fill={thin ? 'var(--color-text-subtle)' : fill}
                    opacity={dimmed ? 0.35 : thin ? 0.55 : 1}
                  />
                )
              })}
              <LabelList
                dataKey="_label"
                position="right"
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
        <h2>Tasa de conversión: trabajo × transferencia</h2>
      </div>
      <div className="heatmap-wrap">
        <div
          className="heatmap"
          style={{ gridTemplateColumns: `minmax(8.5rem, 11rem) repeat(${data.handoffs.length}, 1fr)` }}
        >
          <div className="heatmap__corner" />
          {data.handoffs.map((h) => (
            <div key={h} className="heatmap__col-label" title={dimLabel('handoff_topology', h)}>{dimLabel('handoff_topology', h)}</div>
          ))}
          {data.jobs.map((job) => (
            <Fragment key={job}>
              <div className="heatmap__row-label" title={dimLabel('primary_job', job)}>{dimLabel('primary_job', job)}</div>
              {data.handoffs.map((handoff) => {
                const cell = lookup.get(`${job}|${handoff}`)
                const thin = !cell || cell.total < data.min_sample
                const active = selectedJob === job && selectedHandoff === handoff
                const label = cell
                  ? `${dimLabel('primary_job', job)} × ${dimLabel('handoff_topology', handoff)}: ${cell.win_rate}% (${cell.wins}/${cell.total})`
                  : `${dimLabel('primary_job', job)} × ${dimLabel('handoff_topology', handoff)}: sin datos`
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
        <span>Haz clic en una celda para filtrar por trabajo y transferencia. Las celdas con n &lt; {data.min_sample} aparecen en gris.</span>
        <span className="heatmap__scale" aria-hidden>
          <span>0%</span>
          <span className="heatmap__scale-bar" />
          <span>100%</span>
        </span>
      </div>
    </figure>
  )
}

function TranscriptDrawer({ meeting, onClose }: { meeting: Meeting; onClose: () => void }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      window.removeEventListener('keydown', onKey)
      document.body.style.overflow = prev
    }
  }, [onClose])

  const labels = [
    meeting.primary_job && ['Trabajo', meeting.primary_job, 'primary_job'],
    meeting.handoff_topology && ['Transferencia', meeting.handoff_topology, 'handoff_topology'],
    meeting.system_gravity && ['Gravedad', meeting.system_gravity, 'system_gravity'],
    meeting.trust_surface && ['Confianza', meeting.trust_surface, 'trust_surface'],
    meeting.buying_trigger && ['Motivo', meeting.buying_trigger, 'buying_trigger'],
    meeting.volume_band && ['Volumen', meeting.volume_band, 'volume_band'],
  ].filter(Boolean) as [string, string, string][]

  return (
    <div className="drawer-scrim" onClick={onClose}>
      <aside
        className="drawer"
        role="dialog"
        aria-modal="true"
        aria-labelledby="transcript-title"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="drawer__header">
          <div>
            <h2 id="transcript-title" className="drawer__title">{meeting.nombre}</h2>
            <p className="drawer__meta">
              {meeting.seller} · {meeting.meeting_date} · {meeting.closed ? 'Ganado' : 'Abierto'}
            </p>
          </div>
          <button type="button" className="drawer__close" onClick={onClose} aria-label="Cerrar transcripción">
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
              <path d="M6 6l12 12M18 6L6 18" />
            </svg>
          </button>
        </header>
        {labels.length > 0 && (
          <dl className="drawer__labels">
            {labels.map(([k, v, dimensionKey]) => (
              <div key={k}>
                <dt>{k}</dt>
                <dd>{dimLabel(dimensionKey, v)}</dd>
              </div>
            ))}
          </dl>
        )}
        <h3 className="drawer__section">Transcripción</h3>
        <p className="transcript">{meeting.transcript || 'No hay transcripción para esta reunión.'}</p>
      </aside>
    </div>
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
  const [selected, setSelected] = useState<Meeting | null>(null)

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
    primaryJob && { key: 'job', label: 'Trabajo', value: primaryJob, clear: () => setPrimaryJob('') },
    handoff && { key: 'handoff', label: 'Transferencia', value: handoff, clear: () => setHandoff('') },
    trust && { key: 'trust', label: 'Confianza', value: trust, clear: () => setTrust('') },
    trigger && { key: 'trigger', label: 'Motivo', value: trigger, clear: () => setTrigger('') },
    gravity && { key: 'gravity', label: 'Gravedad', value: gravity, clear: () => setGravity('') },
    volumeBand && { key: 'volume', label: 'Volumen', value: volumeBand, clear: () => setVolumeBand('') },
  ].filter(Boolean) as { key: string; label: string; value: string; clear: () => void }[]

  if (loading) {
    return (
      <div className="app">
        <div className="loading">
          <span className="loading__spinner" aria-hidden />
          Cargando dashboard…
        </div>
      </div>
    )
  }

    return (
    <div className="app">
      <a className="skip-link" href="#main">Saltar al contenido</a>
      <header className="app-header">
        <div className="app-header__brand">
          <div className="app-header__logo" aria-hidden>V</div>
          <div>
            <h1 className="app-header__title">Vambe Dashboard</h1>
            <p className="app-header__subtitle">Información de reuniones de ventas y análisis de tasa de conversión</p>
          </div>
        </div>
        <div className="app-header__stats">
          {health && (
            <span className="stat-pill">
              {health.llm_labels.toLocaleString()} etiquetadas · {health.total_meetings.toLocaleString()} en total
            </span>
          )}
          {filtersActive && (
            <span className="stat-pill stat-pill--neutral">{total.toLocaleString()} en vista</span>
          )}
        </div>
      </header>

      <nav className="tabs" aria-label="Navegación principal">
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
          Dimensiones
        </button>
      </nav>

      <main id="main">
      {tab === 'dimensions' ? (
        <DimensionsPage />
      ) : (
        <>
      <section className="filters" aria-label="Filtros">
        <FilterField label="Cobertura">
          <select
            value={labeledOnly ? 'labeled' : 'all'}
            onChange={(e) => setLabeledOnly(e.target.value === 'labeled')}
          >
            <option value="labeled">Etiquetados</option>
            <option value="all">Todas las reuniones</option>
          </select>
        </FilterField>
        <FilterField label="Vendedor">
          <select value={seller} onChange={(e) => setSeller(e.target.value)}>
            <option value="">Todos</option>
            {filters?.sellers.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </FilterField>
        <FilterField label="Resultado">
          <select value={closed} onChange={(e) => setClosed(e.target.value)}>
            <option value="">Todos</option>
            <option value="1">Cerrado ganado</option>
            <option value="0">Abierto</option>
          </select>
        </FilterField>
        <FilterField label="Trabajo principal">
          <select value={primaryJob} onChange={(e) => setPrimaryJob(e.target.value)}>
            <option value="">Todos</option>
            {filters?.primary_jobs.map((j) => <option key={j} value={j}>{dimLabel('primary_job', j)}</option>)}
          </select>
        </FilterField>
        <FilterField label="Transferencia">
          <select value={handoff} onChange={(e) => setHandoff(e.target.value)}>
            <option value="">Todos</option>
            {filters?.handoff_topologies.map((h) => <option key={h} value={h}>{dimLabel('handoff_topology', h)}</option>)}
          </select>
        </FilterField>
        <FilterField label="Confianza">
          <select value={trust} onChange={(e) => setTrust(e.target.value)}>
            <option value="">Todos</option>
            {filters?.trust_surfaces.map((t) => <option key={t} value={t}>{dimLabel('trust_surface', t)}</option>)}
          </select>
        </FilterField>
        <FilterField label="Motivo">
          <select value={trigger} onChange={(e) => setTrigger(e.target.value)}>
            <option value="">Todos</option>
            {filters?.buying_triggers.map((t) => <option key={t} value={t}>{dimLabel('buying_trigger', t)}</option>)}
          </select>
        </FilterField>
        <FilterField label="Gravedad">
          <select value={gravity} onChange={(e) => setGravity(e.target.value)}>
            <option value="">Todos</option>
            {filters?.system_gravities.map((g) => <option key={g} value={g}>{dimLabel('system_gravity', g)}</option>)}
          </select>
        </FilterField>
        <FilterField label="Volumen">
          <select value={volumeBand} onChange={(e) => setVolumeBand(e.target.value)}>
            <option value="">Todos</option>
            {filters?.volume_bands.map((v) => <option key={v} value={v}>{dimLabel('volume_band', v)}</option>)}
          </select>
        </FilterField>
        <FilterField label="Buscar">
          <input
            placeholder="Nombre o transcripción…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
        </FilterField>
      </section>

      <p className="section-heading">Métricas de rendimiento</p>
      {metrics?.summary && (
        <section className="kpis" aria-label="Totales filtrados">
          <div className="kpi">
            <span className="kpi__value">{metrics.summary.win_rate}%</span>
            <span className="kpi__label">Tasa de conversión</span>
          </div>
          <div className="kpi">
            <span className="kpi__value">{metrics.summary.labeled.toLocaleString()}</span>
            <span className="kpi__label">Etiquetadas en vista</span>
          </div>
          <div className="kpi">
            <span className="kpi__value">{metrics.summary.wins.toLocaleString()}</span>
            <span className="kpi__label">Cerradas ganadas</span>
          </div>
        </section>
      )}
      <p className="chart-hint">Haz clic en una barra o celda del mapa de calor para filtrar. Vuelve a hacer clic para quitar el filtro. Las barras con menos de {MIN_SAMPLE} reuniones se muestran atenuadas.</p>
      {chips.length > 0 && (
        <div className="chips" aria-label="Filtros de gráficos activos">
          {chips.map((chip) => (
            <button key={chip.key} type="button" className="chip" onClick={chip.clear}>
              {chip.label}: {dimLabel(CHIP_DIM_KEY[chip.key], chip.value)}
              <span aria-hidden>×</span>
            </button>
          ))}
        </div>
      )}

      <section className="hero-row">
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
        <Chart
          title={MIX_CHART.title}
          data={(metrics?.[MIX_CHART.dataKey] ?? []) as Record<string, unknown>[]}
          xKey={MIX_CHART.xKey}
          dimensionKey={MIX_CHART.dimensionKey}
          fill={MIX_CHART.color}
          iconClass={MIX_CHART.icon}
          glyph={MIX_CHART.glyph}
          height={MIX_CHART_HEIGHT}
          selected={chartSelected.gravity}
          onSelect={(value) => selectChart('gravity', value)}
        />
      </section>

      <section className="charts">
        {BAR_CHARTS.map((c) => (
          <Chart
            key={c.xKey}
            title={c.title}
            data={(metrics?.[c.dataKey] ?? []) as Record<string, unknown>[]}
            xKey={c.xKey}
            dimensionKey={c.dimensionKey}
            fill={c.color}
            iconClass={c.icon}
            glyph={c.glyph}
            height={CHART_HEIGHT}
            selected={chartSelected[c.xKey]}
            onSelect={(value) => selectChart(c.xKey, value)}
          />
        ))}
      </section>

      <section className="table-section">
        <div className="table-section__header">
          <h2 className="table-section__title">Reuniones</h2>
          <span className="table-section__count">
            {meetings.length} mostradas{total > meetings.length ? ` · ${total.toLocaleString()} coinciden` : ''}
            {' · haz clic en una fila para ver la transcripción'}
          </span>
        </div>
        <div className="table-wrap">
          {meetings.length === 0 ? (
            <div className="empty-state">
              <div className="empty-state__icon" aria-hidden>
                <ChartGlyph name="bars" />
              </div>
              <p>Ninguna reunión coincide con tus filtros.</p>
            </div>
          ) : (
            <table>
              <thead>
                <tr>
                  <th>Nombre</th>
                  <th>Vendedor</th>
                  <th>Fecha</th>
                  <th>Cerrado</th>
                  <th>Trabajo principal</th>
                  <th>Transferencia</th>
                  <th>Modelo</th>
                </tr>
              </thead>
              <tbody>
                {meetings.map((m) => (
                  <tr
                    key={m.id}
                    className="table-row--clickable"
                    onClick={() => setSelected(m)}
                  >
                    <td>
                      <button type="button" className="row-open" onClick={() => setSelected(m)}>
                        {m.nombre}
                      </button>
                    </td>
                    <td>{m.seller}</td>
                    <td>{m.meeting_date}</td>
                    <td>
                      <span className={`badge ${m.closed ? 'badge--won' : 'badge--open'}`}>
                        {m.closed ? 'Ganado' : 'Abierto'}
                      </span>
                    </td>
                    <td>{m.primary_job ? dimLabel('primary_job', m.primary_job) : '—'}</td>
                    <td>{m.handoff_topology ? dimLabel('handoff_topology', m.handoff_topology) : '—'}</td>
                    <td>
                      {m.model ? (
                        <span className="model-cell">
                          <span title={m.model}>{shortModelName(m.model)}</span>
                          {m.prompt_version && (
                            <span className="badge badge--version" title="Versión del prompt">
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
      {selected && <TranscriptDrawer meeting={selected} onClose={() => setSelected(null)} />}
        </>
      )}
      </main>
    </div>
  )
}
