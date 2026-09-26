import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { ApiError, createDevice } from '../api/client.js'
import DemoNotice from '../components/DemoNotice.jsx'
import Icon from '../components/Icon.jsx'
import SectionHeading from '../components/SectionHeading.jsx'
import StatusBadge from '../components/StatusBadge.jsx'

const initialForm = {
  device_category: 'Smartphone',
  brand: 'Apple',
  model: 'iPhone 13',
  age: '2',
  condition: 'Good',
  working_status: 'Fully Working',
  physical_damage: 'Minor scratches',
  accessories: 'Original box and cable',
  original_purchase_price: '65000',
  location: 'Bengaluru, Karnataka',
}

const deviceCategories = [
  'Smartphone',
  'Laptop',
  'Tablet',
  'Desktop computer',
  'Monitor',
  'Television',
  'Printer',
  'Accessories',
  'Other electronics',
]

const conditionOptions = ['Excellent', 'Good', 'Fair', 'Poor', 'Not Working']
const workingStatusOptions = ['Fully Working', 'Partially Working', 'Not Working']
const physicalDamageOptions = ['None', 'Minor scratches', 'Cracks or major damage']
const accessoryOptions = [
  'Original box and cable',
  'Original box, cable and case',
  'No accessories',
]

const requiredFields = [
  'device_category',
  'brand',
  'model',
  'age',
  'condition',
  'working_status',
  'location',
]

const fieldLabels = {
  device_category: 'Device category',
  brand: 'Brand',
  model: 'Model',
  age: 'Age',
  condition: 'Condition',
  working_status: 'Working status',
  physical_damage: 'Physical damage',
  accessories: 'Accessories',
  original_purchase_price: 'Original purchase price',
  location: 'Location',
}

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

function validateForm(form) {
  const errors = {}

  requiredFields.forEach((field) => {
    if (!String(form[field] ?? '').trim()) {
      errors[field] = `${fieldLabels[field]} is required.`
    }
  })

  const age = String(form.age).trim()
  if (age && (!/^\d+$/.test(age) || Number(age) < 0)) {
    errors.age = 'Enter age as a whole number of years, 0 or greater.'
  }

  const purchasePrice = String(form.original_purchase_price).trim()
  if (purchasePrice) {
    const numericPrice = Number(purchasePrice)
    if (!Number.isFinite(numericPrice) || numericPrice < 0) {
      errors.original_purchase_price = 'Enter a valid non-negative purchase price.'
    }
  }

  return errors
}

function buildDevicePayload(form) {
  const purchasePrice = String(form.original_purchase_price).trim()

  return {
    device_category: form.device_category.trim(),
    brand: form.brand.trim(),
    model: form.model.trim(),
    age: Number(form.age),
    condition: form.condition,
    working_status: form.working_status,
    physical_damage: form.physical_damage || null,
    accessories: form.accessories === 'No accessories' ? null : form.accessories || null,
    original_purchase_price: purchasePrice ? Number(purchasePrice) : null,
    location: form.location.trim(),
  }
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
      : item.msg
  })

  return errors
}

function FieldError({ field, errors }) {
  if (!errors[field]) return null
  return <small className="field-error" id={`${field}-error`}>{errors[field]}</small>
}

