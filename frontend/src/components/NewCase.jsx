import React, { useEffect, useState } from 'react'
import { getMeta, createCase } from '../api.js'

export default function NewCase() {
  const [meta, setMeta] = useState(null)
  const [url, setUrl] = useState('')
  const [goals, setGoals] = useState(['explore'])
  const [opts, setOpts] = useState({ max_depth: 6, beam_width: 2, branching: 3 })
  const [err, setErr] = useState('')
  const [busy, setBusy] = useState(false)
  useEffect(() => { getMeta().then(setMeta).catch(e => setErr(String(e))) }, [])
  const toggle = g => setGoals(goals.includes(g) ? goals.filter(x => x !== g) : [...goals, g])
  const sample = s => { setUrl(new URL(s.url, window.location.origin.replace(':5173', ':8000')).href); setGoals(s.goals) }
  const submit = async e => {
    e.preventDefault(); setBusy(true); setErr('')
    try { const r = await createCase({ url, goals, ...opts }); window.location.hash = `#/case/${r.id}` }
    catch (x) { setErr(String(x)) } finally { setBusy(false) }
  }
  return (
    <div className="grid2">
      <form className="panel" onSubmit={submit}>
        <h1>File a new case</h1>
        <p className="muted">The forensic agent opens the interface in a real browser, simulates user goals with Tree-of-Thought route exploration, and files courtroom-style evidence.</p>
        <label>Interface under audit (URL)</label>
        <input value={url} onChange={e => setUrl(e.target.value)} placeholder="https://example.com/account" required />
        <label>User goals to simulate</label>
        <div className="chips">
          {meta && Object.entries(meta.goals).map(([k, g]) => (
            <button type="button" key={k} className={'chip ' + (goals.includes(k) ? 'sel' : '')} onClick={() => toggle(k)}>{g.label}</button>
          ))}
        </div>
        <div className="row3">
          {[['max_depth', 'Max depth', 1, 12], ['beam_width', 'Beam width', 1, 5], ['branching', 'Thoughts / node', 1, 6]].map(([k, l, mn, mx]) => (
            <div key={k}><label>{l}</label><input type="number" min={mn} max={mx} value={opts[k]} onChange={e => setOpts({ ...opts, [k]: +e.target.value })} /></div>
          ))}
        </div>
        <button className="primary" disabled={busy || !url || !goals.length}>{busy ? 'Filing…' : 'Open investigation'}</button>
        {err && <p className="bad">{err}</p>}
      </form>
      <div className="panel">
        <h2>Sample interfaces</h2>
        <p className="muted">Built-in demo sites containing deliberate dark patterns, plus a fair control site.</p>
        {meta?.samples.map(s => (
          <div key={s.url} className="sample" onClick={() => sample(s)}>
            <b>{s.name}</b><span className="muted"> · {s.goals.join(', ')}</span>
          </div>
        ))}
        <h2 style={{ marginTop: 24 }}>Pipeline</h2>
        <ol className="pipeline">
          <li>Playwright browser agent</li><li>UI component snapshot (DOM + computed styles)</li><li>Screenshot + OCR pipeline</li>
          <li>Tree-of-Thought route exploration</li><li>Detectors + optional multimodal LLM witness</li><li>FTC guideline RAG</li><li>Evidence cards &amp; verdict</li>
        </ol>
      </div>
    </div>
  )
}
