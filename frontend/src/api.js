export const API = import.meta.env.VITE_API || ''
const j = r => { if (!r.ok) throw new Error(r.status + ' ' + r.statusText); return r.json() }
export const getMeta = () => fetch(`${API}/api/meta`).then(j)
export const getHealth = () => fetch(`${API}/api/health`).then(j)
export const listCases = () => fetch(`${API}/api/cases`).then(j)
export const getCase = id => fetch(`${API}/api/cases/${id}`).then(j)
export const createCase = body => fetch(`${API}/api/cases`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }).then(j)
export const fileUrl = (id, path) => `${API}/api/cases/${id}/files/${path}`
