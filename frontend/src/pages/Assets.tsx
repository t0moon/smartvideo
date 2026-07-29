import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { listAssets, searchAssets, deleteAsset, type Asset } from '../api.ts'

const TYPE_COLORS: Record<string, string> = {
  brand: '#3b82f6', character: '#8b5cf6', voice: '#06b6d4',
  prompt: '#f59e0b', image: '#10b981', video: '#ef4444',
  subtitle: '#ec4899', template: '#6366f1',
}

export default function Assets() {
  const [assets, setAssets] = useState<Asset[]>([])
  const [loading, setLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')
  const [typeFilter, setTypeFilter] = useState('')
  const navigate = useNavigate()

  const load = async () => {
    try {
      setLoading(true)
      if (searchQuery.trim()) {
        setAssets(await searchAssets(searchQuery))
      } else {
        setAssets(await listAssets(typeFilter || undefined))
      }
    } catch { /* ignore */ }
    finally { setLoading(false) }
  }

  useEffect(() => { load() }, [typeFilter])

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    load()
  }

  const handleDelete = async (id: string) => {
    if (!confirm('Delete this asset?')) return
    try { await deleteAsset(id); load() }
    catch (e) { alert(e) }
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
        <h1 style={{ fontSize: 22, fontWeight: 600 }}>Assets</h1>
        <button onClick={() => navigate('/')} style={{ background: '#eee', border: 'none', padding: '8px 16px', borderRadius: 6, fontSize: 14 }}>Back to Projects</button>
      </div>

      <div style={{ display: 'flex', gap: 12, marginBottom: 20 }}>
        <form onSubmit={handleSearch} style={{ display: 'flex', gap: 8, flex: 1 }}>
          <input
            placeholder='Search assets by tag or name...'
            value={searchQuery} onChange={e => setSearchQuery(e.target.value)}
            style={{ flex: 1, padding: '8px 14px', border: '1px solid #ddd', borderRadius: 6, fontSize: 14 }}
          />
          <button type='submit' style={{ background: '#1a1a2e', color: '#fff', border: 'none', padding: '8px 20px', borderRadius: 6 }}>Search</button>
        </form>
        <select value={typeFilter} onChange={e => setTypeFilter(e.target.value)}
          style={{ padding: '8px 14px', border: '1px solid #ddd', borderRadius: 6, fontSize: 14 }}>
          <option value=''>All Types</option>
          <option value='brand'>Brand</option>
          <option value='character'>Character</option>
          <option value='voice'>Voice</option>
          <option value='prompt'>Prompt</option>
          <option value='image'>Image</option>
          <option value='video'>Video</option>
          <option value='subtitle'>Subtitle</option>
        </select>
      </div>

      {loading && <p style={{ color: '#999' }}>Loading...</p>}

      {!loading && assets.length === 0 && (
        <div style={{ textAlign: 'center', padding: 60, color: '#999' }}>
          <p style={{ fontSize: 18, marginBottom: 8 }}>No assets found</p>
          <p style={{ fontSize: 14 }}>{searchQuery ? 'Try a different search term' : 'Assets are automatically collected after pipeline runs'}</p>
        </div>
      )}

      <div style={{ display: 'grid', gap: 8, gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))' }}>
        {assets.map(a => (
          <div key={a.asset_id}
            style={{ background: '#fff', borderRadius: 8, padding: 16, boxShadow: '0 1px 3px rgba(0,0,0,.08)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start', marginBottom: 8 }}>
              <div>
                <span style={{ background: TYPE_COLORS[a.asset_type] || '#999', color: '#fff', padding: '2px 8px', borderRadius: 8, fontSize: 11, marginRight: 8 }}>
                  {a.asset_type}
                </span>
                <strong style={{ fontSize: 14 }}>{a.name}</strong>
              </div>
              <button onClick={() => handleDelete(a.asset_id)}
                style={{ background: 'none', border: 'none', color: '#ccc', fontSize: 16, cursor: 'pointer', padding: 2 }}>&times;</button>
            </div>
            {a.description && (
              <p style={{ fontSize: 12, color: '#666', marginBottom: 6 }}>{a.description.slice(0, 120)}</p>
            )}
            <div style={{ fontSize: 11, color: '#999' }}>
              Project: {a.project_id.slice(0, 12)} &middot; {new Date(a.created_at).toLocaleDateString()}
            </div>
            {a.tags.length > 0 && (
              <div style={{ marginTop: 6, display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                {a.tags.filter(Boolean).map(t => (
                  <span key={t} style={{ background: '#f3f4f6', padding: '2px 8px', borderRadius: 4, fontSize: 11, color: '#666' }}>{t}</span>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
