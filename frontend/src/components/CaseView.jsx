import React, { useEffect, useState } from 'react'
import { getCase, fileUrl } from '../api.js'
import { VerdictBadge, Pct, Gauge } from './bits.jsx'
import ThoughtTree from './ThoughtTree.jsx'

export default function CaseView({ id }) {
  const [c, setC] = useState(null)
  const [tab, setTab] = useState('charges')
  const [zoom, setZoom] = useState(null)
  useEffect(() => {
    let t, alive = true
    const load = () => getCase(id).then(x => { if (!alive) return; setC(x); if (!['complete', 'error'].includes(x.status)) t = setTimeout(load, 1500) })
    load(); return () => { alive = false; clearTimeout(t) }
  }, [id])
  if (!c) return <p>Loading case…</p>
  const F = p => fileUrl(id, p)

  if (c.status !== 'complete') return (
    <div className="panel">
      <h1>Case {id} — {c.status === 'error' ? 'investigation failed' : 'investigation in progress…'}</h1>
      <p className="url">{c.url}</p>
      {c.status === 'error' && <pre className="bad">{c.error}</pre>}
      <pre className="log">{(c.log || []).join('\n')}</pre>
    </div>
  )
  const v = c.verdict
  return (
    <div>
      <section className="verdict">
        <Gauge score={v.manipulation_score} />
        <div className="vtext">
          <div className="muted small">Case {c.id} · {c.url}</div>
          <h1><VerdictBadge v={v.label} /> {v.summary}</h1>
          <div className="muted">{c.charges.length} charges · {c.findings.length} exhibits · grade <b>{v.grade}</b> ·
            OCR {c.capabilities?.ocr ? 'on' : 'off'} · Vision LLM {c.capabilities?.vision_llm ? 'on' : 'off'}</div>
          <div className="links"><a href={F('report.html')} target="_blank">Court record (HTML)</a><a href={F('report.pdf')} target="_blank">Evidence cards (PDF)</a></div>
        </div>
      </section>
      <div className="tabs">
        {[['charges', 'Charges & evidence'], ['testimony', 'Testimony'], ['tree', 'Thought tree'], ['log', 'Agent log']].map(([k, l]) =>
          <button key={k} className={tab === k ? 'on' : ''} onClick={() => setTab(k)}>{l}</button>)}
      </div>

      {tab === 'charges' && c.charges.map(ch => (
        <div className="charge" key={ch.pattern}>
          <div className="chead"><VerdictBadge v={ch.verdict} /><h2>{ch.count_no}: {ch.name}</h2><Pct x={ch.confidence} /></div>
          <div className="muted small">{ch.category} · India CCPA 2023: {ch.india_ccpa} · witnesses: {ch.sources.join(', ')}</div>
          <p>{ch.charge}</p>
          <div className="cards">
            {ch.exhibits.map(x => (
              <div className="ecard" key={x.id}>
                <div className="ehead"><b>Exhibit {x.id}</b><span>step {x.step} · {x.source} · <Pct x={x.confidence} /></span></div>
                {x.exhibit && <img src={F(x.exhibit)} onClick={() => setZoom(F(x.exhibit))} />}
                <p>{x.description}</p>
                <ul>{x.evidence.map((e, i) => <li key={i}>{e}</li>)}</ul>
              </div>
            ))}
          </div>
          <details><summary>Legal &amp; regulatory basis ({ch.authorities.length})</summary>
            {ch.authorities.map(a => <blockquote key={a.id}><b>{a.source}</b><br />{a.excerpt}<br /><a href={a.url} target="_blank">{a.url}</a></blockquote>)}
          </details>
        </div>
      ))}

      {tab === 'testimony' && c.journeys.map(j => (
        <div className="panel" key={j.goal}>
          <h2>{j.label} — {j.reached ? '✅ reached' : '❌ not reached'} in {j.clicks} clicks</h2>
          <div className="timeline">
            {j.steps.map((s, i) => (
              <div className="tstep" key={i}>
                <div className="dot">{s.step}</div>
                <div className="tbody">
                  <p><b>Step {s.step}:</b> {s.testimony}</p>
                  {s.observations.map((o, k) => <div className="obs" key={k}>⚠ {o}</div>)}
                </div>
                {s.screenshot && <img className="thumb" src={F(s.screenshot)} onClick={() => setZoom(F(s.screenshot))} />}
              </div>
            ))}
          </div>
          {j.alternatives.length > 0 && <p className="muted small">Alternative decision paths explored: {j.alternatives.map(a => `${a.path.length - 1} clicks → "${a.end}"${a.reached ? ' ✓' : ''}`).join(' · ')}</p>}
        </div>
      ))}

      {tab === 'tree' && Object.entries(c.trees).map(([g, nodes]) => <ThoughtTree key={g} goal={g} nodes={nodes} best={c.journeys.find(j => j.goal === g)?.path || []} file={F} onZoom={setZoom} />)}
      {tab === 'log' && <pre className="log">{c.log.join('\n')}</pre>}
      {zoom && <div className="zoom" onClick={() => setZoom(null)}><img src={zoom} /></div>}
    </div>
  )
}
