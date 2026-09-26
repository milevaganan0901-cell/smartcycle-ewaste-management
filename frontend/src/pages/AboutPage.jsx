import { Link } from 'react-router-dom'

import DemoNotice from '../components/DemoNotice.jsx'
import Icon from '../components/Icon.jsx'
import SectionHeading from '../components/SectionHeading.jsx'

const principles = [
  { icon: 'eye', title: 'Transparency', description: 'Make status, reasoning and next steps visible.' },
  { icon: 'heart', title: 'Responsibility', description: 'Treat every device as a resource with a next chapter.' },
  { icon: 'users', title: 'Accessibility', description: 'Make responsible choices feel clear and achievable.' },
]

export default function AboutPage() {
  return (
    <>
      <section className="page-hero page-hero-about">
        <div className="container page-hero-inner">
          <div><p className="eyebrow">About SmartCycle</p><h1>Better choices for the devices we no longer use.</h1><p>SmartCycle is a product concept for making responsible electronics handling simpler, more visible and easier to trust.</p></div>
          <div className="page-hero-side-note"><Icon name="leaf" size={21} /><span><strong>Our north star</strong><small>Make the responsible choice the easier choice.</small></span></div>
        </div>
      </section>

      <section className="section about-story-section"><div className="container about-story-grid"><div className="about-story-visual"><div className="about-circle about-circle-large" /><div className="about-circle about-circle-small" /><div className="about-story-device"><Icon name="recycle" size={64} /></div><span className="about-visual-label">A circular future</span></div><div className="about-story-copy"><SectionHeading eyebrow="The problem" title="Electronics should not disappear into a drawer." description="Old devices are often kept long after they stop being useful, discarded without clarity, or handled without a visible record of what happens next." /><div className="about-list"><div><span className="icon-box"><Icon name="alert" size={19} /></span><p><strong>Unclear value</strong> Users do not know what an old device may be worth.</p></div><div><span className="icon-box"><Icon name="globe" size={19} /></span><p><strong>Unclear outcomes</strong> The path from collection to processing is often invisible.</p></div><div><span className="icon-box"><Icon name="users" size={19} /></span><p><strong>Uneven access</strong> Responsible disposal can feel complicated and time-consuming.</p></div></div></div></div></section>

      <section className="section section-tint"><div className="container solution-layout"><div className="solution-copy"><SectionHeading eyebrow="Our solution" title="Connect the decision to the journey." description="SmartCycle brings submission, value, collection and processing into one understandable product experience." /><Link className="button button-primary" to="/sell">Explore the demo <Icon name="arrowRight" size={17} /></Link></div><div className="solution-flow"><div className="solution-flow-step"><span>01</span><div><strong>Submit</strong><small>Share device details.</small></div></div><div className="solution-flow-line" /><div className="solution-flow-step"><span>02</span><div><strong>Valuation</strong><small>Understand possible value.</small></div></div><div className="solution-flow-line" /><div className="solution-flow-step"><span>03</span><div><strong>Pickup</strong><small>Arrange collection.</small></div></div><div className="solution-flow-line" /><div className="solution-flow-step"><span>04</span><div><strong>Process</strong><small>See the outcome.</small></div></div></div></div></section>

      <section className="section"><div className="container"><SectionHeading align="center" eyebrow="Our process" title="Simple on the surface. Thoughtful underneath." description="The product is designed around a simple promise: users should know what happens next." /><div className="about-process-grid"><div><span className="process-number-large">01</span><h3>Submission</h3><p>Capture the device details that matter.</p></div><div><span className="process-number-large">02</span><h3>Valuation</h3><p>Offer a transparent starting point.</p></div><div><span className="process-number-large">03</span><h3>Pickup</h3><p>Make collection easy to arrange.</p></div><div><span className="process-number-large">04</span><h3>Inspection</h3><p>Confirm condition and functionality.</p></div><div><span className="process-number-large">05</span><h3>Processing</h3><p>Route to refurbish or recycle.</p></div></div></div></section>

      <section className="section section-mission"><div className="container mission-layout"><div className="mission-mark"><Icon name="heart" size={45} /></div><div><p className="eyebrow">Our mission</p><h2>Make responsible electronics disposal simpler and more transparent.</h2><p>We believe better information can lead to better outcomes—for users, for collection partners and for the materials that still have value.</p><Link className="text-link" to="/contact">Start a conversation <Icon name="arrowRight" size={16} /></Link></div></div></section>

      <section className="section section-cta section-cta-short"><div className="container cta-card"><div className="cta-copy"><p className="eyebrow">The next chapter</p><h2>Every device deserves a thoughtful next step.</h2><p>See how SmartCycle could make that step clearer.</p></div><div className="cta-actions"><Link className="button button-light" to="/sell">Sell Your Device <Icon name="arrowRight" size={17} /></Link><Link className="button button-outline-light" to="/how-it-works">How It Works</Link></div></div></section>

      <div className="container page-bottom-note"><DemoNotice>SmartCycle is currently a frontend product concept. Mission language and workflows will be refined with real user and partner feedback.</DemoNotice></div>
    </>
  )
}
