import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { ApiError, getMyDevices, getMyPickups } from '../api/client.js'
import Icon from '../components/Icon.jsx'
import MetricCard from '../components/MetricCard.jsx'
import PickupStatusBadge from '../components/PickupStatusBadge.jsx'
import StatusBadge from '../components/StatusBadge.jsx'
import { useAuth } from '../context/AuthContext.jsx'

const COMPLETED_STATUS = 'Completed'
const CANCELLED_PICKUP_STATUS = 'Cancelled'

const currencyFormatter = new Intl.NumberFormat('en-IN', {
  style: 'currency',
  currency: 'INR',
  maximumFractionDigits: 0,
})

const dateFormatter = new Intl.DateTimeFormat('en-IN', {
  dateStyle: 'medium',
})

function formatCurrency(value) {
  if (typeof value !== 'number' || !Number.isFinite(value)) return 'Not available'
  return currencyFormatter.format(value)
}

function formatDate(value) {
  if (!value) return 'Not available'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return 'Not available'
  return dateFormatter.format(date)
}

function summarizeAddress(address, maxLength = 46) {
  if (typeof address !== 'string' || !address.trim()) return 'Not available'
  const normalized = address.trim()
  return normalized.length > maxLength
    ? `${normalized.slice(0, maxLength - 1)}…`
    : normalized
}

function deviceIconFor(category) {
  const normalized = (category || '').toLowerCase()
  if (normalized.includes('smartphone')) return 'smartphone'
  if (normalized.includes('laptop')) return 'laptop'
  if (normalized.includes('tablet')) return 'tablet'
  if (normalized.includes('monitor')) return 'monitor'
  if (normalized.includes('television')) return 'tv'
  if (normalized.includes('printer')) return 'printer'
  if (normalized.includes('desktop')) return 'desktop'
  if (normalized.includes('accessor')) return 'accessories'
  return 'package'
}

