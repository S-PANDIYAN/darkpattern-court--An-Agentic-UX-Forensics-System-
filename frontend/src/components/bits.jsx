import React from 'react'
const COL = { GUILTY: '#dc2626', LIKELY: '#d97706', 'LIKELY MANIPULATIVE': '#d97706', 'INSUFFICIENT EVIDENCE': '#6b7280', ACQUITTED: '#16a34a' }
export const VerdictBadge = ({ v }) => <span className="badge" style={{ background: COL[v] || '#6b7280' }}>{v}</span>
export const Pct = ({ x }) => <span className="pct">{Math.round(x * 100)}%</span>
export const Gauge = ({ score }) => {
  const c = score < 25 ? '#16a34a' : score < 45 ? '#ca8a04' : score < 70 ? '#ea580c' : '#dc2626'
  return (
    <div className="gauge" style={{ background: `conic-gradient(${c} ${score * 3.6}deg, #1f2937 0)` }}>
      <div><b>{score}</b><small>/100</small></div>
    </div>
  )
}
