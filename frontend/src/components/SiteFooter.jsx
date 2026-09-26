import { Link } from 'react-router-dom'

import Icon from './Icon.jsx'

const platformLinks = [
  { label: 'Sell device', to: '/sell' },
  { label: 'Track device', to: '/track' },
  { label: 'How it works', to: '/how-it-works' },
]

const companyLinks = [
  { label: 'About', to: '/about' },
  { label: 'Contact', to: '/contact' },
]

export default function SiteFooter() {
  return (
    <footer className="site-footer">
      <div className="container footer-main">
        <div className="footer-brand-column">
          <Link className="brand footer-brand" to="/">
            <span className="brand-mark" aria-hidden="true"><Icon name="recycle" size={23} /></span>
            <span className="brand-copy">
              <strong>SmartCycle</strong>
              <small>Give your old electronics a second life.</small>
            </span>
          </Link>
          <p>Making responsible electronics collection, refurbishment and recycling easier to understand.</p>
          <div className="social-row" aria-label="Social media placeholders">
            <span className="social-placeholder" title="LinkedIn placeholder"><Icon name="linkedin" size={17} /></span>
            <span className="social-placeholder" title="X placeholder"><Icon name="twitter" size={17} /></span>
            <span className="social-placeholder" title="Instagram placeholder"><Icon name="instagram" size={17} /></span>
          </div>
        </div>

        <div className="footer-links-column">
          <p className="footer-label">Platform</p>
          {platformLinks.map((link) => <Link key={link.to} to={link.to}>{link.label}</Link>)}
        </div>

        <div className="footer-links-column">
          <p className="footer-label">Company</p>
          {companyLinks.map((link) => <Link key={link.to} to={link.to}>{link.label}</Link>)}
        </div>

        <div className="footer-note-column">
          <p className="footer-label">Built for better outcomes</p>
          <p>Every device has a next chapter. We help make that chapter visible, responsible and easier to choose.</p>
          <span className="demo-chip"><span className="demo-chip-dot" /> Demo experience</span>
        </div>
      </div>
      <div className="container footer-bottom">
        <span>© 2026 SmartCycle. All rights reserved.</span>
        <span>Made for a more circular future.</span>
      </div>
    </footer>
  )
}
