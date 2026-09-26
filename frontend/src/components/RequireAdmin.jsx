import { Link, Navigate, useLocation } from 'react-router-dom'

import { useAuth } from '../context/AuthContext.jsx'

/**
 * Frontend guard for the admin workspace.
 *
 * This is a UX convenience only. The real security boundary is the backend
 * `get_current_admin` dependency, which rejects non-admin tokens with 403 no
 * matter what this component does.
 */
export default function RequireAdmin({ children }) {
  const { isAdmin, isAuthenticated, isRestoring, user } = useAuth()
  const location = useLocation()

  if (isRestoring) {
    return (
      <section className="auth-gate-page section">
        <div className="container auth-gate-card">
          <p className="eyebrow">SmartCycle</p>
          <h1>Checking your session…</h1>
          <p>One moment while we confirm your access.</p>
        </div>
      </section>
    )
  }

  if (!isAuthenticated) {
    return <Navigate replace state={{ from: location }} to="/login" />
  }

  if (!isAdmin) {
    return (
      <section className="auth-gate-page section">
        <div className="container auth-gate-card">
          <p className="eyebrow">Restricted area</p>
          <h1>Administrator access required</h1>
          <p>
            You are signed in as {user?.name || 'a standard user'} with the standard
            user role, so the SmartCycle operations workspace is not available.
            The API independently rejects this request for non-admin accounts.
          </p>
          <Link className="button button-primary" to="/dashboard">Go to my dashboard</Link>
        </div>
      </section>
    )
  }

  return children
}
