import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import {
  ApiError,
  getAdminDashboard,
  getAdminDevices,
  getAdminPickups,
  getAdminUsers,
  getAdminValuationModel,
  updateAdminDeviceStatus,
  updateAdminPickupStatus,
} from '../api/client.js'
import Icon from '../components/Icon.jsx'
import MetricCard from '../components/MetricCard.jsx'
import PickupStatusBadge from '../components/PickupStatusBadge.jsx'
import StatusBadge from '../components/StatusBadge.jsx'
import { useAuth } from '../context/AuthContext.jsx'

const currencyFormatter = new Intl.NumberFormat('en-IN', {
  style: 'currency',
  currency: 'INR',
  maximumFractionDigits: 0,
})

const dateFormatter = new Intl.DateTimeFormat('en-IN', { dateStyle: 'medium' })

// Stage 4B: baseline names come from the training run, so they are labelled
// here rather than shown as raw keys.
const BASELINE_LABELS = {
  mean_predictor: 'Mean-value predictor',
  rule_based_estimator: 'Rule-based estimator',
}

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

function StatusMix({ title, buckets }) {
  const total = buckets.reduce((sum, bucket) => sum + bucket.count, 0)

  return (
    <div className="admin-side-card">
      <div className="admin-side-card-heading">
        <span className="icon-box"><Icon name="chart" size={20} /></span>
        <span><p className="eyebrow">At a glance</p><h3>{title}</h3></span>
      </div>
      <div className="status-mix">
        {buckets.map((bucket) => {
          const share = total > 0 ? Math.round((bucket.count / total) * 100) : 0
          return (
            <div key={bucket.status}>
              <span>{bucket.status}</span>
              <strong>{bucket.count} ({share}%)</strong>
              <i><b style={{ width: `${share}%` }} /></i>
            </div>
          )
        })}
      </div>
      <small className="field-error">Live counts from the SmartCycle database.</small>
    </div>
  )
}

