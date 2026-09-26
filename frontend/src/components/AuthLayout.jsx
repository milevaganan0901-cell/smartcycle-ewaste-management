import { Link } from 'react-router-dom'

import Icon from './Icon.jsx'

export default function AuthLayout({ eyebrow, title, description, children, footerText, footerLink, footerTo }) {
  return (
    <section className="auth-page">
      <div className="container auth-layout">
        <div className="auth-story-panel"><Link className="brand auth-brand" to="/"><span className="brand-mark" aria-hidden="true"><Icon name="recycle" size={23} /></span><span className="brand-copy"><strong>SmartCycle</strong><small>Give your old electronics a second life.</small></span></Link><div className="auth-story-content"><span className="auth-story-icon"><Icon name="leaf" size={26} /></span><p className="eyebrow">A better device journey</p><h1>Make responsible choices easier to see.</h1><p>SmartCycle is being designed to connect people, devices and outcomes in one clear experience.</p></div><div className="auth-story-footer"><span><Icon name="shield" size={15} /> Built around transparency</span><span><Icon name="recycle" size={15} /> Circular by design</span></div></div>
        <div className="auth-form-panel"><div className="auth-form-card"><p className="eyebrow">{eyebrow}</p><h2>{title}</h2><p className="auth-form-description">{description}</p>{children}<p className="auth-footer-copy">{footerText} <Link to={footerTo}>{footerLink}</Link></p></div></div>
      </div>
    </section>
  )
}
