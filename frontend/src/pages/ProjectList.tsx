import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { listProjects, createProject, deleteProject, type Project } from '../api.ts'

const STAGE_COLORS: Record<string, string> = {
  created: '#6b7280', requirement: '#f59e0b', storyboard: '#3b82f6',
  scene_gen: '#8b5cf6', video_prod: '#06b6d4', review: '#ef4444',
  publish: '#10b981', done: '#22c55e', archived: '#9ca3af',
}

export default function ProjectList() {
  const [projects, setProjects] = useState<Project[]>([])
  const [loading, setLoading] = useState(true)
  const [showCreate, setShowCreate] = useState(false)
  const [newName, setNewName] = useState('')
  const [newBrief, setNewBrief] = useState('')
  const navigate = useNavigate()

  const load = async () => {
    try {
      setLoading(true)
      setProjects(await listProjects())
    } catch { /* ignore */ }
    finally { setLoading(false) }
  }

  useEffect(() => { load() }, [])

  const handleCreate = async () => {
    if (!newName.trim()) return
    try {
      const p = await createProject({ name: newName, brief: newBrief })
      setShowCreate(false)
      setNewName('')
      setNewBrief('')
      navigate(`/project/${p.project_id}`)
    } catch (e) { alert(e) }
  }

  const handleDelete = async (id: string) => {
    if (!confirm('Delete this project?')) return
    try { await deleteProject(id); load() }
    catch (e) { alert(e) }
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
        <h1 style={{ fontSize: 22, fontWeight: 600 }}>Projects</h1>
        <button onClick={() => setShowCreate(true)} style={{
          background: '#1a1a2e', color: '#fff', border: 'none', padding: '8px 20px',
          borderRadius: 6, fontSize: 14, fontWeight: 500,
        }}>+ New Project</button>
      </div>

      {showCreate && (
        <div style={{ background: '#fff', borderRadius: 8, padding: 20, marginBottom: 20, boxShadow: '0 1px 3px rgba(0,0,0,.08)' }}>
          <h3 style={{ marginBottom: 12, fontSize: 16 }}>Create Project</h3>
          <input placeholder='Project name' value={newName} onChange={e => setNewName(e.target.value)}
            style={{ width: '100%', padding: '8px 12px', border: '1px solid #ddd', borderRadius: 6, marginBottom: 8 }} />
          <textarea placeholder='Brief' value={newBrief} onChange={e => setNewBrief(e.target.value)} rows={3}
            style={{ width: '100%', padding: '8px 12px', border: '1px solid #ddd', borderRadius: 6, marginBottom: 8, resize: 'vertical' }} />
          <div style={{ display: 'flex', gap: 8 }}>
            <button onClick={handleCreate} style={{ background: '#1a1a2e', color: '#fff', border: 'none', padding: '6px 16px', borderRadius: 6 }}>Create</button>
            <button onClick={() => setShowCreate(false)} style={{ background: '#eee', border: 'none', padding: '6px 16px', borderRadius: 6 }}>Cancel</button>
          </div>
        </div>
      )}

      {loading && <p style={{ color: '#999' }}>Loading...</p>}

      {!loading && projects.length === 0 && (
        <div style={{ textAlign: 'center', padding: 60, color: '#999' }}>
          <p style={{ fontSize: 18, marginBottom: 8 }}>No projects yet</p>
          <p style={{ fontSize: 14 }}>Click '+ New Project' to create one</p>
        </div>
      )}

      <div style={{ display: 'grid', gap: 12 }}>
        {projects.map(p => (
          <div key={p.project_id} onClick={() => navigate(`/project/${p.project_id}`)}
            style={{
              background: '#fff', borderRadius: 8, padding: '16px 20px',
              boxShadow: '0 1px 3px rgba(0,0,0,.08)', cursor: 'pointer',
              display: 'flex', justifyContent: 'space-between', alignItems: 'center',
            }}>
            <div>
              <div style={{ fontWeight: 600, marginBottom: 4 }}>{p.name}</div>
              <div style={{ fontSize: 12, color: '#999' }}>
                {p.project_id.slice(0, 12)} &middot; {new Date(p.created_at).toLocaleDateString()}
              </div>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <span style={{
                background: STAGE_COLORS[p.stage] || '#999', color: '#fff',
                padding: '3px 10px', borderRadius: 12, fontSize: 12,
              }}>{p.stage}</span>
              <button onClick={e => { e.stopPropagation(); handleDelete(p.project_id) }}
                style={{ background: 'none', border: 'none', color: '#ccc', fontSize: 18, padding: 4 }}>&times;</button>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}