import Icon from './Icon.jsx'

export default function DemoNotice({ children, tone = 'teal', icon = 'info' }) {
  return (
    <div className={`demo-notice demo-notice-${tone}`} role="note">
      <Icon name={icon} size={17} />
      <span>{children}</span>
    </div>
  )
}
