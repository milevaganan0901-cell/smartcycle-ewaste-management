import { useState } from 'react'
import { Link } from 'react-router-dom'

import DemoNotice from '../components/DemoNotice.jsx'
import Icon from '../components/Icon.jsx'
import SectionHeading from '../components/SectionHeading.jsx'

const initialForm = { name: '', email: '', phone: '', message: '' }

export default function ContactPage() {
  const [form, setForm] = useState(initialForm)
  const [errors, setErrors] = useState({})
  const [submitted, setSubmitted] = useState(false)

  const updateField = (event) => {
    const { name, value } = event.target
    setForm((current) => ({ ...current, [name]: value }))
    setErrors((current) => ({ ...current, [name]: '' }))
    setSubmitted(false)
  }

  const validate = () => {
    const nextErrors = {}
    if (!form.name.trim()) nextErrors.name = 'Please enter your name.'
    if (!form.email.trim()) nextErrors.email = 'Please enter your email.'
    else if (!/^\S+@\S+\.\S+$/.test(form.email)) nextErrors.email = 'Please enter a valid email.'
    if (!form.phone.trim()) nextErrors.phone = 'Please enter your phone number.'
    if (!form.message.trim()) nextErrors.message = 'Please tell us how we can help.'
    return nextErrors
  }

  const handleSubmit = (event) => {
    event.preventDefault()
    const nextErrors = validate()
    setErrors(nextErrors)
    if (Object.keys(nextErrors).length === 0) {
      setSubmitted(true)
      setForm(initialForm)
    }
  }

  return (
    <>
      <section className="page-hero page-hero-contact"><div className="container page-hero-inner"><div><p className="eyebrow">Contact SmartCycle</p><h1>Let’s make the next step clearer.</h1><p>Have a question about a device, a pickup or the SmartCycle concept? Send a message and our future support flow will pick it up.</p></div><div className="page-hero-side-note"><Icon name="message" size={21} /><span><strong>We are listening.</strong><small>Questions are welcome before you submit a device.</small></span></div></div></section>

      <section className="section contact-section"><div className="container contact-layout"><div className="contact-intro"><SectionHeading eyebrow="Get in touch" title="A human conversation can go a long way." description="Tell us what you are trying to do and we can help point you in the right direction." /><div className="contact-methods"><div><span className="icon-box"><Icon name="mail" size={19} /></span><span><strong>Email</strong><small>hello@smartcycle.example</small></span></div><div><span className="icon-box"><Icon name="phone" size={19} /></span><span><strong>Phone</strong><small>+91 00000 00000</small></span></div><div><span className="icon-box"><Icon name="mapPin" size={19} /></span><span><strong>Coverage</strong><small>Demo service area: Bengaluru</small></span></div></div><DemoNotice>This form is frontend-only for now. Messages are not sent to a backend.</DemoNotice></div>
        <form className="form-card contact-form" noValidate onSubmit={handleSubmit}><div className="form-card-heading"><div><p className="eyebrow">Send a message</p><h2>How can we help?</h2></div><span className="form-step-label">Contact</span></div><div className="form-grid"><label className="field field-full"><span>Name</span><input aria-invalid={Boolean(errors.name)} name="name" onChange={updateField} placeholder="Your full name" value={form.name} />{errors.name ? <small className="field-error">{errors.name}</small> : null}</label><label className="field"><span>Email</span><input aria-invalid={Boolean(errors.email)} name="email" onChange={updateField} placeholder="you@example.com" type="email" value={form.email} />{errors.email ? <small className="field-error">{errors.email}</small> : null}</label><label className="field"><span>Phone</span><input aria-invalid={Boolean(errors.phone)} name="phone" onChange={updateField} placeholder="+91 00000 00000" type="tel" value={form.phone} />{errors.phone ? <small className="field-error">{errors.phone}</small> : null}</label><label className="field field-full"><span>Message</span><textarea aria-invalid={Boolean(errors.message)} name="message" onChange={updateField} placeholder="Tell us a little about your question..." rows="5" value={form.message} />{errors.message ? <small className="field-error">{errors.message}</small> : null}</label></div><div className="form-actions"><span className="form-required-note">All fields are required for this demo.</span><button className="button button-primary" type="submit">Send Message <Icon name="arrowRight" size={17} /></button></div>{submitted ? <div className="form-success" role="status"><Icon name="checkCircle" size={20} /><span><strong>Thanks — your demo message is ready.</strong><small>No message was sent because backend integration is not connected yet.</small></span></div> : null}</form></div></section>

      <section className="section section-tint contact-bottom"><div className="container contact-bottom-grid"><div><p className="eyebrow">Looking for a device?</p><h2>Start with the device flow.</h2><p>Explore a sample submission and see how a transparent estimate could work.</p><Link className="text-link" to="/sell">Sell a device <Icon name="arrowRight" size={16} /></Link></div><div className="contact-bottom-art"><Icon name="message" size={46} /><span>Questions welcome</span></div></div></section>
    </>
  )
}
