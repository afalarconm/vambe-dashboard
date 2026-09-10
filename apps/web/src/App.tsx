import { useCallback, useEffect, useState } from 'react'
import {
  Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import './App.css'

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

function Chart({ title, data, xKey, fill }: {
  title: string
  data: Record<string, unknown>[]
  xKey: string
  fill: string
}) {
  return (
    <div className="chart">
      <h2>{title}</h2>
      <ResponsiveContainer width="100%" height={240}>
        <BarChart data={data} margin={{ bottom: 50 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey={xKey} angle={-30} textAnchor="end" interval={0} tick={{ fontSize: 10 }} />
          <YAxis unit={xKey === 'gravity' ? '' : '%'} domain={xKey === 'gravity' ? undefined : [0, 100]} />
          <Tooltip formatter={(v) => [xKey === 'gravity' ? v : `${v ?? 0}%`, xKey === 'gravity' ? 'Count' : 'Win rate']} />
          <Bar dataKey={xKey === 'gravity' ? 'count' : 'win_rate'} fill={fill} radius={[4, 4, 0, 0]} />
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
  const [seller, setSeller] = useState('')
  const [closed, setClosed] = useState('')
  const [primaryJob, setPrimaryJob] = useState('')
  const [handoff, setHandoff] = useState('')
  const [trust, setTrust] = useState('')
  const [trigger, setTrigger] = useState('')
  const [q, setQ] = useState('')

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
    fetch(`${API}/filters`).then((r) => r.json()).then(setFilters)
    fetch(`${API}/metrics/win-rate-by-job`).then((r) => r.json()).then(setByJob)
    fetch(`${API}/metrics/win-rate-by-handoff`).then((r) => r.json()).then(setByHandoff)
    fetch(`${API}/metrics/win-rate-by-trigger`).then((r) => r.json()).then(setByTrigger)
    fetch(`${API}/metrics/system-gravity-mix`).then((r) => r.json()).then(setGravityMix)
  }, [])

  useEffect(() => {
    fetch(`${API}/meetings?${params()}`)
      .then((r) => r.json())
      .then((d) => { setMeetings(d.items); setTotal(d.total) })
  }, [params])

  const labeled = meetings.filter((m) => m.prompt_version).length

  return (
    <div className="app">
      <header>
        <h1>Vambe Dashboard</h1>
        <span>{total.toLocaleString()} meetings · {labeled} labeled in view</span>
      </header>

      <section className="filters">
        <select value={seller} onChange={(e) => setSeller(e.target.value)}>
          <option value="">All sellers</option>
          {filters?.sellers.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
        <select value={closed} onChange={(e) => setClosed(e.target.value)}>
          <option value="">All outcomes</option>
          <option value="1">Closed won</option>
          <option value="0">Open</option>
        </select>
        <select value={primaryJob} onChange={(e) => setPrimaryJob(e.target.value)}>
          <option value="">All jobs</option>
          {filters?.primary_jobs.map((j) => <option key={j} value={j}>{j}</option>)}
        </select>
        <select value={handoff} onChange={(e) => setHandoff(e.target.value)}>
          <option value="">All handoff</option>
          {filters?.handoff_topologies.map((h) => <option key={h} value={h}>{h}</option>)}
        </select>
        <select value={trust} onChange={(e) => setTrust(e.target.value)}>
          <option value="">All trust</option>
          {filters?.trust_surfaces.map((t) => <option key={t} value={t}>{t}</option>)}
        </select>
        <select value={trigger} onChange={(e) => setTrigger(e.target.value)}>
          <option value="">All triggers</option>
          {filters?.buying_triggers.map((t) => <option key={t} value={t}>{t}</option>)}
        </select>
        <input placeholder="Search name or transcript…" value={q} onChange={(e) => setQ(e.target.value)} />
      </section>

      <section className="charts">
        <Chart title="Win rate by primary job" data={byJob} xKey="job" fill="#4f46e5" />
        <Chart title="Win rate by handoff topology" data={byHandoff} xKey="handoff" fill="#0891b2" />
        <Chart title="Win rate by buying trigger" data={byTrigger} xKey="trigger" fill="#059669" />
        <Chart title="System gravity mix" data={gravityMix} xKey="gravity" fill="#d97706" />
      </section>

      <section className="table-wrap">
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
                <td className={m.closed ? 'won' : 'open'}>{m.closed ? '✓' : '—'}</td>
                <td>{m.primary_job ?? '—'}</td>
                <td>{m.handoff_topology ?? '—'}</td>
                <td title={m.model ?? undefined}>{m.prompt_version ?? '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  )
}
