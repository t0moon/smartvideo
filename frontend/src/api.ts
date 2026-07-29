const API_BASE = '/api/v1'

export interface Project {
  project_id: string
  name: string
  brief: string
  workflow_name: string
  stage: string
  created_at: string
  updated_at: string
  archived_at?: string
  meta: Record<string, unknown>
}

export interface ProjectCreate {
  name: string
  brief?: string
  workflow_name?: string
}

export async function listProjects(): Promise<Project[]> {
  const res = await fetch(`${API_BASE}/projects/`)
  if (!res.ok) throw new Error(`Failed to list projects: ${res.status}`)
  return res.json()
}

export async function getProject(id: string): Promise<Project> {
  const res = await fetch(`${API_BASE}/projects/${id}`)
  if (!res.ok) throw new Error(`Failed to get project: ${res.status}`)
  return res.json()
}

export async function createProject(data: ProjectCreate): Promise<Project> {
  const res = await fetch(`${API_BASE}/projects/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!res.ok) throw new Error(`Failed to create project: ${res.status}`)
  return res.json()
}

export async function deleteProject(id: string): Promise<void> {
  const res = await fetch(`${API_BASE}/projects/${id}`, { method: 'DELETE' })
  if (!res.ok) throw new Error(`Failed to delete project: ${res.status}`)
}

export async function updateProject(id: string, updates: Record<string, unknown>): Promise<Project> {
  const res = await fetch(`${API_BASE}/projects/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(updates),
  })
  if (!res.ok) throw new Error(`Failed to update project: ${res.status}`)
  return res.json()
}


// ── Review API ──────────────────────────────────────────

export interface ReviewTask {
  review_id: string
  project_id: string
  stage: string
  status: string
  content: Record<string, unknown>
  comments: Array<{text: string; action: string; reviewer: string; created_at: string}>
  created_at: string
  resolved_at?: string
  reviewer: string
}

export async function listReviews(projectId?: string, status?: string): Promise<ReviewTask[]> {
  const params = new URLSearchParams()
  if (projectId) params.set('project_id', projectId)
  if (status) params.set('status', status)
  const qs = params.toString()
  const res = await fetch(`/api/v1/reviews/` + (qs ? `?` + qs : ''))
  if (!res.ok) throw new Error(`Failed to list reviews: ` + res.status)
  return res.json()
}

export async function getReview(reviewId: string): Promise<ReviewTask> {
  const res = await fetch(`/api/v1/reviews/` + reviewId)
  if (!res.ok) throw new Error(`Failed to get review: ` + res.status)
  return res.json()
}

export async function approveReview(reviewId: string, comment = '', reviewer = ''): Promise<ReviewTask> {
  const res = await fetch(`/api/v1/reviews/` + reviewId + `/approve`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ reviewer, comment }),
  })
  if (!res.ok) throw new Error(`Failed to approve: ` + res.status)
  return res.json()
}

export async function rejectReview(reviewId: string, comment = '', reviewer = ''): Promise<ReviewTask> {
  const res = await fetch(`/api/v1/reviews/` + reviewId + `/reject`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ reviewer, comment }),
  })
  if (!res.ok) throw new Error(`Failed to reject: ` + res.status)
  return res.json()
}

export async function addReviewComment(reviewId: string, text: string, reviewer = ''): Promise<ReviewTask> {
  const res = await fetch(`/api/v1/reviews/` + reviewId + `/comment`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ comment: text, reviewer }),
  })
  if (!res.ok) throw new Error(`Failed to add comment: ` + res.status)
  return res.json()
}

export async function resumeProject(projectId: string, reviewId: string) {
  const res = await fetch(`/api/v1/workspace/resume/` + projectId + `?review_id=` + reviewId, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ review_id: reviewId }),
  })
  if (!res.ok) throw new Error(`Failed to resume: ` + res.status)
  return res.json()
}


// --- Asset API --------------------------

export interface Asset {
  asset_id: string
  project_id: string
  asset_type: string
  name: string
  description: string
  file_path: string
  tags: string[]
  metadata: Record<string, unknown>
  created_at: string
}

export async function listAssets(assetType?: string, projectId?: string): Promise<Asset[]> {
  const params = new URLSearchParams()
  if (assetType) params.set("asset_type", assetType)
  if (projectId) params.set("project_id", projectId)
  const qs = params.toString()
  const url = '`/api/v1/assets/`' + (qs ? '`?`' + qs : '')
  const res = await fetch(url)
  if (!res.ok) throw new Error('`Failed to list assets: `' + res.status)
  return res.json()
}

export async function searchAssets(q: string): Promise<Asset[]> {
  const res = await fetch('`/api/v1/assets/search?q=`' + encodeURIComponent(q))
  if (!res.ok) throw new Error('`Failed to search assets: `' + res.status)
  return res.json()
}

export async function deleteAsset(id: string): Promise<void> {
  const res = await fetch('`/api/v1/assets/`' + id, { method: 'DELETE' })
  if (!res.ok) throw new Error('`Failed to delete asset: `' + res.status)
}
