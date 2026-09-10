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
}

type WinRate = { job: string; wins: number; total: number; win_rate: number }

const API = '/api'

export default function App() {
  const [filters, setFilters] = useState<Filters | null>(null)
  const [meetings, setMeetings] = useState<Meeting[]>([])
  const [total, setTotal] = useState(0)
  const [winRates, setWinRates] = useState<WinRate[]>([])
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
    fetch(`${API}/metrics/win-rate-by-job`).then((r) => r.json()).then(setWinRates)
  }, [])

  useEffect(() => {
    fetch(`${API}/meetings?${params()}`)
      .then((r) => r.json())
      .then((d) => { setMeetings(d.items); setTotal(d.total) })
  }, [params])

  return (
    <div className="app">
      <header>
        <h1>Vambe Dashboard</h1>
        <span>{total.toLocaleString()} meetings</span>
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

      <section className="chart">
        <h2>Win rate by primary job</h2>
        <ResponsiveContainer width="100%" height={280}>
          <BarChart data={winRates} margin={{ bottom: 60 }}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="job" angle={-35} textAnchor="end" interval={0} tick={{ fontSize: 11 }} />
            <YAxis unit="%" domain={[0, 100]} />
            <Tooltip formatter={(v) => [`${v ?? 0}%`, 'Win rate']} />
            <Bar dataKey="win_rate" fill="#4f46e5" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
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
              <th>Trust</th>
              <th>Trigger</th>
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
                <td>{m.trust_surface ?? '—'}</td>
                <td>{m.buying_trigger ?? '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  )
}
