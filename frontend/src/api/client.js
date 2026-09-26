import { getStoredToken } from '../auth/authStorage.js'

// Where the FastAPI backend lives.
//
// Resolution order:
//   1. VITE_API_URL from the environment (build-time inlined, public by nature)
//   2. http://127.0.0.1:8000 in DEV only, so `npm run dev` needs no setup
//   3. same-origin (empty string) in a production build, which is the correct
//      default when a reverse proxy serves the API and the SPA from one host
//
// A localhost address is therefore never baked into a production bundle. Set
// VITE_API_URL at build time when the API is on a different host, and add that
// origin to the backend's CORS_ORIGIN_PRODUCTION.
const configuredApiUrl = import.meta.env.VITE_API_URL

if (!import.meta.env.DEV && !configuredApiUrl) {
  // Deliberate one-time warning: a misconfigured deployment should be obvious
  // in the console rather than failing as a confusing CORS or 404 error.
  // eslint-disable-next-line no-console
  console.warn(
    'SmartCycle: VITE_API_URL is not set, so API calls go to the same origin as ' +
      'this page. Set VITE_API_URL at build time if the API is served elsewhere.',
  )
}

export const apiBaseUrl = (
  configuredApiUrl || (import.meta.env.DEV ? 'http://127.0.0.1:8000' : '')
).replace(/\/$/, '')

export class ApiError extends Error {
  constructor(
    message,
    { status = null, body = null, isNetworkError = false, isMalformedResponse = false } = {},
  ) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.body = body
    this.isNetworkError = isNetworkError
    this.isMalformedResponse = isMalformedResponse
  }
}

async function readResponseBody(response) {
  const rawBody = await response.text()
  if (!rawBody) return null

  try {
    return JSON.parse(rawBody)
  } catch {
    return null
  }
}

export async function getHealth({ signal } = {}) {
  const response = await fetch(`${apiBaseUrl}/api/v1/health`, { signal })

  if (!response.ok) {
    throw new Error(`Health request failed with ${response.status}`)
  }

  return response.json()
}

export async function createDevice(device, { signal } = {}) {
  let response

  // A token is sent when the visitor is logged in so the backend can associate
  // the device with that user. Anonymous submissions stay fully supported.
  const storedToken = getStoredToken()
  const headers = {
    Accept: 'application/json',
    'Content-Type': 'application/json',
  }
  if (storedToken) {
    headers.Authorization = `Bearer ${storedToken}`
  }

  try {
    response = await fetch(`${apiBaseUrl}/api/devices`, {
      method: 'POST',
      headers,
      body: JSON.stringify(device),
      signal,
    })
  } catch (error) {
    if (error.name === 'AbortError') throw error
    throw new ApiError(
      'Unable to reach the server. Please make sure the backend is running.',
      { isNetworkError: true },
    )
  }

  const body = await readResponseBody(response)
  if (!response.ok) {
    const message = typeof body?.detail === 'string'
      ? body.detail
      : 'The device could not be submitted.'
    throw new ApiError(message, { status: response.status, body })
  }

  return body
}

function isDeviceResponse(body) {
  if (!body || typeof body !== 'object') return false

  const stringFields = [
    'tracking_id',
    'device_category',
    'brand',
    'model',
    'condition',
    'working_status',
    'location',
    'status',
  ]
  const numberFields = [
    'id',
    'age',
    'estimated_purchase_value',
    'potential_refurbished_value',
    'potential_recycled_value',
  ]

  return stringFields.every((field) => typeof body[field] === 'string')
    && numberFields.every((field) => typeof body[field] === 'number' && Number.isFinite(body[field]))
    && typeof body.created_at === 'string'
    && typeof body.updated_at === 'string'
}

export async function getDeviceByTrackingId(trackingId, { signal } = {}) {
  let response

  try {
    response = await fetch(`${apiBaseUrl}/api/devices/${encodeURIComponent(trackingId)}`, {
      method: 'GET',
      headers: {
        Accept: 'application/json',
      },
      signal,
    })
  } catch (error) {
    if (error.name === 'AbortError') throw error
    throw new ApiError(
      'Unable to reach the server. Please make sure the backend is running.',
      { isNetworkError: true },
    )
  }

  const body = await readResponseBody(response)
  if (response.status === 404) {
    throw new ApiError(
      'Tracking ID not found. Please check the ID and try again.',
      { status: 404, body },
    )
  }

  if (!response.ok) {
    throw new ApiError('Something went wrong, please try again.', { status: response.status, body })
  }

  if (!isDeviceResponse(body)) {
    throw new ApiError('Something went wrong, please try again.', {
      status: 502,
      body,
      isMalformedResponse: true,
    })
  }

  return body
}

