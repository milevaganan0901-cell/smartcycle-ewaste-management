import { Link } from 'react-router-dom'

import DemoNotice from '../components/DemoNotice.jsx'
import Icon from '../components/Icon.jsx'
import SectionHeading from '../components/SectionHeading.jsx'
import TrackingTimeline from '../components/TrackingTimeline.jsx'
import {
  acceptedDevices,
  howItWorksSteps,
  journeyStages,
  sampleTrackingSteps,
  valuationFactors,
} from '../data/demoData.js'

/**
 * Stage 4C: this replaces a block of invented platform statistics
 * ("12,480 devices processed"). Every entry describes a capability the
 * application actually implements, so the section carries no fabricated numbers.
 */
const whyItMatters = [
  {
    icon: 'clipboard',
    title: 'Instant estimate',
    description: 'Submit a device and get an estimated value straight away, with refurbishment and recycling figures alongside it.',
  },
  {
    icon: 'route',
    title: 'Trackable journey',
    description: 'Every device gets a tracking ID. Follow its current status at any time, without needing an account.',
  },
  {
    icon: 'truck',
    title: 'Doorstep pickup',
    description: 'Request collection for a device you have submitted, and follow the request status to completion.',
  },
  {
    icon: 'layers',
    title: 'Two real outcomes',
    description: 'Devices are routed to refurbishment or recycling. Both are genuine end states, not a recycling-only claim.',
  },
]

function DeviceIllustration() {
  return (
    <div className="hero-visual" aria-label="Illustration of electronics ready for a second life">
      <div className="hero-visual-grid" aria-hidden="true" />
      <div className="visual-orb visual-orb-one" aria-hidden="true" />
      <div className="visual-orb visual-orb-two" aria-hidden="true" />
      <div className="visual-device visual-phone" aria-hidden="true">
        <Icon name="smartphone" size={31} />
        <span>13</span>
      </div>
      <div className="visual-device visual-laptop" aria-hidden="true">
        <Icon name="laptop" size={50} />
        <span>Air</span>
      </div>
      <div className="visual-device visual-tablet" aria-hidden="true">
        <Icon name="tablet" size={28} />
        <span>Tab</span>
      </div>
      <div className="visual-leaf" aria-hidden="true"><Icon name="leaf" size={37} /></div>
      <div className="visual-caption"><Icon name="spark" size={15} /> Better outcomes start here</div>
    </div>
  )
}

