import { Link } from 'react-router-dom'

import DemoNotice from '../components/DemoNotice.jsx'
import Icon from '../components/Icon.jsx'
import SectionHeading from '../components/SectionHeading.jsx'
import { howItWorksSteps, journeyStages, valuationFactors } from '../data/demoData.js'

export default function HowItWorksPage() {
  return (
    <>
      <section className="page-hero page-hero-how">
        <div className="container page-hero-inner">
          <div>
            <p className="eyebrow">How it works</p>
            <h1>Make the next step easier to understand.</h1>
            <p>SmartCycle gives every device a clear path from submission to the outcome that fits it best.</p>
          </div>
          <div className="page-hero-side-note"><Icon name="route" size={21} /><span><strong>One connected journey.</strong><small>Submission → valuation → pickup → processing.</small></span></div>
        </div>
      </section>

      <section className="section">
        <div className="container">
          <SectionHeading align="center" eyebrow="The SmartCycle method" title="Five simple steps. One responsible outcome." description="The future platform will guide users through each step while keeping the status and reasoning visible." />
          <div className="process-page-grid">
            {howItWorksSteps.map((step, index) => (
              <article className="process-page-card" key={step.number}>
                <div className="process-page-number">{step.number}</div>
                <span className="icon-box"><Icon name={step.icon} size={24} /></span>
                <h2>{step.title}</h2>
                <p>{step.description}</p>
                {index < howItWorksSteps.length - 1 ? <span className="process-connector" aria-hidden="true"><Icon name="arrowRight" size={17} /></span> : null}
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="section section-tint">
        <div className="container">
          <SectionHeading eyebrow="The journey" title="A decision point, not a black box." description="After inspection, each device can move toward the outcome that makes the most sense." />
          <div className="journey-page-card">
            <div className="journey-page-row">
              {journeyStages.map((stage, index) => <div className="journey-page-stage" key={stage.label}><span className="icon-box"><Icon name={stage.icon} size={21} /></span><strong>{stage.label}</strong>{index < journeyStages.length - 1 ? <Icon className="journey-arrow" name="arrowRight" size={18} /> : null}</div>)}
            </div>
            <div className="journey-page-branch"><span /><div className="branch-line" /><div className="branch-outcomes"><div><span className="icon-box icon-box-refurbish"><Icon name="refresh" size={22} /></span><strong>Refurbish</strong><small>Prepare for another user.</small></div><div><span className="icon-box icon-box-recycle"><Icon name="recycle" size={22} /></span><strong>Recycle</strong><small>Recover materials responsibly.</small></div></div></div>
          </div>
        </div>
      </section>

      <section className="section">
        <div className="container process-principles-layout">
          <div><SectionHeading eyebrow="What informs the estimate" title="Value starts with context." description="A future valuation service can use a small set of understandable factors instead of a black-box number." /></div>
          <div className="principle-list">{valuationFactors.map((factor) => <div className="principle-item" key={factor.title}><span className="factor-icon"><Icon name={factor.icon} size={18} /></span><div><strong>{factor.title}</strong><p>{factor.description}</p></div></div>)}</div>
        </div>
      </section>

      <section className="section section-cta section-cta-short">
        <div className="container cta-card"><div className="cta-copy"><p className="eyebrow">See it in action</p><h2>Have a device in mind?</h2><p>Start with a demo submission and explore the future experience.</p></div><div className="cta-actions"><Link className="button button-light" to="/sell">Sell Your Device <Icon name="arrowRight" size={17} /></Link><Link className="button button-outline-light" to="/track">Track a sample</Link></div></div>
      </section>

      <div className="container page-bottom-note"><DemoNotice>How-it-works content is a product concept for the frontend stage. Processing rules will be defined by the backend later.</DemoNotice></div>
    </>
  )
}
