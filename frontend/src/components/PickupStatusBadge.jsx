/**
 * Pickup request status pill.
 *
 * The keys are exactly the backend's `ALLOWED_PICKUP_STATUSES` tuple. The label
 * is always rendered as text and paired with a glyph, so status never depends on
 * colour alone.
 */
const PICKUP_STATUS_STYLES = {
  Requested: 'status-requested',
  Scheduled: 'status-scheduled',
  Collected: 'status-collected',
  Cancelled: 'status-neutral',
}

const GLYPHS = {
  Requested: 'M12 6v6l4 2M12 3a9 9 0 1 1 0 18 9 9 0 0 1 0-18Z',
  Scheduled: 'M8 3v4M16 3v4M4 9h16M5 5h14a1 1 0 0 1 1 1v13a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1Z',
  Collected: 'M21 8 12 3 3 8v8l9 5 9-5Zm-18 0 9 5 9-5m-9 5v8',
  Cancelled: 'M12 3a9 9 0 1 1 0 18 9 9 0 0 1 0-18ZM9 9l6 6m0-6-6 6',
}

export default function PickupStatusBadge({ status, showIcon = true }) {
  const label = status || 'Unknown'
  const className = PICKUP_STATUS_STYLES[label] || 'status-neutral'
  const d = GLYPHS[label]

  return (
    <span className={`status-badge ${className}`}>
      {showIcon && d ? (
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
          <path d={d} />
        </svg>
      ) : null}
      {label}
    </span>
  )
}

export { PICKUP_STATUS_STYLES }
