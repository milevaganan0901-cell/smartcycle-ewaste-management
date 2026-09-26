/**
 * Device lifecycle status pill.
 *
 * The keys below are exactly the values in the backend's
 * `ALLOWED_DEVICE_STATUSES` tuple. Nothing is mapped that the API cannot
 * return, and anything unrecognised falls back to a neutral style rather than
 * being invented into a category.
 *
 * The status name is always rendered as text, and each state also carries a
 * glyph, so status is never communicated by colour alone.
 */
const DEVICE_STATUS_STYLES = {
  Submitted: { className: 'status-neutral', icon: 'file' },
  'Under Review': { className: 'status-inspection', icon: 'search' },
  'Pickup Scheduled': { className: 'status-scheduled', icon: 'calendar' },
  Collected: { className: 'status-collected', icon: 'box' },
  Inspection: { className: 'status-inspection', icon: 'search' },
  Refurbishment: { className: 'status-refurbishing', icon: 'refresh' },
  Recycling: { className: 'status-recycling', icon: 'recycle' },
  Completed: { className: 'status-completed', icon: 'checkCircle' },
}

const FALLBACK = { className: 'status-neutral', icon: 'info' }

export default function StatusBadge({ status, showIcon = true }) {
  const label = status || 'Unknown'
  const style = DEVICE_STATUS_STYLES[label] || FALLBACK

  return (
    <span className={`status-badge ${style.className}`}>
      {showIcon ? <StatusGlyph name={style.icon} /> : null}
      {label}
    </span>
  )
}

/**
 * A small inline glyph. Imported lazily through the Icon component at module
 * scope would create a cycle with Icon's own defaults, so the shapes are
 * inlined here and kept aria-hidden because the adjacent text already names
 * the status.
 */
function StatusGlyph({ name }) {
  const paths = {
    file: <><path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8Z" /><path d="M14 3v5h5" /></>,
    search: <><circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" /></>,
    calendar: <><rect x="3" y="5" width="18" height="16" rx="2" /><path d="M8 3v4M16 3v4M3 10h18" /></>,
    box: <><path d="M21 8 12 3 3 8v8l9 5 9-5Z" /><path d="m3 8 9 5 9-5M12 13v8" /></>,
    refresh: <><path d="M20 11A8 8 0 0 0 6.3 6.3L4 8.5" /><path d="M4 4v4.5h4.5" /><path d="M4 13a8 8 0 0 0 13.7 4.7L20 15.5" /><path d="M20 20v-4.5h-4.5" /></>,
    recycle: <><path d="M7 19H5a2 2 0 0 1-1.7-3l1.4-2.4" /><path d="m8.5 5.6 1-1.7A2 2 0 0 1 11.2 3H14" /><path d="m17.5 9.5 1.6 2.8a2 2 0 0 1-1.7 3H15" /><path d="M7 19h5" /><path d="m10 5 2.5 4.3" /><path d="m14.5 11.5-2.6 4.5" /></>,
    checkCircle: <><circle cx="12" cy="12" r="9" /><path d="m8.5 12.2 2.4 2.4 4.6-5" /></>,
    info: <><circle cx="12" cy="12" r="9" /><path d="M12 11v5M12 8h.01" /></>,
  }

  return (
    <svg
      aria-hidden="true"
      className="status-badge-glyph"
      fill="none"
      focusable="false"
      height="12"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth="2"
      viewBox="0 0 24 24"
      width="12"
    >
      {paths[name] || paths.info}
    </svg>
  )
}

export { DEVICE_STATUS_STYLES }