export default function DashboardPage() {
  const { user, token, logout } = useAuth()
  const navigate = useNavigate()
  const [devices, setDevices] = useState(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState('')
  const [errorType, setErrorType] = useState('')
  const [pickups, setPickups] = useState(null)
  const [isLoadingPickups, setIsLoadingPickups] = useState(true)
  const [pickupError, setPickupError] = useState('')

  const loadDevices = useCallback(async (activeToken) => {
    setIsLoading(true)
    setError('')
    setErrorType('')

    try {
      const result = await getMyDevices(activeToken)
      setDevices(result)
    } catch (loadError) {
      setDevices(null)

      // An expired or invalid token clears the existing Stage 3D auth state,
      // and the shared RequireAuth guard redirects to the login page.
      if (loadError instanceof ApiError && loadError.status === 401) {
        logout()
        return
      }

      if (loadError instanceof ApiError && loadError.isNetworkError) {
        setError('We could not reach SmartCycle right now. Please check your connection and try again.')
        setErrorType('network')
      } else {
        setError('Something went wrong while loading your dashboard. Please try again.')
        setErrorType('server')
      }
    } finally {
      setIsLoading(false)
    }
  }, [logout])

  useEffect(() => {
    if (!token) return undefined

    const controller = new AbortController()
    let isActive = true

    getMyDevices(token, { signal: controller.signal })
      .then((result) => {
        if (!isActive) return
        setDevices(result)
        setError('')
        setErrorType('')
      })
      .catch((loadError) => {
        if (!isActive || loadError.name === 'AbortError') return
        setDevices(null)

        if (loadError instanceof ApiError && loadError.status === 401) {
          logout()
          return
        }

        if (loadError instanceof ApiError && loadError.isNetworkError) {
          setError('We could not reach SmartCycle right now. Please check your connection and try again.')
          setErrorType('network')
        } else {
          setError('Something went wrong while loading your dashboard. Please try again.')
          setErrorType('server')
        }
      })
      .finally(() => {
        if (isActive) setIsLoading(false)
      })

    return () => {
      isActive = false
      controller.abort()
    }
  }, [token, logout])

  const loadPickups = useCallback(async (activeToken) => {
    setIsLoadingPickups(true)
    setPickupError('')

    try {
      setPickups(await getMyPickups(activeToken))
    } catch (pickupLoadError) {
      setPickups(null)

      if (pickupLoadError instanceof ApiError && pickupLoadError.status === 401) {
        logout()
        return
      }

      setPickupError(
        pickupLoadError instanceof ApiError && pickupLoadError.isNetworkError
          ? 'We could not reach SmartCycle right now, so pickup requests could not be loaded.'
          : 'Pickup requests could not be loaded right now. Please try again.',
      )
    } finally {
      setIsLoadingPickups(false)
    }
  }, [logout])

  useEffect(() => {
    if (!token) return undefined

    const controller = new AbortController()
    let isActive = true

    getMyPickups(token, { signal: controller.signal })
      .then((result) => {
        if (!isActive) return
        setPickups(result)
        setPickupError('')
      })
      .catch((pickupLoadError) => {
        if (!isActive || pickupLoadError.name === 'AbortError') return
        setPickups(null)

        if (pickupLoadError instanceof ApiError && pickupLoadError.status === 401) {
          logout()
          return
        }

        setPickupError(
          pickupLoadError instanceof ApiError && pickupLoadError.isNetworkError
            ? 'We could not reach SmartCycle right now, so pickup requests could not be loaded.'
            : 'Pickup requests could not be loaded right now. Please try again.',
        )
      })
      .finally(() => {
        if (isActive) setIsLoadingPickups(false)
      })

    return () => {
      isActive = false
      controller.abort()
    }
  }, [token, logout])

  // Index the real pickup records by device so each row can show its own
  // pickup status, and flag devices that already have an open request.
  const activePickupByDeviceId = useMemo(() => {
    const index = new Map()
    if (!Array.isArray(pickups)) return index

    pickups.forEach((pickup) => {
      if (pickup.status === CANCELLED_PICKUP_STATUS) return
      if (!index.has(pickup.device_id)) {
        index.set(pickup.device_id, pickup)
      }
    })
    return index
  }, [pickups])

  const deviceById = useMemo(() => {
    const index = new Map()
    if (!Array.isArray(devices)) return index

    devices.forEach((device) => index.set(device.id, device))
    return index
  }, [devices])

  const stats = useMemo(() => {
    const list = Array.isArray(devices) ? devices : []
    const completed = list.filter((device) => device.status === COMPLETED_STATUS)
    const totalValue = list.reduce(
      (sum, device) => sum + (device.estimated_purchase_value || 0),
      0,
    )

    return {
      total: list.length,
      active: list.length - completed.length,
      completed: completed.length,
      totalValue,
    }
  }, [devices])

  const handleLogout = () => {
    logout()
    navigate('/')
  }

  // Stats stay as placeholders while loading and after a failure, so a failed
  // request is never mistaken for "this account has no devices".
  const statsUnavailable = isLoading || Boolean(error)

  const firstName = (user?.name || '').trim().split(' ')[0]

  return (
    <section className="dashboard-page section">
      <div className="container">
        <div className="dashboard-header">
          <div>
            <p className="eyebrow">Your dashboard</p>
            <h1>{firstName ? `Welcome, ${firstName}` : 'Welcome'}</h1>
            <p>Keep an eye on your devices and the outcomes they reach.</p>
          </div>
          <div className="dashboard-header-actions">
            <Link className="button button-secondary" to="/track"><Icon name="search" size={16} /> Track a device</Link>
            <Link className="button button-primary" to="/sell"><Icon name="plus" size={16} /> Sell a device</Link>
          </div>
        </div>

        <div className="dashboard-profile">
          <div className="dashboard-profile-main">
            <span className="dashboard-profile-avatar" aria-hidden="true"><Icon name="user" size={22} /></span>
            <div>
              <strong>{user?.name || 'Your account'}</strong>
              <span><Icon name="mail" size={14} /> {user?.email || 'Not available'}</span>
            </div>
          </div>
          <div className="dashboard-profile-meta">
            <div><span>Member since</span><strong>{formatDate(user?.created_at)}</strong></div>
            <div><span>Account status</span><strong>{user ? 'Active' : 'Not available'}</strong></div>
            <button className="dashboard-logout" onClick={handleLogout} type="button"><Icon name="logout" size={16} /> Log out</button>
          </div>
        </div>

        <div className="metrics-grid dashboard-metrics">
          <MetricCard icon="package" label="Total devices" note="From your account" tone="dark" value={statsUnavailable ? '—' : String(stats.total)} />
          <MetricCard icon="truck" label="Active devices" note="Not yet completed" value={statsUnavailable ? '—' : String(stats.active)} />
          <MetricCard icon="checkCircle" label="Completed devices" note="Finished journey" value={statsUnavailable ? '—' : String(stats.completed)} />
          <MetricCard icon="tag" label="Total estimated value" note="Rule-based demo estimate" tone="accent" value={statsUnavailable ? '—' : formatCurrency(stats.totalValue)} />
        </div>

        <div className="dashboard-section-heading">
          <div><p className="eyebrow">Your activity</p><h2>My devices</h2></div>
          {devices && devices.length > 0 ? <Link className="text-link" to="/sell">Add another device <Icon name="arrowRight" size={15} /></Link> : null}
        </div>

        {isLoading ? (
          <div aria-live="polite" className="dashboard-empty-state" role="status">
            <span className="empty-state-icon"><Icon name="refresh" size={28} /></span>
            <h2>Loading your devices…</h2>
            <p>Fetching the devices linked to your account.</p>
          </div>
        ) : error ? (
          <div aria-live="polite" className="dashboard-empty-state dashboard-error-state" role="alert">
            <span className="empty-state-icon"><Icon name="alert" size={28} /></span>
            <h2>{errorType === 'network' ? 'SmartCycle is unavailable.' : 'We could not load your dashboard.'}</h2>
            <p>{error}</p>
            <button className="button button-primary" onClick={() => { loadDevices(token); loadPickups(token); }} type="button">Try again <Icon name="refresh" size={16} /></button>
          </div>
        ) : devices && devices.length > 0 ? (
          <div className="table-card">
            <div className="table-card-header">
              <span>Showing {devices.length} {devices.length === 1 ? 'device' : 'devices'} on your account</span>
              <Link className="text-link" to="/sell">Add another device <Icon name="arrowRight" size={15} /></Link>
            </div>
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Device</th>
                    <th>Tracking ID</th>
                    <th>Estimated value</th>
                    <th>Status</th>
                    <th>Pickup</th>
                    <th>Date</th>
                    <th><span className="sr-only">Actions</span></th>
                  </tr>
                </thead>
                <tbody>
                  {devices.map((device) => {
                    const activePickup = activePickupByDeviceId.get(device.id)
                    return (
                    <tr key={device.tracking_id}>
                      <td>
                        <div className="table-device">
                          <span className="table-device-icon"><Icon name={deviceIconFor(device.device_category)} size={18} /></span>
                          <strong>{device.brand} {device.model}</strong>
                          <small>{device.device_category}</small>
                        </div>
                      </td>
                      <td><span className="tracking-id-text">{device.tracking_id}</span></td>
                      <td><strong>{formatCurrency(device.estimated_purchase_value)}</strong></td>
                      <td><StatusBadge status={device.status} /></td>
                      <td>
                        {activePickup ? (
                          <div className="pickup-cell">
                            <PickupStatusBadge status={activePickup.status} />
                            <small>{formatDate(activePickup.preferred_date)}</small>
                            <small>{activePickup.preferred_time_slot}</small>
                          </div>
                        ) : isLoadingPickups ? (
                          <span className="pickup-cell-muted">Checking…</span>
                        ) : (
                          <span className="pickup-cell-muted">Not requested</span>
                        )}
                      </td>
                      <td>{formatDate(device.created_at)}</td>
                      <td>
                        <div className="table-actions">
                          <Link aria-label={`Track ${device.brand} ${device.model}`} className="icon-button" title="Track device" to={`/track?id=${encodeURIComponent(device.tracking_id)}`}>
                            <Icon name="arrowUpRight" size={17} />
                          </Link>
                          {!activePickup ? (
                            <Link aria-label={`Request pickup for ${device.brand} ${device.model}`} className="icon-button" title="Request pickup" to={`/dashboard/pickup?device=${encodeURIComponent(device.id)}`}>
                              <Icon name="truck" size={17} />
                            </Link>
                          ) : null}
                        </div>
                      </td>
                    </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </div>
        ) : (
          <div className="dashboard-empty-state">
            <span className="empty-state-icon"><Icon name="package" size={28} /></span>
            <h2>You haven't submitted any devices yet.</h2>
            <p>When you submit a device while logged in, it will appear here with its tracking ID and current status.</p>
            <Link className="button button-primary" to="/sell"><Icon name="plus" size={16} /> Sell Your Device</Link>
          </div>
        )}

        <div className="dashboard-section-heading dashboard-pickup-heading">
          <div><p className="eyebrow">Collection</p><h2>My pickup requests</h2></div>
          <Link className="text-link" to="/dashboard/pickup">Request another pickup <Icon name="arrowRight" size={15} /></Link>
        </div>

        {isLoadingPickups ? (
          <div aria-live="polite" className="dashboard-empty-state dashboard-empty-state-compact" role="status">
            <span className="empty-state-icon"><Icon name="refresh" size={26} /></span>
            <h2>Loading your pickup requests…</h2>
            <p>Checking the collection requests linked to your account.</p>
          </div>
        ) : pickupError ? (
          <div aria-live="polite" className="dashboard-empty-state dashboard-empty-state-compact dashboard-error-state" role="alert">
            <span className="empty-state-icon"><Icon name="alert" size={26} /></span>
            <h2>We could not load your pickup requests.</h2>
            <p>{pickupError}</p>
            <button className="button button-primary" onClick={() => loadPickups(token)} type="button">Try again <Icon name="refresh" size={16} /></button>
          </div>
        ) : Array.isArray(pickups) && pickups.length > 0 ? (
          <div className="table-card">
            <div className="table-card-header">
              <span>Showing {pickups.length} pickup {pickups.length === 1 ? 'request' : 'requests'} on your account</span>
            </div>
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Device</th>
                    <th>Pickup status</th>
                    <th>Preferred date</th>
                    <th>Time slot</th>
                    <th>Pickup address</th>
                    <th>Requested on</th>
                  </tr>
                </thead>
                <tbody>
                  {pickups.map((pickup) => {
                    const pickupDevice = deviceById.get(pickup.device_id)
                    return (
                      <tr key={pickup.id}>
                        <td>
                          <div className="table-device">
                            <span className="table-device-icon"><Icon name={deviceIconFor(pickupDevice?.device_category)} size={18} /></span>
                            <strong>{pickupDevice ? `${pickupDevice.brand} ${pickupDevice.model}` : `Device #${pickup.device_id}`}</strong>
                            {pickupDevice ? <small>{pickupDevice.tracking_id}</small> : null}
                          </div>
                        </td>
                        <td><PickupStatusBadge status={pickup.status} /></td>
                        <td>{formatDate(pickup.preferred_date)}</td>
                        <td>{pickup.preferred_time_slot}</td>
                        <td>{summarizeAddress(pickup.pickup_address)}</td>
                        <td>{formatDate(pickup.created_at)}</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </div>
        ) : (
          <div className="dashboard-empty-state dashboard-empty-state-compact">
            <span className="empty-state-icon"><Icon name="truck" size={26} /></span>
            <h2>You haven't requested any pickups yet.</h2>
            <p>Choose one of your devices and tell us when and where to collect it.</p>
            <Link className="button button-primary" to="/dashboard/pickup"><Icon name="truck" size={16} /> Request pickup</Link>
          </div>
        )}

        <div className="dashboard-bottom-grid">
          <div className="dashboard-tip">
            <span className="icon-box"><Icon name="spark" size={21} /></span>
            <div>
              <p className="eyebrow">Helpful next step</p>
              <h3>Know what your device is worth before it becomes clutter.</h3>
              <Link className="text-link" to="/sell">Calculate a demo estimate <Icon name="arrowRight" size={15} /></Link>
            </div>
          </div>
          <div className="dashboard-security">
            <Icon name="shield" size={20} />
            <div>
              <strong>Only you can see this dashboard.</strong>
              <p>Your devices are filtered on the server using your signed-in session.</p>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
