import { useEffect, useRef, useState } from 'react'

import { sendChatMessage } from '../api/client.js'
import Icon from './Icon.jsx'

const GREETING =
  "Hi! 👋 I'm the SmartCycle AI Assistant. How can I help you with e-waste recycling, device valuation, pickup, or tracking?"

const ERROR_MESSAGE =
  "Sorry, I couldn't connect to the AI assistant right now. Please try again."

// In-memory only. Nothing is written to localStorage and nothing is sent to a
// database, so a refresh starts a clean conversation and the assistant never
// holds anything about the visitor between sessions.
export default function ChatWidget() {
  const [isOpen, setIsOpen] = useState(false)
  const [messages, setMessages] = useState([{ id: 'greeting', role: 'assistant', text: GREETING }])
  const [draft, setDraft] = useState('')
  const [isSending, setIsSending] = useState(false)
  const [error, setError] = useState('')

  const transcriptRef = useRef(null)
  const inputRef = useRef(null)
  const nextId = useRef(0)

  // Keep the newest message in view as the conversation grows.
  useEffect(() => {
    const node = transcriptRef.current
    if (node) {
      node.scrollTop = node.scrollHeight
    }
  }, [messages, isSending])

  useEffect(() => {
    if (isOpen) {
      inputRef.current?.focus()
    }
  }, [isOpen])

  // Escape closes the panel, matching the dismiss affordance of the overlay
  // widgets already used in this app.
  useEffect(() => {
    if (!isOpen) return undefined

    const onKeyDown = (event) => {
      if (event.key === 'Escape') setIsOpen(false)
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [isOpen])

  const send = async (event) => {
    event?.preventDefault()
    const text = draft.trim()
    if (!text || isSending) return

    nextId.current += 1
    const userId = `user-${nextId.current}`
    const replyId = `assistant-${nextId.current}`

    setMessages((current) => [...current, { id: userId, role: 'user', text }])
    setDraft('')
    setError('')
    setIsSending(true)

    try {
      const body = await sendChatMessage(text)
      setMessages((current) => [...current, { id: replyId, role: 'assistant', text: body.response }])
    } catch {
      // The API client already reduced the cause to a readable sentence, so the
      // widget never has to interpret status codes or provider detail itself.
      setError(ERROR_MESSAGE)
    } finally {
      setIsSending(false)
    }
  }

  return (
    <div className="chat-widget">
      {isOpen ? (
        <section
          className="chat-panel"
          role="dialog"
          aria-label="SmartCycle AI Assistant"
        >
          <header className="chat-header">
            <span className="chat-header-title">
              <span className="chat-header-icon"><Icon name="spark" size={17} /></span>
              <span>
                <strong>SmartCycle AI Assistant</strong>
                <small>Ask about e-waste, valuation, pickup or tracking</small>
              </span>
            </span>
            <button
              className="chat-close"
              type="button"
              onClick={() => setIsOpen(false)}
              aria-label="Close the assistant"
            >
              <Icon name="close" size={17} />
            </button>
          </header>

          <div className="chat-transcript" ref={transcriptRef}>
            {messages.map((message) => (
              <p
                key={message.id}
                className={`chat-bubble chat-bubble-${message.role}`}
              >
                {message.text}
              </p>
            ))}

            {isSending ? (
              <p className="chat-typing" role="status">
                <span /><span /><span />
                <em>The assistant is typing…</em>
              </p>
            ) : null}

            {error ? (
              <p className="chat-error" role="alert">{error}</p>
            ) : null}
          </div>

          <form className="chat-composer" onSubmit={send}>
            <label className="sr-only" htmlFor="chat-message">Your message</label>
            <input
              id="chat-message"
              ref={inputRef}
              type="text"
              value={draft}
              maxLength={2000}
              placeholder="Ask about recycling, valuation or pickup…"
              autoComplete="off"
              onChange={(event) => setDraft(event.target.value)}
            />
            <button
              className="chat-send"
              type="submit"
              disabled={isSending || !draft.trim()}
              aria-label="Send message"
            >
              <Icon name="arrowRight" size={17} />
            </button>
          </form>
        </section>
      ) : null}

      <button
        className="chat-launcher"
        type="button"
        onClick={() => setIsOpen((current) => !current)}
        aria-expanded={isOpen}
        aria-label={isOpen ? 'Close the SmartCycle AI Assistant' : 'Open the SmartCycle AI Assistant'}
      >
        <Icon name={isOpen ? 'close' : 'message'} size={22} />
      </button>
    </div>
  )
}
