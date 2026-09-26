import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'

import { ApiError } from '../api/client.js'
import AuthLayout from '../components/AuthLayout.jsx'
import PasswordField from '../components/PasswordField.jsx'
import DemoNotice from '../components/DemoNotice.jsx'
import Icon from '../components/Icon.jsx'
import { useAuth } from '../context/AuthContext.jsx'

const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

export default function LoginPage() {
  const { login } = useAuth()
  const location = useLocation()
  const navigate = useNavigate()
  const [form, setForm] = useState({ email: '', password: '' })
  const [errors, setErrors] = useState({})
  const [message, setMessage] = useState(
    location.state?.registered
      ? 'Account created. Please log in to continue.'
      : location.state?.from
        ? 'Please log in to view your dashboard.'
        : '',
  )
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
    if (!form.email.trim()) {
      nextErrors.email = 'Please enter your email.'
    } else if (!emailPattern.test(form.email.trim())) {
      nextErrors.email = 'Enter a valid email address.'
    }
    if (!form.password) {
      nextErrors.password = 'Please enter your password.'
    }
    setErrors(nextErrors)
    if (Object.keys(nextErrors).length > 0) return

    setIsSubmitting(true)
    try {
      await login({ email: form.email.trim(), password: form.password })
      const destination = location.state?.from?.pathname || '/dashboard'
      navigate(destination, { replace: true })
    } catch (error) {
      setMessage(
        error instanceof ApiError
          ? error.message
          : 'Unable to log you in right now. Please try again.',
      )
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <AuthLayout eyebrow="Welcome back" title="Log in to SmartCycle" description="Your devices, pickups and outcomes live here." footerText="New to SmartCycle?" footerLink="Create an account" footerTo="/register">
      <form className="auth-form" onSubmit={handleSubmit} noValidate><label className="field"><span>Email</span><input autoComplete="email" name="email" onChange={updateField} placeholder="you@example.com" type="email" value={form.email} />{errors.email ? <small className="field-error">{errors.email}</small> : null}</label><PasswordField
          autoComplete="current-password"
          error={errors.password}
          label="Password"
          name="password"
          onChange={updateField}
          placeholder="Enter your password"
          value={form.password}
        /><button className="button button-primary button-full" disabled={isSubmitting} type="submit">{isSubmitting ? 'Logging in…' : 'Login'} {!isSubmitting ? <Icon name="arrowRight" size={17} /> : null}</button>{message ? <div className="auth-message" role="status"><Icon name="info" size={17} />{message}</div> : null}</form>
      <DemoNotice>Login is connected to the SmartCycle API. Passwords are hashed and never stored in plain text.</DemoNotice>
      <div className="auth-demo-link"><span>Want to explore the demo?</span><Link to="/">Back to home <Icon name="arrowUpRight" size={15} /></Link></div>
    </AuthLayout>
  )
}
