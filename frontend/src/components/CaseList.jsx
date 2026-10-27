import React, { useEffect, useState } from 'react'
import { listCases } from '../api.js'
import { VerdictBadge } from './bits.jsx'

export default function CaseList() {
  const [cases, setCases] = useState(null)
  useEffect(() => { listCases().then(setCases) }, [])
  if (!cases) return <p>Loading docket…</p>
  return (
    <div className="panel">
      <h1>Case docket</h1>
      <table className="docket"><thead><tr><th>Case</th><th>Interface</th><th>Goals</th><th>Status</th><th>Verdict</th><th>Score</th></tr></thead>
        <tbody>{cases.map(c => (
          <tr key={c.id} onClick={() => (window.location.hash = `#/case/${c.id}`)}>
            <td><code>{c.id}</code></td><td className="url">{c.url}</td><td>{(c.goals || []).join(', ')}</td><td>{c.status}</td>
            <td>{c.verdict ? <VerdictBadge v={c.verdict.label} /> : '—'}</td><td>{c.verdict?.manipulation_score ?? '—'}</td>
          </tr>))}
        </tbody></table>
      {!cases.length && <p className="muted">No cases yet.</p>}
    </div>
  )
}
