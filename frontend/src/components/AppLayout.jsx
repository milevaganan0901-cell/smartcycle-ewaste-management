import { useEffect } from 'react'
import { Outlet, useLocation } from 'react-router-dom'

import ChatWidget from './ChatWidget.jsx'
import SiteFooter from './SiteFooter.jsx'
import SiteHeader from './SiteHeader.jsx'

export default function AppLayout() {
  const { pathname } = useLocation()

  useEffect(() => {
    window.scrollTo({ top: 0, behavior: 'auto' })
  }, [pathname])

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">Skip to main content</a>
      <SiteHeader />
      <main id="main-content">
        <Outlet />
      </main>
      <SiteFooter />
      <ChatWidget />
    </div>
  )
}
