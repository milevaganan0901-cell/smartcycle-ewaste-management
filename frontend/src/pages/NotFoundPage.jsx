import { Link } from 'react-router-dom'

import Icon from '../components/Icon.jsx'

export default function NotFoundPage() {
  return (
    <section className="not-found-page section"><div className="container not-found-card"><span className="not-found-icon"><Icon name="search" size={30} /></span><p className="eyebrow">Page not found</p><h1>That route has not been mapped yet.</h1><p>Return to the SmartCycle home page or explore the device journey.</p><div className="hero-actions"><Link className="button button-primary" to="/">Back to home <Icon name="arrowRight" size={17} /></Link><Link className="button button-secondary" to="/how-it-works">How it works</Link></div></div></section>
  )
}
