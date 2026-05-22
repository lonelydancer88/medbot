import { useState } from 'react'
import type { Message } from '../types'

interface Props {
  message: Message
  isStreaming?: boolean
}

export function MessageBubble({ message, isStreaming }: Props) {
  const isAi = message.role === 'ai'
  const [thinkingExpanded, setThinkingExpanded] = useState(true)
  const hasThinking = isAi && message.thinking && message.thinking.trim().length > 0
  const hasContent = message.content.trim().length > 0
  const effectiveExpanded = isStreaming ? hasThinking : thinkingExpanded

  return (
    <div
      style={{
        display: 'flex',
        justifyContent: isAi ? 'flex-start' : 'flex-end',
        marginBottom: '16px',
      }}
    >
      <div style={{ maxWidth: '75%' }}>
        {/* Thinking section */}
        {hasThinking && (
          <div style={{ marginBottom: '4px' }}>
            <button
              onClick={() => isStreaming ? null : setThinkingExpanded(!thinkingExpanded)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
                padding: '4px 10px',
                border: 'none',
                borderRadius: '6px',
                background: '#fef3c7',
                color: '#92400e',
                fontSize: '12px',
                cursor: isStreaming ? 'default' : 'pointer',
                fontWeight: 500,
              }}
            >
              <span>{effectiveExpanded ? '▼' : '▶'}</span>
              <span>思考过程{isStreaming ? '...' : ''}</span>
            </button>
            {effectiveExpanded && (
              <div
                style={{
                  marginTop: '4px',
                  padding: '10px 12px',
                  borderRadius: '8px',
                  background: '#fffbeb',
                  border: '1px solid #fde68a',
                  color: '#78350f',
                  fontSize: '13px',
                  lineHeight: 1.5,
                  whiteSpace: 'pre-wrap',
                }}
              >
                {message.thinking}
              </div>
            )}
          </div>
        )}

        {/* Main message — show even if empty during streaming */}
        {(hasContent || isStreaming) && (
          <div
            style={{
              padding: '12px 16px',
              borderRadius: '12px',
              background: isAi ? '#f0f4f8' : '#2563eb',
              color: isAi ? '#1a202c' : '#fff',
              lineHeight: 1.6,
              whiteSpace: 'pre-wrap',
              fontSize: '15px',
            }}
          >
            {hasContent ? message.content : (
              <span style={{ color: '#9ca3af' }}>...</span>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
