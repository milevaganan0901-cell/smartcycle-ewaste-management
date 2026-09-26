import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { ApiError } from '../api/client.js'
import AuthLayout from '../components/AuthLayout.jsx'
import PasswordField from '../components/PasswordField.jsx'
import DemoNotice from '../components/DemoNotice.jsx'
import Icon from '../components/Icon.jsx'
import { useAuth } from '../context/AuthContext.jsx'

const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

const serverFieldMessages = {
  name: 'Please enter your name.',
  email: 'Enter a valid email address.',
  password: 'Use at least 8 characters.',
  confirm_password: 'Passwords do not match.',
}

function mapServerErrors(error) {
  if (!(error instanceof ApiError)) return null
  if (!error.body || !Array.isArray(error.body.detail)) return null

  const fieldNames = {
    name: 'name',
    email: 'email',
    password: 'password',
    confirm_password: 'confirmPassword',
  }
  const mapped = {}

  error.body.detail.forEach((item) => {
    const field = Array.isArray(item?.loc) ? item.loc[item.loc.length - 1] : null
    const target = fieldNames[field]
    if (target && !mapped[target]) {
      mapped[target] = serverFieldMessages[field]
    }
  })

  return Object.keys(mapped).length > 0 ? mapped : null
}

export default function RegisterPage() {
  const { register } = useAuth()
  const navigate = useNavigate()
  const [form, setForm] = useState({ name: '', email: '', password: '', confirmPassword: '' })
  const [errors, setErrors] = useState({})
  const [message, setMessage] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)

  const updateField = (event) => {
    const { name, value } = event.target
    setForm((current) => ({ ...current, [name]: value }))
    setErrors((current) => ({ ...current, [name]: '' }))
    setMessage('')
  }

  const handleSubmit = async (event) => {
    event.preventDefault()

    const nextErrors = {}
    if (!form.name.trim()) nextErrors.name = 'Please enter your name.'
    if (!form.email.trim()) {
      nextErrors.email = 'Please enter your email.'
    } else if (!emailPattern.test(form.email.trim())) {
      nextErrors.email = 'Enter a valid email address.'
    }
    if (!form.password) {
      nextErrors.password = 'Please enter a password.'
    } else if (form.password.length < 8) {
      nextErrors.password = 'Use at least 8 characters.'
    }
    if (!form.confirmPassword) {
      nextErrors.confirmPassword = 'Repeat your password.'
    } else if (form.password !== form.confirmPassword) {
      nextErrors.confirmPassword = 'Passwords do not match.'
    }
    setErrors(nextErrors)
    if (Object.keys(nextErrors).length > 0) return

    setIsSubmitting(true)
    try {
      await register({
        name: form.name.trim(),
        email: form.email.trim(),
        password: form.password,
        confirm_password: form.confirmPassword,
      })
      navigate('/login', { replace: true, state: { registered: true } })
    } catch (error) {
      const fieldErrors = mapServerErrors(error)
      if (fieldErrors) {
        setErrors(fieldErrors)
      } else if (error instanceof ApiError) {
        if (error.status === 400) {
          setErrors({ email: error.message })
        } else {
          setMessage(error.message)
        }
      } else {
        setMessage('Unable to create your account right now. Please try again.')
      }
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <AuthLayout eyebrow="Get started" title="Create your SmartCycle account" description="Save your device journey in one place." footerText="Already have an account?" footerLink="Log in" footerTo="/login">
      <form className="auth-form" noValidate onSubmit={handleSubmit}><label className="field"><span>Name</span><input autoComplete="name" name="name" onChange={updateField} placeholder="Your full name" value={form.name} />{errors.name ? <small className="field-error">{errors.name}</small> : null}</label><label className="field"><span>Email</span><input autoComplete="email" name="email" onChange={updateField} placeholder="you@example.com" type="email" value={form.email} />{errors.email ? <small className="field-error">{errors.email}</small> : null}</label><PasswordField
          autoComplete="new-password"
          error={errors.password}
          hint="Use at least 8 characters."
          label="Password"
          name="password"
          onChange={updateField}
          placeholder="At least 8 characters"
          value={form.password}
        /><PasswordField
          autoComplete="new-password"
          error={errors.confirmPassword}
          label="Confirm password"
          name="confirmPassword"
          onChange={updateField}
          placeholder="Repeat your password"
          value={form.confirmPassword}
        /><button className="button button-primary button-full" disabled={isSubmitting} type="submit">{isSubmitting ? 'Creating account…' : 'Create account'} {!isSubmitting ? <Icon name="arrowRight" size={17} /> : null}</button>{message ? <div className="auth-message" role="alert"><Icon name="info" size={17} />{message}</div> : null}</form>
      <DemoNotice>Registration creates a real SmartCycle account. Your password is hashed before it is stored.</DemoNotice>
      <div className="auth-demo-link"><span>Prefer to look around first?</span><Link to="/">Back to home <Icon name="arrowUpRight" size={15} /></Link></div>
    </AuthLayout>
  )
}
