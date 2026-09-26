import { useId, useState } from 'react'

import Icon from './Icon.jsx'

/**
 * Password input with a show/hide toggle.
 *
 * Stage 4C addition. It only changes how the field renders - the value, the
 * `name`, the `autoComplete` hint and every validation rule stay exactly as the
 * page defines them, so no authentication logic is affected.
 *
 * The toggle is a real button, so it is keyboard reachable and announces its
 * current state, and it never steals focus from the field on toggle.
 */
export default function PasswordField({
  label,
  name,
  value,
  onChange,
  autoComplete = 'current-password',
  placeholder,
  error,
  hint,
}) {
  const [revealed, setRevealed] = useState(false)
  const inputId = useId()
  const errorId = `${inputId}-error`
  const hintId = `${inputId}-hint`

  const describedBy = [error ? errorId : null, hint ? hintId : null]
    .filter(Boolean)
    .join(' ')

  return (
    <label className="field" htmlFor={inputId}>
      <span>{label}</span>
      <div className="input-with-icon input-with-action">
        <input
          aria-describedby={describedBy || undefined}
          aria-invalid={error ? true : undefined}
          autoComplete={autoComplete}
          id={inputId}
          name={name}
          onChange={onChange}
          placeholder={placeholder}
          type={revealed ? 'text' : 'password'}
          value={value}
        />
        <button
          aria-controls={inputId}
          aria-label={revealed ? `Hide ${label.toLowerCase()}` : `Show ${label.toLowerCase()}`}
          aria-pressed={revealed}
          className="password-toggle"
          onClick={() => setRevealed((current) => !current)}
          tabIndex={-1}
          type="button"
        >
          <Icon name={revealed ? 'eyeOff' : 'eye'} size={17} />
        </button>
      </div>
      {hint && !error ? <small className="field-hint" id={hintId}>{hint}</small> : null}
      {error ? <small className="field-error" id={errorId}>{error}</small> : null}
    </label>
  )
}
