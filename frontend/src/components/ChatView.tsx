import { useState, useRef, useEffect, useCallback } from 'react'
import { createSession, getSession, streamChat } from '../api/client'
import type { Message, Diagnosis, StreamDoneData, StreamDiagnosisData, StreamPhaseData, StreamMedicalRecordData } from '../types'
import { MessageBubble } from './MessageBubble'
import { DiagnosisCard } from './DiagnosisCard'
import { MedicalRecordCard } from './MedicalRecordCard'

interface Props {
  sessionId: string | null
  onSessionChange: (id: string) => void
  onBack: () => void
}

export function ChatView({ sessionId, onSessionChange, onBack }: Props) {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [phase, setPhase] = useState('collecting')
  const [diagnoses, setDiagnoses] = useState<Diagnosis[]>([])
  const [medicalRecord, setMedicalRecord] = useState('')
  const [initializing, setInitializing] = useState(!sessionId)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  // Initialize session if needed
  useEffect(() => {
    if (sessionId) {
      // Load existing session
      setInitializing(true)
      getSession(sessionId)
        .then((data) => {
          setMessages(data.messages || [])
          setPhase(data.phase)
          setDiagnoses(data.diagnoses || [])
          setMedicalRecord(data.medical_record || '')
        })
        .catch(console.error)
        .finally(() => setInitializing(false))
    } else {
      // Create new session
      setInitializing(true)
      createSession()
        .then((data) => {
          onSessionChange(data.session_id)
          setMessages([{ role: 'ai', content: data.reply, thinking: data.thinking }])
          setPhase(data.phase)
        })
        .catch(console.error)
        .finally(() => setInitializing(false))
    }
  }, [sessionId])

  // Auto scroll
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSend = useCallback(async () => {
    const text = input.trim()
    if (!text || loading || !sessionId) return

    setInput('')
    const userMsg: Message = { role: 'patient', content: text }
    setMessages((prev) => [...prev, userMsg])

    // Add placeholder for streaming AI response
    const placeholder: Message = { role: 'ai', content: '', thinking: '' }
    setMessages((prev) => [...prev, placeholder])
    setLoading(true)

    try {
      await streamChat(sessionId, text, {
        onThinking: (delta: string) => {
          setMessages((prev) => {
            const updated = [...prev]
            const last = updated[updated.length - 1]
            updated[updated.length - 1] = {
              ...last,
              thinking: (last.thinking || '') + delta,
            }
            return updated
          })
        },

        onText: (delta: string) => {
          setMessages((prev) => {
            const updated = [...prev]
            const last = updated[updated.length - 1]
            updated[updated.length - 1] = {
              ...last,
              content: (last.content || '') + delta,
            }
            return updated
          })
        },

        onDone: (data: StreamDoneData) => {
          setMessages((prev) => {
            const updated = [...prev]
            const last = updated[updated.length - 1]
            updated[updated.length - 1] = {
              ...last,
              content: data.text,
              thinking: data.thinking,
            }
            return updated
          })
        },

        onDiagnosis: (data: StreamDiagnosisData) => {
          if (data.diagnoses && data.diagnoses.length > 0) {
            setDiagnoses(data.diagnoses)
          }
          if (data.content) {
            setMessages((prev) => [...prev, {
              role: 'ai',
              content: data.content,
            }])
          }
        },

        onMedicalRecord: (data: StreamMedicalRecordData) => {
          if (data.content) {
            setMedicalRecord(data.content)
          }
        },

        onPhase: (data: StreamPhaseData) => {
          setPhase(data.phase)
          setLoading(false)
        },

        onError: (error: string) => {
          setMessages((prev) => {
            const updated = [...prev]
            updated[updated.length - 1] = {
              role: 'ai',
              content: `抱歉，出现错误：${error}`,
            }
            return updated
          })
          setLoading(false)
        },

        onConnected: () => {},
      })
    } catch (err: unknown) {
      setMessages((prev) => {
        const updated = [...prev]
        updated[updated.length - 1] = {
          role: 'ai',
          content: `错误：${err instanceof Error ? err.message : '请求失败'}`,
        }
        return updated
      })
      setLoading(false)
    }
  }, [input, loading, sessionId])

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const handleNewSession = () => {
    setMessages([])
    setDiagnoses([])
    setMedicalRecord('')
    setPhase('collecting')
    setInitializing(true)
    createSession()
      .then((data) => {
        onSessionChange(data.session_id)
        setMessages([{ role: 'ai', content: data.reply, thinking: data.thinking }])
        setPhase(data.phase)
      })
      .catch(console.error)
      .finally(() => setInitializing(false))
  }

  if (initializing) {
    return (
      <div
        style={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          height: '80vh',
          color: '#6b7280',
        }}
      >
        连接中...
      </div>
    )
  }

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100vh',
        maxWidth: '680px',
        margin: '0 auto',
      }}
    >
      {/* Header */}
      <div
        style={{
          padding: '16px 20px',
          borderBottom: '1px solid #e5e7eb',
          display: 'flex',
          alignItems: 'center',
          gap: '12px',
          background: '#fff',
        }}
      >
        <button
          onClick={onBack}
          style={{
            padding: '6px 12px',
            border: '1px solid #d1d5db',
            borderRadius: '6px',
            background: '#fff',
            cursor: 'pointer',
            fontSize: '13px',
          }}
        >
          ← 历史
        </button>
        <h1 style={{ margin: 0, fontSize: '18px', fontWeight: 600 }}>
          问诊助手
        </h1>
        {phase === 'complete' ? (
          <span
            style={{
              marginLeft: 'auto',
              fontSize: '12px',
              padding: '2px 8px',
              borderRadius: '4px',
              background: '#dcfce7',
              color: '#166534',
            }}
          >
            已完成
          </span>
        ) : (
          <span
            style={{
              marginLeft: 'auto',
              fontSize: '12px',
              padding: '2px 8px',
              borderRadius: '4px',
              background: '#fef3c7',
              color: '#92400e',
            }}
          >
            问诊中
          </span>
        )}
      </div>

      {/* Messages */}
      <div
        style={{
          flex: 1,
          overflowY: 'auto',
          padding: '20px',
          background: '#f9fafb',
        }}
      >
        {messages.map((msg, i) => (
          <MessageBubble
            key={i}
            message={msg}
            isStreaming={loading && i === messages.length - 1 && msg.role === 'ai'}
          />
        ))}

        <div ref={messagesEndRef} />

        {/* Diagnosis Card */}
        {diagnoses.length > 0 && (
          <DiagnosisCard
            diagnoses={diagnoses}
            onNewSession={handleNewSession}
          />
        )}

        {/* Medical Record Card */}
        {medicalRecord && (
          <MedicalRecordCard content={medicalRecord} />
        )}
      </div>

      {/* Input */}
      {phase !== 'complete' && (
        <div
          style={{
            padding: '16px 20px',
            borderTop: '1px solid #e5e7eb',
            display: 'flex',
            gap: '10px',
            background: '#fff',
          }}
        >
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="描述您的症状..."
            disabled={loading}
            style={{
              flex: 1,
              padding: '12px 16px',
              border: '1px solid #d1d5db',
              borderRadius: '8px',
              fontSize: '15px',
              outline: 'none',
            }}
          />
          <button
            onClick={handleSend}
            disabled={loading || !input.trim()}
            style={{
              padding: '12px 24px',
              background: loading || !input.trim() ? '#93c5fd' : '#2563eb',
              color: '#fff',
              border: 'none',
              borderRadius: '8px',
              cursor: loading || !input.trim() ? 'not-allowed' : 'pointer',
              fontSize: '15px',
              fontWeight: 500,
            }}
          >
            发送
          </button>
        </div>
      )}
    </div>
  )
}
