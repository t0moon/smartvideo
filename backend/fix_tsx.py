import pathlib

d = 'C:/Users/gyue/Desktop/smartvideo-main/frontend/src/pages'
b = chr(96)  # backtick

# ProjectDetail.tsx
pd = '''import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { getProject, type Project } from '../api.ts'

export default function ProjectDetail() {
  const { projectId } = useParams<{ projectId: string }>()
  const navigate = useNavigate()
  const [project, setProject] = useState<Project | null>(null)
  const [loading, setLoading] = useState(true)
  const [briefInput, setBriefInput] = useState('')
  const [running, setRunning] = useState(false)
  const [resultVideo, setResultVideo] = useState('')

  useEffect(() => {
    if (!projectId) return
    ;(async () => {
      try {
        const p = await getProject(projectId!)
        setProject(p)
        setBriefInput(p.brief)
      } catch { /* ignore */ }
      finally { setLoading(false) }
    })()
  }, [projectId])

  const handleRun = async () => {
    if (!projectId || !briefInput.trim()) return
    setRunning(true)
    try {
      const res = await fetch(''' + b + '''/api/v1/workspace/run/${projectId}''' + b + ''', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ brief: briefInput }),
      })
      if (!res.ok) throw new Error(''' + b + '''Run failed: ${res.status}''' + b + ''')
      const data = await res.json()
      setResultVideo(data.final_video_path)
      const updated = await getProject(projectId)
      setProject(updated)
    } catch (e) {
      alert(e)
    } finally {
      setRunning(false)
    }
  }

  if (loading) return <p>Loading...</p>
  if (!project) return <p>Project not found</p>

  return (
    <div>
      <button onClick={() => navigate('/')} style={{ background: 'none', border: 'none', color: '#666', marginBottom: 16, cursor: 'pointer', fontSize: 14 }}>
        &larr; Back
      </button>

      <div style={{ background: '#fff', borderRadius: 8, padding: 24, boxShadow: '0 1px 3px rgba(0,0,0,.08)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start', marginBottom: 20 }}>
          <div>
            <h1 style={{ fontSize: 22, fontWeight: 600 }}>{project.name}</h1>
            <p style={{ fontSize: 13, color: '#999', marginTop: 4 }}>
              {project.project_id} &middot; {project.workflow_name}
            </p>
          </div>
          <span style={{
            background: '#1a1a2e', color: '#fff',
            padding: '4px 12px', borderRadius: 12, fontSize: 13,
          }}>{project.stage}</span>
        </div>

        <div style={{ marginBottom: 16 }}>
          <label style={{ fontSize: 14, fontWeight: 500, display: 'block', marginBottom: 6 }}>Brief</label>
          <textarea value={briefInput} onChange={e => setBriefInput(e.target.value)}
            rows={5} placeholder="Enter your video brief here..."
            style={{ width: '100%', padding: '10px 14px', border: '1px solid #ddd', borderRadius: 6, resize: 'vertical', fontSize: 14 }}
          />
        </div>

        <button onClick={handleRun} disabled={running || !briefInput.trim()}
          style={{
            background: running ? '#999' : '#1a1a2e', color: '#fff',
            border: 'none', padding: '10px 24px', borderRadius: 6, fontSize: 14,
            fontWeight: 500, cursor: running ? 'not-allowed' : 'pointer',
          }}>
          {running ? 'Generating...' : 'Run Pipeline'}
        </button>

        {resultVideo && (
          <div style={{ marginTop: 20, padding: 16, background: '#f0fdf4', borderRadius: 6, border: '1px solid #bbf7d0' }}>
            <p style={{ fontSize: 14, fontWeight: 500, color: '#16a34a' }}>Pipeline completed</p>
            <p style={{ fontSize: 13, color: '#666', marginTop: 4, wordBreak: 'break-all' }}>{resultVideo}</p>
          </div>
        )}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginTop: 20 }}>
        <div style={{ background: '#fff', borderRadius: 8, padding: 20, boxShadow: '0 1px 3px rgba(0,0,0,.08)' }}>
          <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 8 }}>Timeline</h3>
          <p style={{ fontSize: 13, color: '#999' }}>
            Created: {new Date(project.created_at).toLocaleString()}<br />
            Updated: {new Date(project.updated_at).toLocaleString()}<br />
            Stage: {project.stage}
          </p>
        </div>
        <div style={{ background: '#fff', borderRadius: 8, padding: 20, boxShadow: '0 1px 3px rgba(0,0,0,.08)' }}>
          <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 8 }}>Assets</h3>
          <p style={{ fontSize: 13, color: '#999' }}>Asset library coming in Phase 4</p>
        </div>
      </div>
    </div>
  )
}
'''

pathlib.Path(f'{d}/ProjectDetail.tsx').write_text(pd, encoding='utf-8')
print('ProjectDetail.tsx written')
