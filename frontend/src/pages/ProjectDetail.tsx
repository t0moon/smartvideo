import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { getProject, updateProject, listReviews, type Project, type ReviewTask } from '../api.ts'
import ReviewCard from '../components/ReviewCard.tsx'

export default function ProjectDetail() {
  const { projectId } = useParams<{ projectId: string }>()
  const navigate = useNavigate()
  const [project, setProject] = useState<Project | null>(null)
  const [reviews, setReviews] = useState<ReviewTask[]>([])
  const [loading, setLoading] = useState(true)
  const [briefInput, setBriefInput] = useState('')
  const [running, setRunning] = useState(false)
  const [statusMsg, setStatusMsg] = useState('')
  const [resultVideo, setResultVideo] = useState('')

  const load = async () => {
    if (!projectId) return
    try {
      const p = await getProject(projectId)
      setProject(p)
      setBriefInput(p.brief)
      // Load pending reviews
      const revs = await listReviews(projectId)
      setReviews(revs)
    } catch { /* ignore */ }
    finally { setLoading(false) }
  }

  useEffect(() => { load() }, [projectId])

  const handleRun = async () => {
    if (!projectId || !briefInput.trim()) return
    setRunning(true)
    setStatusMsg('Starting pipeline...')
    try {
      const res = await fetch(`/api/v1/workspace/run/` + projectId, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ brief: briefInput }),
      })
      if (!res.ok) throw new Error(`Run failed: ` + res.status)
      const data = await res.json()
      if (data.status === 'paused') {
        setStatusMsg(`Pipeline paused - review required`)
        load()  // Reload reviews
      } else if (data.status === 'completed') {
        setStatusMsg('Pipeline completed')
        setResultVideo(data.final_video_path)
        const updated = await getProject(projectId)
        setProject(updated)
      } else if (data.status === 'blocked') {
        setStatusMsg('Blocked by pending reviews')
      } else {
        setStatusMsg('Error: ' + (data.error || 'unknown'))
      }
    } catch (e) {
      setStatusMsg('Error: ' + e)
    } finally {
      setRunning(false)
    }
  }

  const handleReviewResolved = async () => {
    if (!projectId) return
    setStatusMsg('Review resolved!')
    await load()
    // Auto-resume if there are no more pending reviews
    const revs = await listReviews(projectId)
    const pending = revs.filter(r => r.status === 'pending')
    if (pending.length === 0) {
      setRunning(true)
      try {
        const res = await fetch(`/api/v1/workspace/resume/` + projectId + `?review_id=` + revs[0]?.review_id || '', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ review_id: revs[0]?.review_id || '' }),
        })
        const data = await res.json()
        if (data.status === 'completed') {
          setStatusMsg('Pipeline resumed and completed')
          setResultVideo(data.final_video_path)
        } else if (data.status === 'paused') {
          setStatusMsg('Pipeline paused for next review')
          await load()
        } else {
          setStatusMsg('Resumed')
          await load()
        }
      } catch (e) {
        setStatusMsg('Resume error: ' + e)
      } finally {
        setRunning(false)
      }
    }
  }

  if (loading) return <p>Loading...</p>
  if (!project) return <p>Project not found</p>

  const pendingReviews = reviews.filter(r => r.status === 'pending')

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
          <span style={{ background: '#1a1a2e', color: '#fff', padding: '4px 12px', borderRadius: 12, fontSize: 13 }}>
            {project.stage}
          </span>
        </div>

        {/* Pending Reviews */}
        {pendingReviews.length > 0 && (
          <div style={{ marginBottom: 20 }}>
            <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 8, color: '#92400e' }}>
              Pending Reviews (`{pendingReviews.length}`)
            </h3>
            {pendingReviews.map(r => (
              <ReviewCard key={r.review_id} review={r} onResolved={handleReviewResolved} />
            ))}
          </div>
        )}

        {/* Completed Reviews */}
        {reviews.filter(r => r.status !== 'pending').length > 0 && (
          <details style={{ marginBottom: 16 }}>
            <summary style={{ fontSize: 13, color: '#999', cursor: 'pointer' }}>
              Review History (`{reviews.filter(r => r.status !== 'pending').length}`)
            </summary>
            {reviews.filter(r => r.status !== 'pending').map(r => (
              <div key={r.review_id} style={{ fontSize: 12, color: '#666', padding: '8px 0', borderBottom: '1px solid #eee' }}>
                <strong>{r.stage}</strong>: {r.status} {r.reviewer ? 'by ' + r.reviewer : ''}
                {r.comments.map((c, i) => (
                  <div key={i} style={{ padding: '2px 0 2px 12px', color: '#999' }}>{c.text}</div>
                ))}
              </div>
            ))}
          </details>
        )}

        {/* Brief Input */}
        <div style={{ marginBottom: 16 }}>
          <label style={{ fontSize: 14, fontWeight: 500, display: 'block', marginBottom: 6 }}>Brief</label>
          <textarea value={briefInput} onChange={e => setBriefInput(e.target.value)}
            rows={5} placeholder='Enter your video brief here...'
            style={{ width: '100%', padding: '10px 14px', border: '1px solid #ddd', borderRadius: 6, resize: 'vertical', fontSize: 14 }}
          />
        </div>

        <button onClick={handleRun} disabled={running || !briefInput.trim() || pendingReviews.length > 0}
          style={{
            background: running ? '#999' : '#1a1a2e', color: '#fff',
            border: 'none', padding: '10px 24px', borderRadius: 6, fontSize: 14,
            fontWeight: 500, cursor: running ? 'not-allowed' : 'pointer',
          }}>
          {running ? 'Generating...' : pendingReviews.length > 0 ? 'Resolve Reviews First' : 'Run Pipeline'}
        </button>

        {statusMsg && (
          <div style={{ marginTop: 12, fontSize: 14, color: statusMsg.includes('Error') ? '#dc2626' : '#666' }}>
            {statusMsg}
          </div>
        )}

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
          <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 8 }}>Reviews</h3>
          <p style={{ fontSize: 13, color: '#999' }}>
            Total: `{reviews.length}`<br />
            Pending: `{pendingReviews.length}`
          </p>
        </div>
      </div>
    </div>
  )
}