export default function AdminDashboardPage() {
  const { token, user } = useAuth()
  const [stats, setStats] = useState(null)
  const [users, setUsers] = useState([])
  const [devices, setDevices] = useState([])
  const [pickups, setPickups] = useState([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState('')
  const [errorType, setErrorType] = useState('')
  const [deviceFilter, setDeviceFilter] = useState('All statuses')

  const loadAdminData = useCallback(async (activeToken) => {
    setIsLoading(true)
    setError('')
    setErrorType('')

    try {
      const [nextStats, nextUsers, nextDevices, nextPickups, nextModel] = await Promise.all([
        getAdminDashboard(activeToken),
        getAdminUsers(activeToken),
        getAdminDevices(activeToken),
        getAdminPickups(activeToken),
        getAdminValuationModel(activeToken),
      ])

      setStats(nextStats)
      setUsers(nextUsers)
      setDevices(nextDevices)
      setPickups(nextPickups)
      setModelInfo(nextModel)
    } catch (loadError) {
      setStats(null)
      setUsers([])
      setDevices([])
      setPickups([])
      setModelInfo(null)

      if (loadError instanceof ApiError && loadError.status === 401) {
        setError('Your session has ended. Please log in again.')
        setErrorType('unauthorized')
        return
      }

      if (loadError instanceof ApiError && loadError.status === 403) {
        setError('Administrator access is required for this resource.')
        setErrorType('forbidden')
        return
      }

      if (loadError instanceof ApiError && loadError.isNetworkError) {
        setError('We could not reach SmartCycle right now. Please check your connection and try again.')
        setErrorType('network')
        return
      }

      setError('Something went wrong while loading the admin workspace. Please try again.')
      setErrorType('server')
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    if (!token) return undefined
    void loadAdminData(token)
  }, [token, loadAdminData])

  // The selectable statuses are the backend's own defined values, taken from
  // the status buckets the admin dashboard endpoint returns.
  const deviceStatuses = useMemo(
    () => (stats ? stats.devices_by_status.map((bucket) => bucket.status) : []),
    [stats],
  )

  const pickupStatuses = useMemo(
    () => (stats ? stats.pickups_by_status.map((bucket) => bucket.status) : []),
    [stats],
  )

  const [modelInfo, setModelInfo] = useState(null)
  const [updating, setUpdating] = useState({})
  const [updateError, setUpdateError] = useState('')
  const [updateSuccess, setUpdateSuccess] = useState('')

  const applyDeviceUpdate = useCallback((deviceId, changes) => {
    setDevices((current) => current.map((device) => (
      device.id === deviceId ? { ...device, ...changes } : device
    )))
  }, [])

  const applyPickupUpdate = useCallback((pickupId, changes) => {
    setPickups((current) => current.map((pickup) => (
      pickup.id === pickupId ? { ...pickup, ...changes } : pickup
    )))
  }, [])

  const refreshStats = useCallback(async () => {
    try {
      setStats(await getAdminDashboard(token))
    } catch {
      // A failed refresh must not break the table the admin is looking at.
    }
  }, [token])

  const runStatusUpdate = useCallback(async (key, request, onApplied) => {
    if (updating[key]) return

    setUpdating((current) => ({ ...current, [key]: true }))
    setUpdateError('')
    setUpdateSuccess('')

    try {
      await request()
      onApplied()
      await refreshStats()
    } catch (error) {
      setUpdateError(
        error instanceof ApiError
          ? error.message
          : 'The status could not be updated. Please try again.',
      )
    } finally {
      setUpdating((current) => ({ ...current, [key]: false }))
    }
  }, [refreshStats, updating])

  const handleDeviceStatusChange = (device, nextStatus) => {
    if (!nextStatus || nextStatus === device.status) return

    void runStatusUpdate(
      `device-${device.id}`,
      () => updateAdminDeviceStatus(token, device.id, nextStatus),
      () => {
        applyDeviceUpdate(device.id, { status: nextStatus })
        setUpdateSuccess(`${device.tracking_id} is now "${nextStatus}".`)
      },
    )
  }

  const handlePickupStatusChange = (pickup, nextStatus) => {
    if (!nextStatus || nextStatus === pickup.status) return

    void runStatusUpdate(
      `pickup-${pickup.id}`,
      () => updateAdminPickupStatus(token, pickup.id, nextStatus),
      () => {
        applyPickupUpdate(pickup.id, { status: nextStatus })
        setUpdateSuccess(`Pickup #${pickup.id} is now "${nextStatus}".`)
      },
    )
  }

  const filteredDevices = deviceFilter === 'All statuses'
    ? devices
    : devices.filter((device) => device.status === deviceFilter)

  return (
    <section className="admin-page section">
      <div className="container">
        <div className="admin-header">
          <div>
            <div className="admin-label"><span className="admin-label-dot" /> Operations workspace</div>
            <h1>Admin dashboard</h1>
            <p>Real platform statistics, users, devices and pickup requests.</p>
          </div>
          <div className="admin-header-actions">
            <Link className="button button-secondary" to="/"><Icon name="external" size={16} /> View public site</Link>
          </div>
        </div>

        {isLoading ? (
          <div aria-live="polite" className="dashboard-empty-state" role="status">
            <span className="empty-state-icon"><Icon name="refresh" size={28} /></span>
            <h2>Loading the operations workspace…</h2>
            <p>Reading live statistics from the SmartCycle database.</p>
          </div>
        ) : error ? (
          <div aria-live="polite" className="dashboard-empty-state dashboard-error-state" role="alert">
            <span className="empty-state-icon"><Icon name="alert" size={28} /></span>
            <h2>{errorType === 'forbidden' ? 'Administrator access required.' : 'The admin workspace could not be loaded.'}</h2>
            <p>{error}</p>
            {errorType === 'forbidden' ? (
              <Link className="button button-primary" to="/dashboard">Go to my dashboard <Icon name="arrowRight" size={16} /></Link>
            ) : (
              <button className="button button-primary" onClick={() => loadAdminData(token)} type="button">Try again <Icon name="refresh" size={16} /></button>
            )}
          </div>
        ) : (
          <>
            <div className="metrics-grid admin-metrics">
              <MetricCard icon="users" label="Total users" note="Registered accounts" tone="dark" value={String(stats.total_users)} />
              <MetricCard icon="package" label="Total devices" note="All submissions" value={String(stats.total_devices)} />
              <MetricCard icon="truck" label="Total pickups" note="All requests" value={String(stats.total_pickups)} />
              <MetricCard icon="chart" label="Device statuses" note="Distinct values in use" value={String(stats.devices_by_status.filter((b) => b.count > 0).length)} />
              <MetricCard icon="layers" label="Pickup statuses" note="Distinct values in use" value={String(stats.pickups_by_status.filter((b) => b.count > 0).length)} />
              <MetricCard icon="shield" label="Signed in as" note="Administrator" value={user?.role || 'admin'} />
            </div>

            {updateError ? (
              <div className="form-error-summary admin-update-feedback" role="alert">
                <Icon name="alert" size={18} />
                <span>{updateError}</span>
              </div>
            ) : null}

            {updateSuccess ? (
              <div aria-live="polite" className="form-success admin-update-feedback" role="status">
                <Icon name="checkCircle" size={18} />
                <span>{updateSuccess}</span>
              </div>
            ) : null}

            <div className="admin-content-grid">
              <div className="admin-table-card">
                <div className="admin-table-heading">
                  <div><p className="eyebrow">Operations queue</p><h2>Device management</h2></div>
                  <div className="admin-table-actions">
                    <select aria-label="Filter devices by status" disabled={isLoading} onChange={(event) => setDeviceFilter(event.target.value)} value={deviceFilter}>
                      <option>All statuses</option>
                      {deviceStatuses.map((statusName) => <option key={statusName}>{statusName}</option>)}
                    </select>
                  </div>
                </div>
                <div className="table-wrap">
                  <table className="data-table admin-data-table">
                    <thead>
                      <tr><th>Tracking ID</th><th>Owner</th><th>Device</th><th>Condition</th><th>Value</th><th>Status</th><th>Date</th><th>Update status</th></tr>
                    </thead>
                    <tbody>
                      {filteredDevices.length === 0 ? (
                        <tr><td colSpan="8">No devices match this filter.</td></tr>
                      ) : filteredDevices.map((device) => (
                        <tr key={device.tracking_id}>
                          <td><span className="tracking-id-text">{device.tracking_id}</span></td>
                          <td><strong>{device.owner_name || 'Unowned'}</strong><small className="table-cell-sub">{device.owner_email || 'No linked account'}</small></td>
                          <td>{device.brand} {device.model}<small className="table-cell-sub">{device.device_category}</small></td>
                          <td>{device.condition}</td>
                          <td><strong>{formatCurrency(device.estimated_purchase_value)}</strong></td>
                          <td><StatusBadge status={device.status} /></td>
                          <td>{formatDate(device.created_at)}</td>
                          <td>
                            <div className="admin-status-control">
                              <select
                                aria-label={`Set status for ${device.tracking_id}`}
                                disabled={Boolean(updating[`device-${device.id}`])}
                                onChange={(event) => handleDeviceStatusChange(device, event.target.value)}
                                value={device.status}
                              >
                                {deviceStatuses.map((statusName) => <option key={statusName}>{statusName}</option>)}
                              </select>
                              {updating[`device-${device.id}`] ? <span className="admin-status-saving">Saving…</span> : null}
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <div className="table-card-footer">
                  <span>Showing {filteredDevices.length} of {devices.length} real device records</span>
                </div>
              </div>

              <aside className="admin-side-column">
                <StatusMix title="Device status mix" buckets={stats.devices_by_status} />
                <StatusMix title="Pickup status mix" buckets={stats.pickups_by_status} />
                <div className="admin-side-card">
                  <div className="admin-side-card-heading">
                    <span className="icon-box"><Icon name="spark" size={20} /></span>
                    <span><p className="eyebrow">Valuation engine</p><h3>ML model status</h3></span>
                  </div>
                  {modelInfo ? (
                    <div className="admin-model-info">
                      <div><span>Status</span><strong>{modelInfo.model_available ? 'Loaded' : 'Unavailable'}</strong></div>
                      <div><span>Model</span><strong>{modelInfo.model_type || 'Not available'}</strong></div>
                      {modelInfo.dataset_identifier ? <div><span>Dataset</span><strong>{modelInfo.dataset_identifier}</strong></div> : null}
                      {modelInfo.total_rows ? <div><span>Dataset rows</span><strong>{modelInfo.total_rows}</strong></div> : null}
                      {modelInfo.training_age_range ? <div><span>Trained on ages</span><strong>{modelInfo.training_age_range}</strong></div> : null}
                      {modelInfo.trained_at ? <div><span>Trained at</span><strong>{new Date(modelInfo.trained_at).toLocaleString('en-IN')}</strong></div> : null}
                      {modelInfo.metrics && Object.keys(modelInfo.metrics).length > 0 ? (
                        <>
                          {modelInfo.metrics.mae !== undefined ? <div><span>MAE</span><strong>Rs {Number(modelInfo.metrics.mae).toLocaleString('en-IN')}</strong></div> : null}
                          {modelInfo.metrics.rmse !== undefined ? <div><span>RMSE</span><strong>Rs {Number(modelInfo.metrics.rmse).toLocaleString('en-IN')}</strong></div> : null}
                          {modelInfo.metrics.r2 !== undefined ? <div><span>R²</span><strong>{Number(modelInfo.metrics.r2).toFixed(4)}</strong></div> : null}
                        </>
                      ) : null}

                      {modelInfo.baselines && Object.keys(modelInfo.baselines).length > 0 ? (
                        <div className="admin-model-baselines">
                          <p className="admin-model-subhead">Baseline comparison (same held-out rows)</p>
                          {Object.entries(modelInfo.baselines).map(([name, scores]) => (
                            <div key={name}>
                              <span>{BASELINE_LABELS[name] || name}</span>
                              <strong>MAE Rs {Number(scores.mae).toLocaleString('en-IN')}</strong>
                            </div>
                          ))}
                          {modelInfo.baseline_note ? <p className="admin-model-note">{modelInfo.baseline_note}</p> : null}
                        </div>
                      ) : null}

                      {modelInfo.metrics_ceiling_note ? <p className="admin-model-note">{modelInfo.metrics_ceiling_note}</p> : null}
                      {modelInfo.model_selection_note ? <p className="admin-model-note">{modelInfo.model_selection_note}</p> : null}
                      <p className="admin-model-note">{modelInfo.disclaimer || 'No metrics available.'}</p>
                      <p className="admin-model-note">If the model is unavailable, or a submission falls outside what the model was trained on, the {modelInfo.fallback_method} estimate is used automatically.</p>
                    </div>
                  ) : (
                    <p className="admin-model-note">Model information is unavailable right now.</p>
                  )}
                </div>
              </aside>
            </div>

            <div className="admin-section-grid">
              <div className="admin-table-card">
                <div className="admin-table-heading">
                  <div><p className="eyebrow">Accounts</p><h2>Users</h2></div>
                </div>
                <div className="table-wrap">
                  <table className="data-table admin-data-table">
                    <thead>
                      <tr><th>Name</th><th>Email</th><th>Role</th><th>Devices</th><th>Pickups</th><th>Joined</th></tr>
                    </thead>
                    <tbody>
                      {users.map((row) => (
                        <tr key={row.id}>
                          <td><strong>{row.name}</strong></td>
                          <td>{row.email}</td>
                          <td><span className={`status-badge ${row.role === 'admin' ? 'status-requested' : 'status-neutral'}`}>{row.role}</span></td>
                          <td>{row.device_count}</td>
                          <td>{row.pickup_count}</td>
                          <td>{formatDate(row.created_at)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <div className="table-card-footer">
                  <span>Showing {users.length} real accounts</span>
                </div>
              </div>

              <div className="admin-table-card">
                <div className="admin-table-heading">
                  <div><p className="eyebrow">Collection</p><h2>Pickup requests</h2></div>
                </div>
                <div className="table-wrap">
                  <table className="data-table admin-data-table">
                    <thead>
                      <tr><th>Device</th><th>Owner</th><th>Address</th><th>Preferred</th><th>Status</th><th>Requested</th><th>Update status</th></tr>
                    </thead>
                    <tbody>
                      {pickups.length === 0 ? (
                        <tr><td colSpan="7">No pickup requests yet.</td></tr>
                      ) : pickups.map((pickup) => (
                        <tr key={pickup.id}>
                          <td><strong>{pickup.device_label}</strong><small className="table-cell-sub">{pickup.device_tracking_id}</small></td>
                          <td><strong>{pickup.owner_name}</strong><small className="table-cell-sub">{pickup.owner_email}</small></td>
                          <td>{pickup.pickup_address}</td>
                          <td>{formatDate(pickup.preferred_date)}<small className="table-cell-sub">{pickup.preferred_time_slot}</small></td>
                          <td><PickupStatusBadge status={pickup.status} /></td>
                          <td>{formatDate(pickup.created_at)}</td>
                          <td>
                            <div className="admin-status-control">
                              <select
                                aria-label={`Set status for pickup ${pickup.id}`}
                                disabled={Boolean(updating[`pickup-${pickup.id}`])}
                                onChange={(event) => handlePickupStatusChange(pickup, event.target.value)}
                                value={pickup.status}
                              >
                                {pickupStatuses.map((statusName) => <option key={statusName}>{statusName}</option>)}
                              </select>
                              {updating[`pickup-${pickup.id}`] ? <span className="admin-status-saving">Saving…</span> : null}
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <div className="table-card-footer">
                  <span>Showing {pickups.length} real pickup requests</span>
                </div>
              </div>
            </div>

            <div className="admin-section-grid">
              <div className="admin-table-card">
                <div className="admin-table-heading">
                  <div><p className="eyebrow">Recent activity</p><h2>Latest device submissions</h2></div>
                </div>
                <div className="admin-activity-list">
                  {stats.recent_devices.map((device) => (
                    <div className="admin-activity-item" key={device.id}>
                      <span className="table-device-icon"><Icon name={deviceIconFor(device.device_category)} size={17} /></span>
                      <div>
                        <strong>{device.brand} {device.model}</strong>
                        <small>{device.tracking_id} · {device.owner_name || 'Unowned'}</small>
                      </div>
                      <StatusBadge status={device.status} />
                    </div>
                  ))}
                </div>
              </div>

              <div className="admin-table-card">
                <div className="admin-table-heading">
                  <div><p className="eyebrow">Recent activity</p><h2>Latest pickup requests</h2></div>
                </div>
                <div className="admin-activity-list">
                  {stats.recent_pickups.length === 0 ? (
                    <div className="admin-activity-item"><small>No pickup requests yet.</small></div>
                  ) : stats.recent_pickups.map((pickup) => (
                    <div className="admin-activity-item" key={pickup.id}>
                      <span className="table-device-icon"><Icon name="truck" size={17} /></span>
                      <div>
                        <strong>{pickup.device_tracking_id}</strong>
                        <small>{formatDate(pickup.preferred_date)} · {pickup.preferred_time_slot} · {pickup.owner_name || 'Unknown owner'}</small>
                      </div>
                      <PickupStatusBadge status={pickup.status} />
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </>
        )}
      </div>
    </section>
  )
}
