import Icon from './Icon.jsx'

function statusIcon(state, index) {
  if (state === 'complete') return <Icon name="check" size={15} />
  if (state === 'current') return <span className="timeline-current-dot" />
  return <span className="timeline-pending-dot">{index + 1}</span>
}

export default function TrackingTimeline({ steps, compact = false }) {
  return (
    <ol className={`tracking-timeline ${compact ? 'tracking-timeline-compact' : ''}`}>
      {steps.map((step, index) => (
        <li className={`tracking-step tracking-step-${step.state}`} key={step.title}>
          <div className="tracking-marker" aria-hidden="true">
            {statusIcon(step.state, index)}
          </div>
          <div className="tracking-step-copy">
            <div className="tracking-step-title-row">
              <h3>{step.title}</h3>
              <span className="tracking-step-date">{step.date}</span>
            </div>
            <p>{step.description}</p>
          </div>
        </li>
      ))}
    </ol>
  )
}