export default function SellDevicePage() {
  const [form, setForm] = useState(initialForm)
  const [fieldErrors, setFieldErrors] = useState({})
  const [submitError, setSubmitError] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [createdDevice, setCreatedDevice] = useState(null)
  const navigate = useNavigate()

  const updateField = (event) => {
    const { name, value } = event.target
    setForm((current) => ({ ...current, [name]: value }))
    setFieldErrors((current) => ({ ...current, [name]: '' }))
    setSubmitError('')
    setCreatedDevice(null)
  }

  const handleSubmit = async (event) => {
    event.preventDefault()
    const validationErrors = validateForm(form)
    setFieldErrors(validationErrors)

    if (Object.keys(validationErrors).length > 0) {
      setSubmitError('Please correct the highlighted fields before submitting.')
      return
    }

    setIsSubmitting(true)
    setSubmitError('')

    try {
      const device = await createDevice(buildDevicePayload(form))
      setCreatedDevice(device)
    } catch (error) {
      if (error instanceof ApiError && error.status === 422) {
        const backendErrors = mapBackendFieldErrors(error.body)
        if (Object.keys(backendErrors).length > 0) {
          setFieldErrors(backendErrors)
          setSubmitError('Please correct the highlighted fields before submitting.')
        } else {
          setSubmitError('Some device details need attention. Please review the form.')
        }
      } else if (error instanceof ApiError && error.isNetworkError) {
        setSubmitError(error.message)
      } else if (error instanceof ApiError && error.status >= 500) {
        setSubmitError('Something went wrong on the server. Please try again.')
      } else if (error instanceof ApiError && error.status === 409) {
        setSubmitError('The device could not be submitted right now. Please try again.')
      } else {
        setSubmitError('Something went wrong. Please try again.')
      }
    } finally {
      setIsSubmitting(false)
    }
  }

  const editDetails = () => {
    setCreatedDevice(null)
    setSubmitError('')
  }

  return (
    <>
      <section className="page-hero page-hero-sell">
        <div className="container page-hero-inner">
          <div>
            <p className="eyebrow">Sell a device</p>
            <h1>Tell us about the device you want to move on.</h1>
            <p>Share a few details and see a transparent demo estimate before deciding on collection.</p>
          </div>
          <div className="page-hero-side-note">
            <Icon name="shield" size={21} />
            <span><strong>Your information stays yours.</strong><small>Your details are sent to the SmartCycle device API for this submission.</small></span>
          </div>
        </div>
      </section>

      <section className="section form-section">
        <div className="container form-layout">
          <form className="form-card" noValidate onSubmit={handleSubmit}>
            <p className="form-required-note">Fields marked <span aria-hidden="true">*</span><span className="sr-only">with an asterisk</span> are required. Price and accessories are optional.</p>
            <div className="form-card-heading">
              <div><p className="eyebrow">Device details</p><h2>Start with the basics.</h2></div>
              <span className="form-step-label">01 / 02</span>
            </div>
            <DemoNotice>This form sends a real device submission to the SmartCycle device API. The returned values are rule-based/demo estimates.</DemoNotice>

            {submitError ? (
              <div className="form-error-summary" role="alert">
                <Icon name="alert" size={18} />
                <span>{submitError}</span>
              </div>
            ) : null}

            <div className="form-grid">
              <label className="field">
                <span data-required="true">Device category</span>
                <select aria-describedby={fieldErrors.device_category ? 'device_category-error' : undefined} aria-invalid={Boolean(fieldErrors.device_category)} disabled={isSubmitting} name="device_category" onChange={updateField} value={form.device_category}>
                  {deviceCategories.map((category) => <option key={category}>{category}</option>)}
                </select>
                <FieldError errors={fieldErrors} field="device_category" />
              </label>
              <label className="field">
                <span data-required="true">Brand</span>
                <input aria-describedby={fieldErrors.brand ? 'brand-error' : undefined} aria-invalid={Boolean(fieldErrors.brand)} disabled={isSubmitting} name="brand" onChange={updateField} value={form.brand} />
                <FieldError errors={fieldErrors} field="brand" />
              </label>
              <label className="field">
                <span data-required="true">Model</span>
                <input aria-describedby={fieldErrors.model ? 'model-error' : undefined} aria-invalid={Boolean(fieldErrors.model)} disabled={isSubmitting} name="model" onChange={updateField} placeholder="e.g. iPhone 13" value={form.model} />
                <FieldError errors={fieldErrors} field="model" />
              </label>
              <label className="field">
                <span data-required="true">Age (years)</span>
                <input aria-describedby={fieldErrors.age ? 'age-error' : undefined} aria-invalid={Boolean(fieldErrors.age)} disabled={isSubmitting} min="0" name="age" onChange={updateField} step="1" type="number" value={form.age} />
                <FieldError errors={fieldErrors} field="age" />
              </label>
              <label className="field">
                <span data-required="true">Condition</span>
                <select aria-describedby={fieldErrors.condition ? 'condition-error' : undefined} aria-invalid={Boolean(fieldErrors.condition)} disabled={isSubmitting} name="condition" onChange={updateField} value={form.condition}>
                  {conditionOptions.map((condition) => <option key={condition}>{condition}</option>)}
                </select>
                <FieldError errors={fieldErrors} field="condition" />
              </label>
              <label className="field">
                <span data-required="true">Working status</span>
                <select aria-describedby={fieldErrors.working_status ? 'working_status-error' : undefined} aria-invalid={Boolean(fieldErrors.working_status)} disabled={isSubmitting} name="working_status" onChange={updateField} value={form.working_status}>
                  {workingStatusOptions.map((status) => <option key={status}>{status}</option>)}
                </select>
                <FieldError errors={fieldErrors} field="working_status" />
              </label>
              <label className="field">
                <span data-required="false">Physical damage</span>
                <select disabled={isSubmitting} name="physical_damage" onChange={updateField} value={form.physical_damage}>
                  {physicalDamageOptions.map((damage) => <option key={damage}>{damage}</option>)}
                </select>
                <FieldError errors={fieldErrors} field="physical_damage" />
              </label>
              <label className="field">
                <span data-required="false">Accessories</span>
                <select disabled={isSubmitting} name="accessories" onChange={updateField} value={form.accessories}>
                  {accessoryOptions.map((accessory) => <option key={accessory}>{accessory}</option>)}
                </select>
                <FieldError errors={fieldErrors} field="accessories" />
              </label>
              <label className="field">
                <span data-required="false">Original purchase price</span>
                <div className="input-with-prefix">
                  <span>₹</span>
                  <input aria-describedby={fieldErrors.original_purchase_price ? 'original_purchase_price-error' : undefined} aria-invalid={Boolean(fieldErrors.original_purchase_price)} disabled={isSubmitting} min="0" name="original_purchase_price" onChange={updateField} step="0.01" type="number" value={form.original_purchase_price} />
                </div>
                <FieldError errors={fieldErrors} field="original_purchase_price" />
              </label>
              <label className="field field-full">
                <span data-required="true">Location</span>
                <div className="input-with-icon">
                  <Icon name="mapPin" size={17} />
                  <input aria-describedby={fieldErrors.location ? 'location-error' : undefined} aria-invalid={Boolean(fieldErrors.location)} disabled={isSubmitting} name="location" onChange={updateField} value={form.location} />
                </div>
                <FieldError errors={fieldErrors} field="location" />
              </label>
            </div>

            <div className="form-actions">
              <span className="form-required-note"><span>*</span> Required fields are marked by the form labels</span>
              <button aria-busy={isSubmitting} className="button button-primary" disabled={isSubmitting} type="submit">
                {isSubmitting ? 'Submitting…' : 'Calculate Estimated Value'}
                <Icon name={isSubmitting ? 'refresh' : 'arrowRight'} size={17} />
              </button>
            </div>
          </form>

          <aside className="result-column">
            <div className={`result-card ${createdDevice ? 'result-card-visible' : ''}`}>
              <div className="result-card-header">
                <span className="icon-box"><Icon name="tag" size={21} /></span>
                <span className="result-badge">{createdDevice ? 'API result' : 'Awaiting submission'}</span>
              </div>
              <p className="eyebrow">Estimated value</p>
              <h2>{createdDevice ? 'Here is a starting point.' : 'Your result will appear here.'}</h2>
              {createdDevice ? (
                <>
                  <div className="result-device-row">
                    <div><span>Device</span><strong>{createdDevice.brand} {createdDevice.model}</strong></div>
                    <StatusBadge status={createdDevice.status} />
                  </div>
                  <div className="result-tracking-row">
                    <div><span>Tracking ID</span><strong>{createdDevice.tracking_id}</strong></div>
                    <Icon name="checkCircle" size={20} />
                  </div>
                  <div className="result-price-block"><span>Estimated purchase value</span><strong>{formatCurrency(createdDevice.estimated_purchase_value)}</strong></div>
                  <div className="result-method-row"><span>Valuation method</span><strong>{valuationMethodLabel(createdDevice.valuation_method)}</strong></div>
                  <div className="result-breakdown">
                    <div><span>Condition</span><strong>{createdDevice.condition}</strong></div>
                    <div><span>Potential refurbished value</span><strong>{formatCurrency(createdDevice.potential_refurbished_value)}</strong></div>
                    <div><span>Potential recycled value</span><strong>{formatCurrency(createdDevice.potential_recycled_value)}</strong></div>
                    <div><span>Current status</span><StatusBadge status={createdDevice.status} /></div>
                  </div>
                  <p className="result-factors">
                    Estimate is driven by: {[
                      createdDevice.device_category,
                      createdDevice.brand,
                      `${createdDevice.age} year${createdDevice.age === 1 ? '' : 's'} old`,
                      createdDevice.condition,
                      createdDevice.working_status,
                      createdDevice.physical_damage && createdDevice.physical_damage.toLowerCase() !== 'none'
                        ? createdDevice.physical_damage
                        : 'no physical damage',
                    ].filter(Boolean).join(' · ')}
                    {createdDevice.original_purchase_price ? ' · original purchase price' : ' · no purchase price given'}
                  </p>
                  <DemoNotice>Estimates are for demonstration only and are not a guaranteed transaction price. This is a demonstration ML pipeline trained on development data, not a representation of live market prices. If your device falls outside what the model was trained on, the rule-based estimator is used instead.</DemoNotice>
                  <div className="result-actions">
                    <button className="button button-primary button-full" onClick={() => navigate(`/track?id=${encodeURIComponent(createdDevice.tracking_id)}`)} type="button">Track this device <Icon name="arrowRight" size={17} /></button>
                    <button className="text-button" onClick={editDetails} type="button">Edit details</button>
                  </div>
                </>
              ) : (
                <div className="result-empty"><Icon name="spark" size={24} /><p>Submit the device details to receive a tracking ID and a rule-based/demo estimate from the API.</p></div>
              )}
            </div>
            <div className="side-tip"><Icon name="info" size={18} /><p><strong>What happens next?</strong> The device is stored with a tracking ID. If you are logged in, request collection for it from your dashboard.</p></div>
          </aside>
        </div>
      </section>
    </>
  )
}