function isUserResponse(body) {
  if (!body || typeof body !== 'object') return false

  return typeof body.id === 'number'
    && typeof body.name === 'string'
    && typeof body.email === 'string'
    && typeof body.created_at === 'string'
}

export async function registerUser(user, { signal } = {}) {
  let response

  try {
    response = await fetch(`${apiBaseUrl}/api/auth/register`, {
      method: 'POST',
      headers: {
        Accept: 'application/json',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(user),
      signal,
    })
  } catch (error) {
    if (error.name === 'AbortError') throw error
    throw new ApiError(
      'Unable to reach the server. Please make sure the backend is running.',
      { isNetworkError: true },
    )
  }

  const body = await readResponseBody(response)
  if (!response.ok) {
    const message = typeof body?.detail === 'string'
      ? body.detail
      : 'The account could not be created. Please check your details and try again.'
    throw new ApiError(message, { status: response.status, body })
  }

  if (!isUserResponse(body)) {
    throw new ApiError('The server returned an unexpected response.', {
      status: 502,
      body,
      isMalformedResponse: true,
    })
  }

  return body
}

export async function loginUser(credentials, { signal } = {}) {
  let response

  try {
    response = await fetch(`${apiBaseUrl}/api/auth/login`, {
      method: 'POST',
      headers: {
        Accept: 'application/json',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(credentials),
      signal,
    })
  } catch (error) {
    if (error.name === 'AbortError') throw error
    throw new ApiError(
      'Unable to reach the server. Please make sure the backend is running.',
      { isNetworkError: true },
    )
  }

  const body = await readResponseBody(response)
  if (!response.ok) {
    const message = response.status === 401
      ? 'Incorrect email or password'
      : 'Unable to log you in right now. Please try again.'
    throw new ApiError(message, { status: response.status, body })
  }

  if (!body || typeof body.access_token !== 'string' || body.token_type !== 'bearer') {
    throw new ApiError('The server returned an unexpected response.', {
      status: 502,
      body,
      isMalformedResponse: true,
    })
  }

  return body
}

export async function getCurrentUser(token, { signal } = {}) {
  let response

  try {
    response = await fetch(`${apiBaseUrl}/api/auth/me`, {
      method: 'GET',
      headers: {
        Accept: 'application/json',
        Authorization: `Bearer ${token}`,
      },
      signal,
    })
  } catch (error) {
    if (error.name === 'AbortError') throw error
    throw new ApiError(
      'Unable to reach the server. Please make sure the backend is running.',
      { isNetworkError: true },
    )
  }

  const body = await readResponseBody(response)
  if (!response.ok) {
    const message = response.status === 401
      ? 'Your session has ended. Please log in again.'
      : 'Unable to load your account right now. Please try again.'
    throw new ApiError(message, { status: response.status, body })
  }

  if (!isUserResponse(body)) {
    throw new ApiError('The server returned an unexpected response.', {
      status: 502,
      body,
      isMalformedResponse: true,
    })
  }

  return body
}

export async function getMyDevices(token, { signal } = {}) {
  let response

  try {
    response = await fetch(`${apiBaseUrl}/api/users/me/devices`, {
      method: 'GET',
      headers: {
        Accept: 'application/json',
        Authorization: `Bearer ${token}`,
      },
      signal,
    })
  } catch (error) {
    if (error.name === 'AbortError') throw error
    throw new ApiError(
      'Unable to reach the server. Please make sure the backend is running.',
      { isNetworkError: true },
    )
  }

  const body = await readResponseBody(response)
  if (!response.ok) {
    const message = response.status === 401
      ? 'Your session has ended. Please log in again.'
      : 'Your devices could not be loaded right now. Please try again.'
    throw new ApiError(message, { status: response.status, body })
  }

  if (!Array.isArray(body) || !body.every(isDeviceResponse)) {
    throw new ApiError('The server returned an unexpected response.', {
      status: 502,
      body,
      isMalformedResponse: true,
    })
  }

  return body
}

function isPickupResponse(body) {
  if (!body || typeof body !== 'object') return false

  return Number.isInteger(body.id)
    && Number.isInteger(body.device_id)
    && typeof body.pickup_address === 'string'
    && typeof body.preferred_date === 'string'
    && typeof body.preferred_time_slot === 'string'
    && typeof body.status === 'string'
    && typeof body.created_at === 'string'
    && typeof body.updated_at === 'string'
}

function readPickupErrorMessage(status, body) {
  if (status === 401) return 'Your session has ended. Please log in again.'
  if (status === 404 || status === 409) {
    return typeof body?.detail === 'string'
      ? body.detail
      : 'That pickup request could not be completed.'
  }
  if (status === 422) return 'Please check the highlighted fields and try again.'
  return 'Something went wrong. Please try again.'
}

export async function getMyPickups(token, { signal } = {}) {
  let response

  try {
    response = await fetch(`${apiBaseUrl}/api/pickups/my`, {
      method: 'GET',
      headers: {
        Accept: 'application/json',
        Authorization: `Bearer ${token}`,
      },
      signal,
    })
  } catch (error) {
    if (error.name === 'AbortError') throw error
    throw new ApiError(
      'Unable to reach the server. Please make sure the backend is running.',
      { isNetworkError: true },
    )
  }

  const body = await readResponseBody(response)
  if (!response.ok) {
    const message = response.status === 401
      ? 'Your session has ended. Please log in again.'
      : 'Your pickup requests could not be loaded right now. Please try again.'
    throw new ApiError(message, { status: response.status, body })
  }

  if (!Array.isArray(body) || !body.every(isPickupResponse)) {
    throw new ApiError('The server returned an unexpected response.', {
      status: 502,
      body,
      isMalformedResponse: true,
    })
  }

  return body
}

export async function createPickupRequest(token, pickup, { signal } = {}) {
  let response

  try {
    response = await fetch(`${apiBaseUrl}/api/pickups`, {
      method: 'POST',
      headers: {
        Accept: 'application/json',
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify(pickup),
      signal,
    })
  } catch (error) {
    if (error.name === 'AbortError') throw error
    throw new ApiError(
      'Unable to reach the server. Please make sure the backend is running.',
      { isNetworkError: true },
    )
  }

  const body = await readResponseBody(response)
  if (!response.ok) {
    throw new ApiError(readPickupErrorMessage(response.status, body), {
      status: response.status,
      body,
    })
  }

  if (!isPickupResponse(body)) {
    throw new ApiError('The server returned an unexpected response.', {
      status: 502,
      body,
      isMalformedResponse: true,
    })
  }

  return body
}

function isAdminDeviceResponse(body) {
  if (!body || typeof body !== 'object') return false

  return typeof body.tracking_id === 'string'
    && typeof body.device_category === 'string'
    && typeof body.brand === 'string'
    && typeof body.model === 'string'
    && typeof body.status === 'string'
    && typeof body.estimated_purchase_value === 'number'
    && Number.isFinite(body.estimated_purchase_value)
    && typeof body.created_at === 'string'
}

function readAdminErrorMessage(status, body) {
  if (status === 401) return 'Your session has ended. Please log in again.'
  if (status === 403) return 'Administrator access is required for this resource.'
  return 'The admin data could not be loaded right now. Please try again.'
}

async function fetchAdminResource(path, token, { signal } = {}) {
  let response

  try {
    response = await fetch(`${apiBaseUrl}${path}`, {
      method: 'GET',
      headers: {
        Accept: 'application/json',
        Authorization: `Bearer ${token}`,
      },
      signal,
    })
  } catch (error) {
    if (error.name === 'AbortError') throw error
    throw new ApiError(
      'Unable to reach the server. Please make sure the backend is running.',
      { isNetworkError: true },
    )
  }

  const body = await readResponseBody(response)
  if (!response.ok) {
    throw new ApiError(readAdminErrorMessage(response.status, body), {
      status: response.status,
      body,
    })
  }

  return body
}

export async function getAdminDashboard(token, { signal } = {}) {
  const body = await fetchAdminResource('/api/admin/dashboard', token, { signal })

  const totalFields = ['total_users', 'total_devices', 'total_pickups']
  const hasTotals = totalFields.every((field) => Number.isInteger(body?.[field]))
  const hasBreakdowns = ['devices_by_status', 'pickups_by_status'].every(
    (field) => Array.isArray(body?.[field]),
  )
  const hasRecent = ['recent_devices', 'recent_pickups'].every(
    (field) => Array.isArray(body?.[field]),
  )

  if (!hasTotals || !hasBreakdowns || !hasRecent) {
    throw new ApiError('The server returned an unexpected response.', {
      status: 502,
      body,
      isMalformedResponse: true,
    })
  }

  return body
}

export async function getAdminUsers(token, { signal } = {}) {
  const body = await fetchAdminResource('/api/admin/users', token, { signal })

  if (!Array.isArray(body) || !body.every((row) => row && typeof row.email === 'string' && typeof row.role === 'string')) {
    throw new ApiError('The server returned an unexpected response.', {
      status: 502,
      body,
      isMalformedResponse: true,
    })
  }

  return body
}

export async function getAdminDevices(token, { signal } = {}) {
  const body = await fetchAdminResource('/api/admin/devices', token, { signal })

  if (!Array.isArray(body) || !body.every(isAdminDeviceResponse)) {
    throw new ApiError('The server returned an unexpected response.', {
      status: 502,
      body,
      isMalformedResponse: true,
    })
  }

  return body
}

export async function getAdminPickups(token, { signal } = {}) {
  const body = await fetchAdminResource('/api/admin/pickups', token, { signal })

  const valid = Array.isArray(body) && body.every(
    (row) => row
      && Number.isInteger(row.id)
      && typeof row.device_tracking_id === 'string'
      && typeof row.status === 'string',
  )

  if (!valid) {
    throw new ApiError('The server returned an unexpected response.', {
      status: 502,
      body,
      isMalformedResponse: true,
    })
  }

  return body
}

async function sendAdminStatusUpdate(path, token, statusValue, { signal } = {}) {
  let response

  try {
    response = await fetch(`${apiBaseUrl}${path}`, {
      method: 'PATCH',
      headers: {
        Accept: 'application/json',
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ status: statusValue }),
      signal,
    })
  } catch (error) {
    if (error.name === 'AbortError') throw error
    throw new ApiError(
      'Unable to reach the server. Please make sure the backend is running.',
      { isNetworkError: true },
    )
  }

  const body = await readResponseBody(response)
  if (!response.ok) {
    const message = readAdminStatusErrorMessage(response.status, body)
    throw new ApiError(message, { status: response.status, body })
  }

  return body
}

function readAdminStatusErrorMessage(status, body) {
  if (status === 401) return 'Your session has ended. Please log in again.'
  if (status === 403) return 'Administrator access is required to change a status.'
  if (status === 404) {
    return typeof body?.detail === 'string'
      ? body.detail
      : 'That record could not be found.'
  }
  if (status === 422) return 'That status is not valid. Please choose one of the available statuses.'
  return 'The status could not be updated. Please try again.'
}

export async function updateAdminDeviceStatus(token, deviceId, statusValue, { signal } = {}) {
  const body = await sendAdminStatusUpdate(
    `/api/admin/devices/${encodeURIComponent(deviceId)}/status`,
    token,
    statusValue,
    { signal },
  )

  if (!isDeviceResponse(body)) {
    throw new ApiError('The server returned an unexpected response.', {
      status: 502,
      body,
      isMalformedResponse: true,
    })
  }

  return body
}

export async function updateAdminPickupStatus(token, pickupId, statusValue, { signal } = {}) {
  const body = await sendAdminStatusUpdate(
    `/api/admin/pickups/${encodeURIComponent(pickupId)}/status`,
    token,
    statusValue,
    { signal },
  )

  const valid = body
    && Number.isInteger(body.id)
    && typeof body.status === 'string'
    && typeof body.pickup_address === 'string'

  if (!valid) {
    throw new ApiError('The server returned an unexpected response.', {
      status: 502,
      body,
      isMalformedResponse: true,
    })
  }

  return body
}

export async function getAdminValuationModel(token, { signal } = {}) {
  const body = await fetchAdminResource('/api/admin/valuation-model', token, { signal })

  if (!body || typeof body.model_available !== 'boolean') {
    throw new ApiError('The server returned an unexpected response.', {
      status: 502,
      body,
      isMalformedResponse: true,
    })
  }

  return body
}
