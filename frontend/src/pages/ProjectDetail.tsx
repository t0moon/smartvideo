import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { getProject, updateProject, listReviews, getProjectStatus, resumeProject, uploadAsset, listAssets, type Project, type ReviewTask, type ProjectStatus, type UploadAssetType, type UploadedAsset } from '../api.ts'
import ReviewCard from '../components/ReviewCard.tsx'

export default function ProjectDetail() {
  const { projectId } = useParams<{ projectId: string }>()
  const navigate = useNavigate()
  const [project, setProject] = useState<Project | null>(null)
  const [reviews, setReviews] = useState<ReviewTask[]>([])
  const [projectStatus, setProjectStatus] = useState<ProjectStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [briefInput, setBriefInput] = useState('')
  const [running, setRunning] = useState(false)
  const [statusMsg, setStatusMsg] = useState('')
  const [resultVideo, setResultVideo] = useState('')

  // 需求三: 用户素材上传
  const [uploadType, setUploadType] = useState<UploadAssetType>('image')
  const [uploadFile, setUploadFile] = useState<File | null>(null)
  const [uploading, setUploading] = useState(false)
  const [uploadedAssets, setUploadedAssets] = useState<UploadedAsset[]>([])
  const [uploadMsg, setUploadMsg] = useState('')

  const loadUploadedAssets = async () => {
    if (!projectId) return
    try {
      const assets = await listAssets(undefined, projectId)
      setUploadedAssets(assets.filter(a => (a.tags || []).includes('user_upload')))
    } catch { /* ignore */ }
  }

  const load = async () => {
    if (!projectId) return
    try {
      const p = await getProject(projectId)
      setProject(p)
      setBriefInput(p.brief)
      // Load pending reviews
      const revs = await listReviews(projectId)
      setReviews(revs)
      // Load resumable pipeline status (需求一A: HITL continuity)
      try {
        const st = await getProjectStatus(projectId)
        setProjectStatus(st)
      } catch { /* status is best-effort */ }
      // Load user-uploaded assets (需求三)
      try { await loadUploadedAssets() } catch { /* ignore */ }
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

  // 需求一A：项目在节点中断后，从中断处继续（直接 resume 暂停时的 review）
  const handleContinue = async () => {
    if (!projectId || !projectStatus?.pause_review_id) return
    setRunning(true)
    setStatusMsg('Resuming pipeline from last checkpoint...')
    try {
      const data = await resumeProject(projectId, projectStatus.pause_review_id)
      if (data.status === 'completed') {
        setStatusMsg('Pipeline resumed and completed')
        setResultVideo(data.final_video_path)
        const updated = await getProject(projectId)
        setProject(updated)
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

  // 需求三: 上传用户素材（产品图 / 模特图 / 模特音色 / BGM）
  const handleUpload = async () => {
    if (!projectId || !uploadFile) return
    setUploading(true)
    setUploadMsg('')
    try {
      const a = await uploadAsset(projectId, uploadType, uploadFile)
      setUploadMsg('上传成功：' + a.name)
      setUploadFile(null)
      const el = document.getElementById('asset-file-input') as HTMLInputElement | null
      if (el) el.value = ''
      await loadUploadedAssets()
    } catch (e) {
      setUploadMsg('上传失败：' + e)
    } finally {
      setUploading(false)
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

        {/* 需求一A: Pipeline status banner + continue/new controls */}
        {projectStatus?.has_state && (
          <div style={{
            marginBottom: 20, padding: 14, borderRadius: 8,
            background: projectStatus.paused ? '#fff7ed' : '#f0fdf4',
            border: `1px solid ${projectStatus.paused ? '#fed7aa' : '#bbf7d0'}`,
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 10 }}>
              <div>
                <p style={{ fontSize: 14, fontWeight: 600, margin: 0 }}>
                  {projectStatus.paused ? '⏸ 项目已暂停在中途节点' : '✅ 流水线已结束'}
                </p>
                <p style={{ fontSize: 12, color: '#666', margin: '4px 0 0' }}>
                  当前阶段：<strong>{projectStatus.stage}</strong>
                  {projectStatus.paused && projectStatus.pause_stage ? ` · 暂停于：${projectStatus.pause_stage}` : ''}
                </p>
              </div>
              <div style={{ display: 'flex', gap: 8 }}>
                {projectStatus.paused && projectStatus.pause_review_id && (
                  <button onClick={handleContinue} disabled={running}
                    style={{ background: running ? '#999' : '#16a34a', color: '#fff', border: 'none', padding: '8px 18px', borderRadius: 6, fontSize: 14, fontWeight: 500, cursor: running ? 'not-allowed' : 'pointer' }}>
                    {running ? '恢复中...' : '继续项目'}
                  </button>
                )}
                <button onClick={() => navigate('/')}
                  style={{ background: 'none', border: '1px solid #ccc', padding: '8px 18px', borderRadius: 6, fontSize: 14, cursor: 'pointer' }}>
                  新建项目
                </button>
              </div>
            </div>
          </div>
        )}

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

        {/* 需求三: 用户素材上传 */}
        <div style={{ marginBottom: 20, padding: 16, background: '#faf5ff', border: '1px solid #e9d5ff', borderRadius: 8 }}>
          <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 10, color: '#6b21a8' }}>
            📤 上传广告素材
          </h3>
          <p style={{ fontSize: 12, color: '#777', margin: '0 0 12px' }}>
            支持：产品图 / 模特图（image、character）；模特音色（voice）；配乐 BGM（bgm，将自动混入成片）。
          </p>
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
            <select
              value={uploadType}
              onChange={e => setUploadType(e.target.value as UploadAssetType)}
              style={{ padding: '8px 10px', border: '1px solid #ddd', borderRadius: 6, fontSize: 14 }}
            >
              <option value="image">产品图 / 素材图</option>
              <option value="character">模特图</option>
              <option value="voice">模特音色</option>
              <option value="bgm">配乐 BGM</option>
            </select>
            <input
              id="asset-file-input"
              type="file"
              onChange={e => setUploadFile(e.target.files?.[0] || null)}
              style={{ flex: 1, minWidth: 180, fontSize: 13 }}
            />
            <button
              onClick={handleUpload}
              disabled={uploading || !uploadFile}
              style={{ background: uploading ? '#999' : '#6b21a8', color: '#fff', border: 'none', padding: '8px 18px', borderRadius: 6, fontSize: 14, fontWeight: 500, cursor: uploading || !uploadFile ? 'not-allowed' : 'pointer' }}
            >
              {uploading ? '上传中...' : '上传'}
            </button>
          </div>
          {uploadMsg && (
            <div style={{ marginTop: 10, fontSize: 13, color: uploadMsg.includes('失败') ? '#dc2626' : '#16a34a' }}>
              {uploadMsg}
            </div>
          )}

          {uploadedAssets.length > 0 && (
            <div style={{ marginTop: 12 }}>
              <p style={{ fontSize: 13, fontWeight: 500, margin: '0 0 6px' }}>已上传（{uploadedAssets.length}）：</p>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                {uploadedAssets.map(a => (
                  <span key={a.asset_id} style={{ fontSize: 12, background: '#fff', border: '1px solid #e9d5ff', borderRadius: 12, padding: '4px 10px', color: '#6b21a8' }}>
                    {a.tags?.[0] || a.asset_type}: {a.name}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>

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
