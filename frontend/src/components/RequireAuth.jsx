import { Navigate, useLocation } from 'react-router-dom'

import { useAuth } from '../context/AuthContext.jsx'

export default function RequireAuth({ children }) {
  const { isAuthenticated, isRestoring } = useAuth()
  const location = useLocation()

  if (isRestoring) {
    return (
      <section className="auth-gate-page section">
        <div className="container auth-gate-card">
          <p className="eyebrow">SmartCycle</p>
          <h1>Checking your session…</h1>
          <p>One moment while we confirm your login.</p>
        </div>
      </section>
    )
  }

  if (!isAuthenticated) {
    return <Navigate replace state={{ from: location }} to="/login" />
  }

  return children
}
