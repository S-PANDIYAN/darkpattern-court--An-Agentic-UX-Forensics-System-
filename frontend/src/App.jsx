import React, { useEffect, useState } from 'react'
import NewCase from './components/NewCase.jsx'
import CaseList from './components/CaseList.jsx'
import CaseView from './components/CaseView.jsx'
import { getHealth } from './api.js'

const useHash = () => {
  const [h, setH] = useState(window.location.hash || '#/')
  useEffect(() => { const f = () => setH(window.location.hash || '#/'); window.addEventListener('hashchange', f); return () => window.removeEventListener('hashchange', f) }, [])
  return h
}

export default function App() {
  const hash = useHash()
  const [health, setHealth] = useState(null)
  useEffect(() => { getHealth().then(setHealth).catch(() => setHealth({ ok: false })) }, [])
  const caseId = hash.startsWith('#/case/') ? hash.slice(7) : null
  return (
    <div>
      <header className="topbar">
        <a href="#/" className="logo">⚖️ DarkPattern Court</a>
        <span className="tag">Agentic UX Forensics</span>
        <nav><a href="#/">New case</a><a href="#/cases">Case docket</a></nav>
        <span className="health">
          {health ? (health.ok ? <>API ● <i className={health.ocr ? 'on' : 'off'}>OCR</i> <i className={health.vision_llm ? 'on' : 'off'}>Vision LLM</i></> : <b className="bad">API offline</b>) : '…'}
        </span>
      </header>
      <main className="container">
        {caseId ? <CaseView id={caseId} /> : hash === '#/cases' ? <CaseList /> : <NewCase />}
      </main>
    </div>
  )
}
