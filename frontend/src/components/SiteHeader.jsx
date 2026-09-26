import { useEffect, useRef, useState } from 'react'
import { Link, NavLink, useNavigate } from 'react-router-dom'

import { useAuth } from '../context/AuthContext.jsx'
import Icon from './Icon.jsx'

const navigation = [
  { label: 'Home', to: '/' },
  { label: 'Sell Device', to: '/sell' },
  { label: 'Track Device', to: '/track' },
  { label: 'How It Works', to: '/how-it-works' },
  { label: 'About', to: '/about' },
  { label: 'Contact', to: '/contact' },
]

function navClass({ isActive }) {
  return isActive ? 'nav-link nav-link-active' : 'nav-link'
}

export default function SiteHeader() {
  const [menuOpen, setMenuOpen] = useState(false)
  const { isAdmin, isAuthenticated, logout, user } = useAuth()
  const navigate = useNavigate()
  const toggleRef = useRef(null)
  const panelRef = useRef(null)

  const closeMenu = () => setMenuOpen(false)

  const handleLogout = () => {
    logout()
    closeMenu()
    navigate('/')
  }

  // Stage 4C: Escape closes the mobile menu and returns focus to the toggle,
  // so keyboard users are never stranded inside an off-canvas panel.
  useEffect(() => {
    if (!menuOpen) return undefined

    const onKeyDown = (event) => {
      if (event.key !== 'Escape') return
      setMenuOpen(false)
      toggleRef.current?.focus()
    }
    const onPointerDown = (event) => {
      const panel = panelRef.current
      const toggle = toggleRef.current
      if (!panel || !toggle) return
      if (panel.contains(event.target) || toggle.contains(event.target)) return
      setMenuOpen(false)
    }

    document.addEventListener('keydown', onKeyDown)
    document.addEventListener('pointerdown', onPointerDown)
    return () => {
      document.removeEventListener('keydown', onKeyDown)
      document.removeEventListener('pointerdown', onPointerDown)
    }
  }, [menuOpen])

  const firstName = user?.name ? user.name.trim().split(' ')[0] : ''

  return (
    <header className="site-header">
      <div className="container header-inner">
        <Link className="brand" to="/" onClick={closeMenu}>
          <span className="brand-mark" aria-hidden="true"><Icon name="recycle" size={23} /></span>
          <span className="brand-copy">
            <strong>SmartCycle</strong>
            <small>Give your old electronics a second life.</small>
          </span>
        </Link>

        <nav className="desktop-navigation" aria-label="Primary navigation">
          {navigation.map((item) => (
            <NavLink className={navClass} end={item.to === '/'} key={item.to} to={item.to}>
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="header-actions">
          {isAuthenticated ? (
            <>
              {firstName ? <span className="header-user">Hi, {firstName}</span> : null}
              <NavLink className="header-login" onClick={closeMenu} to="/dashboard">Dashboard</NavLink>
              {isAdmin ? (
                <NavLink className="header-login" onClick={closeMenu} to="/admin">Admin</NavLink>
              ) : null}
              <button className="button button-secondary button-small header-logout" onClick={handleLogout} type="button">Log out</button>
            </>
          ) : (
            <>
              <NavLink className="header-login" to="/login">Login</NavLink>
              <Link className="button button-primary button-small" to="/register">Get started <Icon name="arrowRight" size={16} /></Link>
            </>
          )}
        </div>

        <button
          ref={toggleRef}
          aria-controls="mobile-navigation-panel"
          aria-expanded={menuOpen}
          aria-label={menuOpen ? 'Close navigation menu' : 'Open navigation menu'}
          className="menu-toggle"
          onClick={() => setMenuOpen((current) => !current)}
          type="button"
        >
          <Icon name={menuOpen ? 'close' : 'menu'} size={22} />
        </button>
      </div>

      {/*
        Stage 4C: the collapsed panel is removed from the accessibility tree and
        the tab order with `hidden`, rather than being clipped by max-height.
        A clipped panel left all eight links keyboard-focusable while invisible.
        The open/close animation lives on the inner wrapper so it survives this.
      */}
      <div
        className="mobile-navigation"
        hidden={!menuOpen}
        id="mobile-navigation-panel"
        ref={panelRef}
      >
        <div className="container mobile-navigation-inner">
          <nav aria-label="Mobile navigation">
            {navigation.map((item) => (
              <NavLink className={navClass} end={item.to === '/'} key={item.to} onClick={closeMenu} to={item.to}>
                {item.label}
                <Icon name="arrowUpRight" size={15} />
              </NavLink>
            ))}
          </nav>
          <div className="mobile-navigation-actions">
            {isAuthenticated ? (
              <>
                <NavLink className="button button-secondary" onClick={closeMenu} to="/dashboard">Dashboard</NavLink>
                {isAdmin ? (
                  <NavLink className="button button-secondary" onClick={closeMenu} to="/admin">Admin</NavLink>
                ) : null}
                <button className="button button-primary" onClick={handleLogout} type="button">Log out</button>
              </>
            ) : (
              <>
                <NavLink className="button button-secondary" onClick={closeMenu} to="/login">Login</NavLink>
                <Link className="button button-primary" onClick={closeMenu} to="/register">Get started <Icon name="arrowRight" size={16} /></Link>
              </>
            )}
          </div>
        </div>
      </div>
    </header>
  )
}
