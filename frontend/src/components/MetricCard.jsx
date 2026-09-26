import Icon from './Icon.jsx'

export default function MetricCard({ icon, value, label, note, tone = 'default' }) {
  return (
    <article className={`metric-card metric-card-${tone}`}>
      <span className="metric-icon"><Icon name={icon} size={20} /></span>
      <strong>{value}</strong>
      <span className="metric-label">{label}</span>
      {note ? <small>{note}</small> : null}
    </article>
  )
}
