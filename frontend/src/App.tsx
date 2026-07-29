import { Routes, Route, Link } from 'react-router-dom'
import ProjectList from './pages/ProjectList.tsx'
import ProjectDetail from './pages/ProjectDetail.tsx'
import Assets from './pages/Assets.tsx'

export default function App() {
  return (
    <div style={{ minHeight: '100vh', background: '#f5f5f5' }}>
      <nav style={{
        background: '#1a1a2e',
        color: '#fff',
        padding: '12px 24px',
        display: 'flex',
        alignItems: 'center',
        gap: 24,
      }}>
        <Link to="/" style={{ color: '#fff', textDecoration: 'none', fontSize: 20, fontWeight: 700 }}>
          SmartVideo
        </Link>
        <Link to="/" style={{ color: '#aaa', textDecoration: 'none', fontSize: 14 }}>
          Projects
        </Link>
      </nav>
      <main style={{ maxWidth: 1200, margin: '0 auto', padding: 24 }}>
        <Routes>
          <Route path="/" element={<ProjectList />} />`n          <Route path="/assets" element={<Assets />} />
          <Route path="/project/:projectId" element={<ProjectDetail />} />
        </Routes>
      </main>
    </div>
  )
}

