import React from 'react'

const STATUS = { goal: '🎯 goal', expanded: 'expanded', dead_end: '⛔ dead end', beam_pruned: '✂ beam-pruned', loop: '↺ loop' }

function Node({ id, nodes, best, file, onZoom }) {
  const n = nodes[id]
  if (!n) return null
  const onBest = best.includes(id)
  return (
    <li>
      <div className={`tnode ${n.status} ${onBest ? 'best' : ''}`}>
        {n.screenshot && <img src={file(n.screenshot)} onClick={() => onZoom(file(n.screenshot))} />}
        <div>
          <div><b>{n.depth === 0 ? 'START' : `“${n.thought?.text}”`}</b> <span className="muted">value {n.value?.toFixed?.(1)}</span></div>
          <div className="small">{n.title}</div>
          <div className="small muted">{STATUS[n.status] || n.status}{n.thought?.rationale && n.depth > 0 ? ` · ${n.thought.rationale}` : ''}{n.finding_count ? ` · ${n.finding_count} findings` : ''}</div>
          {n.pruned?.length > 0 && <div className="pruned">Pruned thoughts: {n.pruned.map(p => `“${p.text}” (${p.score}; ${p.reason})`).join(' · ')}</div>}
        </div>
      </div>
      {n.children?.length > 0 && <ul>{n.children.map(c => <Node key={c} id={c} nodes={nodes} best={best} file={file} onZoom={onZoom} />)}</ul>}
    </li>
  )
}

export default function ThoughtTree({ goal, nodes, best, file, onZoom }) {
  const root = Object.values(nodes).find(n => !n.parent)
  return (
    <div className="panel">
      <h2>Tree-of-Thought exploration — {goal}</h2>
      <p className="muted small">Each node is a page state; each edge is a candidate action ("thought") scored by the value function. Highlighted nodes form the chosen decision path.</p>
      <ul className="tree">{root && <Node id={root.id} nodes={nodes} best={best} file={file} onZoom={onZoom} />}</ul>
    </div>
  )
}
