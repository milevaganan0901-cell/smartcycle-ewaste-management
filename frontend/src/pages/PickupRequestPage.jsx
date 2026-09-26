import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'

import { ApiError, createPickupRequest, getMyDevices } from '../api/client.js'
import DemoNotice from '../components/DemoNotice.jsx'
import Icon from '../components/Icon.jsx'
import PickupStatusBadge from '../components/PickupStatusBadge.jsx'
import { useAuth } from '../context/AuthContext.jsx'

const timeSlots = [
  '9:00 AM – 12:00 PM',
  '12:00 PM – 3:00 PM',
  '3:00 PM – 6:00 PM',
]

const fieldLabels = {
  device_id: 'Device',
  pickup_address: 'Pickup address',
  preferred_date: 'Preferred pickup date',
  preferred_time_slot: 'Preferred time slot',
}

function toDateInputValue(date) {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function formatDate(value) {
  if (!value) return 'Not available'
  const date = new Date(`${value}T00:00:00`)
  if (Number.isNaN(date.getTime())) return 'Not available'
  return new Intl.DateTimeFormat('en-IN', { dateStyle: 'medium' }).format(date)
}

function mapBackendFieldErrors(body) {
  const detail = Array.isArray(body?.detail) ? body.detail : []
  const errors = {}

  detail.forEach((item) => {
    const location = Array.isArray(item.loc) ? item.loc : []
    const field = location[location.length - 1]
    if (!fieldLabels[field]) return

    errors[field] = item.msg === 'Field required'
      ? `${fieldLabels[field]} is required.`
      : String(item.msg).replace(/^Value error, /, '')
  })

  return errors
}

function FieldError({ field, errors }) {
  if (!errors[field]) return null
  return <small className="field-error" id={`${field}-error`}>{errors[field]}</small>
}

export default function PickupRequestPage() {
  const { user, token, logout } = useAuth()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const requestedDeviceId = searchParams.get('device')

  const [devices, setDevices] = useState(null)
  const [isLoadingDevices, setIsLoadingDevices] = useState(true)
  const [loadError, setLoadError] = useState('')
  const [form, setForm] = useState({
    device_id: '',
    pickup_address: '',
    preferred_date: '',
    preferred_time_slot: timeSlots[0],
  })
  const [fieldErrors, setFieldErrors] = useState({})
  const [submitError, setSubmitError] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [createdPickup, setCreatedPickup] = useState(null)

  const today = useMemo(() => toDateInputValue(new Date()), [])

  const handleUnauthorized = useCallback(() => {
    logout()
  }, [logout])

  useEffect(() => {
    if (!token) return undefined

    const controller = new AbortController()
    let isActive = true

    getMyDevices(token, { signal: controller.signal })
      .then((result) => {
        if (!isActive) return
        setDevices(result)
        setLoadError('')
      })
      .catch((error) => {
        if (!isActive || error.name === 'AbortError') return
        setDevices(null)

        if (error instanceof ApiError && error.status === 401) {
          handleUnauthorized()
          return
        }
        if (error instanceof ApiError && error.isNetworkError) {
          setLoadError('We could not reach SmartCycle right now. Please check your connection and try again.')
        } else {
          setLoadError('We could not load your devices. Please try again.')
        }
      })
      .finally(() => {
        if (isActive) setIsLoadingDevices(false)
      })

    return () => {
      isActive = false
      controller.abort()
    }
  }, [token, handleUnauthorized])

  // Preselect the device from the query string, but only if the server says it
  // belongs to this account. The option list can only ever contain own devices.
  useEffect(() => {
    if (!Array.isArray(devices) || devices.length === 0) return

    const requested = Number(requestedDeviceId)
    const isOwnDevice = devices.some((device) => device.id === requested)
    setForm((current) => ({
      ...current,
      device_id: isOwnDevice ? String(requested) : (current.device_id || String(devices[0].id)),
    }))
  }, [devices, requestedDeviceId])

  const updateField = (event) => {
    const { name, value } = event.target
    setForm((current) => ({ ...current, [name]: value }))
    setFieldErrors((current) => ({ ...current, [name]: '' }))
    setSubmitError('')
  }

  const validateForm = () => {
    const errors = {}

    if (!form.device_id) errors.device_id = 'Choose a device to collect.'
    if (form.pickup_address.trim().length < 5) {
      errors.pickup_address = 'Enter a full pickup address (at least 5 characters).'
    }
    if (!form.preferred_date) {
      errors.preferred_date = 'Choose a preferred pickup date.'
    } else if (form.preferred_date < today) {
      errors.preferred_date = 'Choose a pickup date that is today or later.'
    }
    if (!form.preferred_time_slot) {
      errors.preferred_time_slot = 'Choose a preferred time slot.'
    }

    return errors
  }

  const handleSubmit = async (event) => {
    event.preventDefault()

    const errors = validateForm()
    setFieldErrors(errors)
    if (Object.keys(errors).length > 0) return

    setIsSubmitting(true)
    setSubmitError('')

    try {
      const result = await createPickupRequest(token, {
        device_id: Number(form.device_id),
        pickup_address: form.pickup_address.trim(),
        preferred_date: form.preferred_date,
        preferred_time_slot: form.preferred_time_slot,
      })
      setCreatedPickup(result)
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        handleUnauthorized()
        return
      }

      const backendErrors = mapBackendFieldErrors(error.body)
      if (Object.keys(backendErrors).length > 0) {
        setFieldErrors(backendErrors)
        return
      }

      if (error instanceof ApiError && error.isNetworkError) {
        setSubmitError('We could not reach SmartCycle right now. Please check your connection and try again.')
        return
      }

      setSubmitError(error instanceof ApiError ? error.message : 'Something went wrong while saving your pickup request. Please try again.')
    } finally {
      setIsSubmitting(false)
    }
  }

  const selectedDevice = Array.isArray(devices)
    ? devices.find((device) => String(device.id) === form.device_id)
    : null

  if (createdPickup) {
    const createdDevice = Array.isArray(devices)
      ? devices.find((device) => device.id === createdPickup.device_id)
      : null

    return (
      <>
        <section className="page-hero page-hero-sell">
          <div className="container page-hero-inner">
            <div>
              <p className="eyebrow">Pickup requested</p>
              <h1>Your collection request is recorded.</h1>
              <p>The SmartCycle team will confirm the slot. You can see this request on your dashboard at any time.</p>
            </div>
            <div className="page-hero-side-note">
              <Icon name="checkCircle" size={21} />
              <span><strong>Request saved.</strong><small>Only your account can see this pickup request.</small></span>
            </div>
          </div>
        </section>

        <section className="section form-section">
          <div className="container form-layout">
            <div className="form-card">
              <div className="form-card-heading">
                <div><p className="eyebrow">Confirmation</p><h2>Pickup request #{createdPickup.id}</h2></div>
                <PickupStatusBadge status={createdPickup.status} />
              </div>

              <div className="result-device-row">
                <div>
                  <span>Device</span>
                  <strong>{createdDevice ? `${createdDevice.brand} ${createdDevice.model}` : `Device #${createdPickup.device_id}`}</strong>
                </div>
              </div>

              <div className="result-tracking-row">
                <div><span>Tracking ID</span><strong>{createdDevice ? createdDevice.tracking_id : 'Not available'}</strong></div>
                <Icon name="checkCircle" size={20} />
              </div>

              <div className="result-breakdown">
                <div><span>Pickup address</span><strong>{createdPickup.pickup_address}</strong></div>
                <div><span>Preferred date</span><strong>{formatDate(createdPickup.preferred_date)}</strong></div>
                <div><span>Preferred time slot</span><strong>{createdPickup.preferred_time_slot}</strong></div>
                <div><span>Current status</span><PickupStatusBadge status={createdPickup.status} /></div>
              </div>

              <div className="form-actions">
                <span className="form-required-note">You can follow this request from your dashboard.</span>
                <div className="result-actions">
                  <button className="button button-secondary" onClick={() => navigate('/dashboard')} type="button">Back to dashboard</button>
                  {createdDevice ? (
                    <Link className="button button-primary" to={`/track?id=${encodeURIComponent(createdDevice.tracking_id)}`}>Track device <Icon name="arrowRight" size={17} /></Link>
                  ) : null}
                </div>
              </div>
            </div>

            <aside className="result-column">
              <div className="side-tip">
                <Icon name="info" size={18} />
                <p><strong>What happens next?</strong> A collection slot is confirmed against your preferred date and time. The request stays on your dashboard until it moves through the pickup lifecycle.</p>
              </div>
              <div className="side-tip">
                <Icon name="shield" size={18} />
                <p><strong>Only your account can see this.</strong> Pickup requests are filtered on the server using your signed-in session.</p>
              </div>
            </aside>
          </div>
        </section>
      </>
    )
  }

  return (
    <>
      <section className="page-hero page-hero-sell">
        <div className="container page-hero-inner">
          <div>
            <p className="eyebrow">Request pickup</p>
            <h1>Arrange collection for one of your devices.</h1>
            <p>Choose a device you submitted, tell us where to collect it and pick a preferred time slot.</p>
          </div>
          <div className="page-hero-side-note">
            <Icon name="truck" size={21} />
            <span><strong>One request per device.</strong><small>You can request pickup again for a different device at any time.</small></span>
          </div>
        </div>
      </section>

      <section className="section form-section">
        <div className="container form-layout">
          <form className="form-card" noValidate onSubmit={handleSubmit}>
            <div className="form-card-heading">
              <div><p className="eyebrow">Pickup details</p><h2>Where and when should we collect it?</h2></div>
              <span className="form-step-label">Collection</span>
            </div>
            <DemoNotice>This form sends a real pickup request to the SmartCycle pickup API for a device on your account.</DemoNotice>

            {submitError ? (
              <div className="form-error-summary" role="alert">
                <Icon name="alert" size={18} />
                <span>{submitError}</span>
              </div>
            ) : null}

            <div className="form-grid">
              <label className="field">
                <span>Device</span>
                <select
                  aria-describedby={fieldErrors.device_id ? 'device_id-error' : undefined}
                  aria-invalid={Boolean(fieldErrors.device_id)}
                  disabled={isSubmitting || isLoadingDevices || !devices?.length}
                  name="device_id"
                  onChange={updateField}
                  value={form.device_id}
                >
                  {!devices?.length ? <option value="">No devices available</option> : null}
                  {devices?.map((device) => (
                    <option key={device.id} value={String(device.id)}>
                      {device.brand} {device.model} · {device.tracking_id}
                    </option>
                  ))}
                </select>
                <FieldError errors={fieldErrors} field="device_id" />
              </label>

              <label className="field">
                <span>Pickup address</span>
                <input
                  aria-describedby={fieldErrors.pickup_address ? 'pickup_address-error' : undefined}
                  aria-invalid={Boolean(fieldErrors.pickup_address)}
                  disabled={isSubmitting}
                  name="pickup_address"
                  onChange={updateField}
                  placeholder="Flat, street, area, city and PIN code"
                  value={form.pickup_address}
                />
                <FieldError errors={fieldErrors} field="pickup_address" />
              </label>

              <label className="field">
                <span>Preferred pickup date</span>
                <input
                  aria-describedby={fieldErrors.preferred_date ? 'preferred_date-error' : undefined}
                  aria-invalid={Boolean(fieldErrors.preferred_date)}
                  disabled={isSubmitting}
                  min={today}
                  name="preferred_date"
                  onChange={updateField}
                  type="date"
                  value={form.preferred_date}
                />
                <FieldError errors={fieldErrors} field="preferred_date" />
              </label>

              <label className="field">
                <span>Preferred time slot</span>
                <select
                  aria-describedby={fieldErrors.preferred_time_slot ? 'preferred_time_slot-error' : undefined}
                  aria-invalid={Boolean(fieldErrors.preferred_time_slot)}
                  disabled={isSubmitting}
                  name="preferred_time_slot"
                  onChange={updateField}
                  value={form.preferred_time_slot}
                >
                  {timeSlots.map((slot) => <option key={slot}>{slot}</option>)}
                </select>
                <FieldError errors={fieldErrors} field="preferred_time_slot" />
              </label>
            </div>

            <div className="form-actions">
              <span className="form-required-note"><span>*</span> Required fields are marked by the form labels</span>
              <button aria-busy={isSubmitting} className="button button-primary" disabled={isSubmitting || isLoadingDevices || !devices?.length} type="submit">
                {isSubmitting ? 'Saving request…' : 'Request pickup'}
                <Icon name={isSubmitting ? 'refresh' : 'arrowRight'} size={17} />
              </button>
            </div>
          </form>

          <aside className="result-column">
            <div className="result-card result-card-visible">
              <div className="result-card-header">
                <span className="icon-box"><Icon name="truck" size={21} /></span>
                <span className="result-badge">{selectedDevice ? 'Ready to request' : 'Select a device'}</span>
              </div>
              <p className="eyebrow">Selected device</p>
              <h2>{selectedDevice ? 'Check the details before we collect.' : 'No device selected yet.'}</h2>
              {selectedDevice ? (
                <>
                  <div className="result-device-row">
                    <div><span>Device</span><strong>{selectedDevice.brand} {selectedDevice.model}</strong></div>
                  </div>
                  <div className="result-tracking-row">
                    <div><span>Tracking ID</span><strong>{selectedDevice.tracking_id}</strong></div>
                    <Icon name="checkCircle" size={20} />
                  </div>
                  <div className="result-breakdown">
                    <div><span>Current status</span><span className="status-badge status-neutral">{selectedDevice.status}</span></div>
                    <div><span>Submitted on</span><strong>{formatDate(selectedDevice.created_at.slice(0, 10))}</strong></div>
                    <div><span>Location on record</span><strong>{selectedDevice.location}</strong></div>
                  </div>
                </>
              ) : (
                <div className="result-empty"><Icon name="spark" size={24} /><p>Devices you submitted while logged in appear here, and only those can be scheduled for pickup.</p></div>
              )}
            </div>

            <div className="side-tip">
              <Icon name="info" size={18} />
              <p><strong>Contact details</strong> We use the email on your account ({user?.email || 'your account email'}) for this request, so you do not need to enter it again.</p>
            </div>

            {loadError ? (
              <div className="form-error-summary" role="alert">
                <Icon name="alert" size={18} />
                <span>{loadError}</span>
              </div>
            ) : null}

            {!loadError && Array.isArray(devices) && devices.length === 0 ? (
              <div className="side-tip">
                <Icon name="info" size={18} />
                <p><strong>No devices yet.</strong> Submit a device first, then return here to request pickup. <Link className="text-link" to="/sell">Sell a device <Icon name="arrowRight" size={15} /></Link></p>
              </div>
            ) : null}

            <div className="side-tip">
              <Icon name="shield" size={18} />
              <p><strong>Your devices only.</strong> The device list and every pickup request are filtered on the server using your signed-in session.</p>
            </div>
          </aside>
        </div>
      </section>
    </>
  )
}
