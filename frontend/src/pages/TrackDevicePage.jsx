import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

import { ApiError, getDeviceByTrackingId } from '../api/client.js'
import DemoNotice from '../components/DemoNotice.jsx'
import Icon from '../components/Icon.jsx'
import SectionHeading from '../components/SectionHeading.jsx'
import StatusBadge from '../components/StatusBadge.jsx'
import { demoTrackingId } from '../data/demoData.js'

const lifecycleStatuses = [
  'Submitted',
  'Under Review',
  'Pickup Scheduled',
  'Collected',
  'Inspection',
  'Refurbishment',
  'Recycling',
  'Completed',
]

const VALUATION_METHOD_LABELS = {
  ml: 'Machine Learning Estimate',
  rule_based: 'Rule-Based Estimate',
}

function valuationMethodLabel(method) {
  return VALUATION_METHOD_LABELS[method] || 'Rule-Based Estimate'
}

function formatCurrency(value) {
  return new Intl.NumberFormat('en-IN', {
    currency: 'INR',
    maximumFractionDigits: 0,
  }).format(value)
}

function formatDate(value) {
  if (!value) return 'Not available'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return 'Not available'

  return new Intl.DateTimeFormat('en-IN', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(date)
}

function validateTrackingId(value) {
  const normalizedId = value.trim().toUpperCase()
  if (!normalizedId) {
    return { normalizedId, error: 'Enter a tracking ID to continue.' }
  }
  if (normalizedId.length > 32) {
    return { normalizedId, error: 'Enter a valid tracking ID and try again.' }
  }
  return { normalizedId, error: '' }
}

function StatusGuide({ currentStatus }) {
  return (
    <section className="status-guide" aria-labelledby="status-guide-title">
      <div className="status-guide-heading">
        <div>
          <p className="eyebrow">Lifecycle status</p>
          <h3 id="status-guide-title">Current status</h3>
        </div>
        <StatusBadge status={currentStatus} />
      </div>
      <div className="status-guide-list" aria-label="Supported lifecycle statuses">
        {lifecycleStatuses.map((status) => (
          <span className={`status-guide-item ${status === currentStatus ? 'status-guide-item-current' : ''}`} key={status}>
            {status}
          </span>
        ))}
      </div>
      <small className="status-guide-note">The backend stores the current status; this list is a guide to the supported lifecycle values.</small>
    </section>
  )
}

function DeviceResult({ device }) {
  const details = [
    { label: 'Device category', value: device.device_category },
    { label: 'Brand', value: device.brand },
    { label: 'Model', value: device.model },
    { label: 'Age', value: `${device.age} years` },
    { label: 'Condition', value: device.condition },
    { label: 'Working status', value: device.working_status },
    { label: 'Physical damage', value: device.physical_damage || 'Not provided' },
    { label: 'Accessories', value: device.accessories || 'Not provided' },
    {
      label: 'Original purchase price',
      value: device.original_purchase_price === null ? 'Not provided' : formatCurrency(device.original_purchase_price),
    },
  ]

  return (
    <div className="tracking-result-card">
      <div className="tracking-result-header">
        <div>
          <span className="tracking-id-label">Tracking ID</span>
          <h2>{device.tracking_id}</h2>
          <p>{device.brand} {device.model} · {device.device_category}</p>
        </div>
        <StatusBadge status={device.status} />
      </div>

      <div className="tracking-result-meta">
        <span><Icon name="calendar" size={16} /> Submitted {formatDate(device.created_at)}</span>
        <span><Icon name="refresh" size={16} /> Updated {formatDate(device.updated_at)}</span>
        <span><Icon name="mapPin" size={16} /> {device.location}</span>
      </div>

      <div className="tracking-detail-grid">
        {details.map((detail) => (
          <div className="tracking-detail-item" key={detail.label}>
            <span>{detail.label}</span>
            <strong>{detail.value}</strong>
          </div>
        ))}
      </div>

      <div className="tracking-valuations">
        <p className="eyebrow">Rule-based/demo estimates</p>
        <div className="result-price-block"><span>Estimated purchase value</span><strong>{formatCurrency(device.estimated_purchase_value)}</strong></div>
        <div className="result-method-row"><span>Valuation method</span><strong>{valuationMethodLabel(device.valuation_method)}</strong></div>
        <div className="result-breakdown">
          <div><span>Potential refurbished value</span><strong>{formatCurrency(device.potential_refurbished_value)}</strong></div>
          <div><span>Potential recycled value</span><strong>{formatCurrency(device.potential_recycled_value)}</strong></div>
        </div>
        <DemoNotice>These values are demonstration estimates from the SmartCycle device record, not a guaranteed transaction price or a representation of live market prices.</DemoNotice>
      </div>

      <StatusGuide currentStatus={device.status} />

      <div className="tracking-help-card">
        <Icon name="message" size={19} />
        <p><strong>Need help with a device?</strong> Contact the SmartCycle team if you need help understanding the current record.</p>
        <Link to="/contact">Contact support <Icon name="arrowUpRight" size={15} /></Link>
      </div>
    </div>
  )
}

export default function TrackDevicePage() {
  const [searchParams] = useSearchParams()
  const requestedId = searchParams.get('id') || (searchParams.get('demo') ? demoTrackingId : '')
  const [trackingId, setTrackingId] = useState(requestedId)
  const [device, setDevice] = useState(null)
  const [error, setError] = useState('')
  const [errorType, setErrorType] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const lastAutoLookup = useRef('')

  const lookupDevice = useCallback(async (rawTrackingId) => {
    const { normalizedId, error: validationError } = validateTrackingId(rawTrackingId)
    setTrackingId(normalizedId)

    if (validationError) {
      setError(validationError)
      setErrorType('validation')
      setDevice(null)
      return
    }

    setError('')
    setErrorType('')
    setDevice(null)
    setIsLoading(true)

    try {
      const result = await getDeviceByTrackingId(normalizedId)
      setDevice(result)
    } catch (lookupError) {
      if (lookupError instanceof ApiError && lookupError.status === 404) {
        setError('Tracking ID not found. Please check the ID and try again.')
        setErrorType('not-found')
      } else if (lookupError instanceof ApiError && lookupError.isNetworkError) {
        setError('Unable to reach the server. Please make sure the backend is running.')
        setErrorType('network')
      } else {
        setError('Something went wrong, please try again.')
        setErrorType('server')
      }
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    const normalizedId = requestedId.trim().toUpperCase()
    if (normalizedId && lastAutoLookup.current !== normalizedId) {
      lastAutoLookup.current = normalizedId
      void lookupDevice(normalizedId)
    }
  }, [requestedId, lookupDevice])

  const handleInputChange = (event) => {
    setTrackingId(event.target.value)
    setError('')
    setErrorType('')
    setDevice(null)
  }

  const handleSubmit = (event) => {
    event.preventDefault()
    if (isLoading) return
    void lookupDevice(trackingId)
  }

  return (
    <>
      <section className="page-hero page-hero-track">
        <div className="container page-hero-inner">
          <div>
            <p className="eyebrow">Track device</p>
            <h1>Track Your Device</h1>
            <p>Use the unique tracking ID from your submission to see the current device record and status.</p>
          </div>
          <div className="page-hero-side-note"><Icon name="mapPin" size={21} /><span><strong>One ID. One clear record.</strong><small>The current status is read from the SmartCycle device API.</small></span></div>
        </div>
      </section>

      <section className="section tracking-page-section">
        <div className="container tracking-page-layout">
          <div className="tracking-search-card">
            <SectionHeading eyebrow="Find a submission" title="Enter your tracking ID" description="Use the ID created when you submitted the device." />
            <form className="tracking-form tracking-form-large" noValidate onSubmit={handleSubmit}>
              <label htmlFor="tracking-id">Tracking ID</label>
              <div className="tracking-input-row">
                <input aria-describedby={error ? 'tracking-error' : 'tracking-help'} disabled={isLoading} id="tracking-id" onChange={handleInputChange} placeholder={demoTrackingId} value={trackingId} />
                <button aria-busy={isLoading} className="button button-primary" disabled={isLoading} type="submit">
                  {isLoading ? 'Tracking…' : 'Track'}
                  <Icon name={isLoading ? 'refresh' : 'arrowRight'} size={17} />
                </button>
              </div>
              {error ? <div className="form-error-summary" id="tracking-error" role="alert"><Icon name="alert" size={18} /><span>{error}</span></div> : <small id="tracking-help">Tracking IDs look like EW-2026-0001.</small>}
            </form>
            <DemoNotice>Live lookup uses the device record stored by the SmartCycle API. Only the current backend status is shown.</DemoNotice>
          </div>

          {isLoading ? (
            <div aria-live="polite" className="tracking-empty-state tracking-feedback-state" role="status"><span className="empty-state-icon"><Icon name="refresh" size={28} /></span><h2>Looking up your device…</h2><p>Checking the current record and status.</p></div>
          ) : device ? (
            <DeviceResult device={device} />
          ) : error ? (
            <div aria-live="polite" className="tracking-empty-state tracking-feedback-state tracking-error-state" role="alert">
              <span className="empty-state-icon"><Icon name="alert" size={28} /></span>
              <h2>
                {errorType === 'not-found'
                  ? 'We could not find a device record.'
                  : errorType === 'network'
                    ? 'The server is unavailable.'
                    : 'Check your tracking ID and try again.'}
              </h2>
              <p>{error}</p>
            </div>
          ) : (
            <div className="tracking-empty-state"><span className="empty-state-icon"><Icon name="search" size={28} /></span><h2>Your device journey will appear here.</h2><p>Enter a tracking ID to see the current device record.</p></div>
          )}
        </div>
      </section>
    </>
  )
}