export default function HomePage() {
  return (
    <>
      <section className="home-hero">
        <div className="container hero-layout">
          <div className="hero-copy">
            <p className="eyebrow">A cleaner path for every device</p>
            <h1>Give your old electronics a <span>second life.</span></h1>
            <p className="hero-description">
              Sell your unused electronics responsibly. Get an estimated value, schedule collection, and track your device through refurbishment or recycling.
            </p>
            <div className="hero-actions">
              <Link className="button button-primary" to="/sell">Sell Your Device <Icon name="arrowRight" size={17} /></Link>
              <Link className="button button-secondary" to="/track">Track My Device <Icon name="search" size={17} /></Link>
            </div>
            <div className="hero-assurance"><Icon name="shield" size={17} /> Responsible handling, clearly explained</div>
          </div>
          <DeviceIllustration />
        </div>
      </section>

      <section className="section section-stats" aria-labelledby="home-why-title">
        <div className="container">
          <div className="stats-heading-row">
            <SectionHeading
              description="SmartCycle is a working demonstration. Everything below is something the application genuinely does today, using your own device records rather than invented impact figures."
              eyebrow="A clearer view of circular electronics"
              title="A better system starts with visibility."
            />
          </div>
          <ul className="metrics-grid capability-grid" id="home-why-title">
            {whyItMatters.map((item) => (
              <li className="metric-card capability-card" key={item.title}>
                <span className="metric-icon"><Icon name={item.icon} size={20} /></span>
                <strong>{item.title}</strong>
                <span className="metric-label">{item.description}</span>
              </li>
            ))}
          </ul>
          <DemoNotice>SmartCycle is a demonstration project, so it publishes no aggregate impact figures. Each estimate you receive is calculated from your own device details.</DemoNotice>
        </div>
      </section>

      <section className="section section-tint" id="how-it-works" aria-labelledby="home-how-title">
        <div className="container">
          <SectionHeading
            align="center"
            eyebrow="How it works"
            title="From unused device to responsible outcome."
            description="A simple, transparent journey designed to make the next step feel easy."
          />
          <div className="process-grid">
            {howItWorksSteps.map((step) => (
              <article className="process-card" key={step.number}>
                <div className="process-card-top"><span className="process-number">{step.number}</span><span className="icon-box"><Icon name={step.icon} size={21} /></span></div>
                <h3>{step.title}</h3>
                <p>{step.description}</p>
              </article>
            ))}
          </div>
          <div className="center-action"><Link className="text-link" to="/how-it-works">See the complete process <Icon name="arrowRight" size={16} /></Link></div>
        </div>
      </section>

      <section className="section" aria-labelledby="accepted-title">
        <div className="container split-heading-row">
          <SectionHeading
            eyebrow="What we accept"
            title="Your old tech has value beyond the drawer."
            description="Start with the device you want to move on. If it is not listed, our team can help you check the next step."
          />
          <div className="accepted-contact"><Icon name="message" size={18} /><span>Not sure where to start?</span><Link to="/contact">Talk to us <Icon name="arrowUpRight" size={15} /></Link></div>
        </div>
        <div className="accepted-grid">
          {acceptedDevices.map((device) => (
            <article className="accepted-card" key={device.label}>
              <span className="icon-box icon-box-soft"><Icon name={device.icon} size={25} /></span>
              <h3>{device.label}</h3>
              <p>{device.note}</p>
              <Link aria-label={`Learn more about ${device.label}`} to="/sell"><Icon name="arrowUpRight" size={16} /></Link>
            </article>
          ))}
        </div>
        <div className="center-action"><Link className="button button-secondary" to="/contact">Don't see your device? Contact us <Icon name="arrowRight" size={16} /></Link></div>
      </section>

      <section className="section section-journey" aria-labelledby="journey-title">
        <div className="container">
          <SectionHeading
            align="center"
            eyebrow="Device journey"
            title="Every device follows a clear path."
            description="The final outcome is determined after inspection, with the reason and next step recorded along the way."
          />
          <div className="journey-track">
            {journeyStages.map((stage, index) => (
              <div className="journey-stage" key={stage.label}>
                <div className="journey-icon"><Icon name={stage.icon} size={23} /></div>
                <span>{stage.label}</span>
                {index < journeyStages.length - 1 ? <Icon className="journey-arrow" name="arrowRight" size={18} /> : null}
              </div>
            ))}
            <div className="journey-split" aria-hidden="true"><span /></div>
            <div className="journey-outcomes">
              <div className="journey-outcome journey-outcome-refurbish"><span className="icon-box"><Icon name="refresh" size={21} /></span><strong>Refurbish</strong><small>Second life</small></div>
              <div className="journey-outcome journey-outcome-recycle"><span className="icon-box"><Icon name="recycle" size={21} /></span><strong>Recycle</strong><small>Material recovery</small></div>
            </div>
          </div>
        </div>
      </section>

      <section className="section section-valuation" aria-labelledby="valuation-title">
        <div className="container valuation-layout">
          <div className="valuation-visual">
            <div className="valuation-orbit valuation-orbit-a" aria-hidden="true" />
            <div className="valuation-orbit valuation-orbit-b" aria-hidden="true" />
            <div className="valuation-device-card"><Icon name="smartphone" size={42} /><span>iPhone 13</span><strong>Good condition</strong></div>
            <div className="valuation-tag"><Icon name="tag" size={18} /><span>Demo estimate</span><strong>₹28,000</strong></div>
          </div>
          <div className="valuation-copy">
            <SectionHeading
              eyebrow="Estimated value"
              title="Know Your Device's Estimated Value"
              description="A useful starting point helps you decide what happens next. The future SmartCycle valuation service can consider:"
            />
            <div className="factor-grid">
              {valuationFactors.map((factor) => <div className="factor-item" key={factor.title}><span className="factor-icon"><Icon name={factor.icon} size={17} /></span><span><strong>{factor.title}</strong><small>{factor.description}</small></span></div>)}
            </div>
            <DemoNotice>Demo estimate only — actual valuation will be calculated by the backend in a future stage.</DemoNotice>
            <Link className="button button-primary" to="/sell">Check Estimated Value <Icon name="arrowRight" size={17} /></Link>
          </div>
        </div>
      </section>

      <section className="section section-impact" aria-labelledby="impact-title">
        <div className="container">
          <div className="impact-header">
            <SectionHeading
              description="SmartCycle is designed to make the path from collection to outcome easier to see. The points below describe the real outcomes the lifecycle supports, rather than publishing impact figures this demonstration has not earned."
              eyebrow="Environmental impact"
              title="More visibility. More responsible choices."
            />
          </div>
          <div className="impact-grid">
            <div className="impact-card"><Icon name="shield" size={24} /><strong>Tracked, not lost</strong><span>Every submission carries a tracking ID and a recorded status, so a device does not simply disappear from view.</span></div>
            <div className="impact-card"><Icon name="refresh" size={24} /><strong>Refurbishment is a real outcome</strong><span>Devices that still work can be routed to Refurbishment, which keeps working hardware in use.</span></div>
            <div className="impact-card"><Icon name="recycle" size={24} /><strong>Recycling is a real outcome</strong><span>Devices that do not work can be routed to Recycling, so materials are recovered rather than discarded.</span></div>
          </div>
        </div>
      </section>

      <section className="section section-tracking-preview" aria-labelledby="tracking-preview-title">
        <div className="container tracking-preview-layout">
          <div className="tracking-preview-copy">
            <SectionHeading
              eyebrow="Tracking preview"
              title="Know Where Your Device Is"
              description="A tracking ID gives every submission a shared point of reference—from pickup request to final outcome."
            />
            <form className="tracking-form" onSubmit={(event) => event.preventDefault()}>
              <label htmlFor="home-tracking-id">Enter your tracking ID</label>
              <div className="tracking-input-row">
                <input aria-describedby="home-tracking-help" defaultValue="EW-2026-0001" id="home-tracking-id" />
                <button className="button button-primary" type="submit">Track Device <Icon name="arrowRight" size={16} /></button>
              </div>
              <small id="home-tracking-help">Try the sample ID to preview the experience.</small>
            </form>
            <DemoNotice>Sample tracking data for demonstration purposes.</DemoNotice>
            <Link className="text-link" to="/track">Open the full tracking page <Icon name="arrowRight" size={16} /></Link>
          </div>
          <div className="tracking-preview-card">
            <div className="tracking-card-header"><div><span className="tracking-id-label">Tracking ID</span><strong>EW-2026-0001</strong></div><StatusBadgeLike /></div>
            <TrackingTimeline compact steps={sampleTrackingSteps} />
          </div>
        </div>
      </section>

      <section className="section section-cta" aria-labelledby="cta-title">
        <div className="container cta-card">
          <div className="cta-copy"><p className="eyebrow">Ready when you are</p><h2 id="cta-title">Ready to give your electronics a second life?</h2><p>Start with a device, understand its possible value, and choose a clearer next step.</p></div>
          <div className="cta-actions"><Link className="button button-light" to="/sell">Sell Your Device <Icon name="arrowRight" size={17} /></Link><Link className="button button-outline-light" to="/how-it-works">Learn How It Works</Link></div>
        </div>
      </section>
    </>
  )
}

function StatusBadgeLike() {
  return <span className="status-badge status-inspection">Current</span>
}
