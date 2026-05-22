import { useEffect, useState } from 'react'
import { listSessions } from '../api/client'
import type { SessionData } from '../types'

interface Props {
  onSelect: (id: string) => void
  onBack: () => void
}

export function SessionList({ onSelect, onBack }: Props) {
  const [sessions, setSessions] = useState<SessionData[]>([])
  const [loading, setLoading] = useState(true)
  const [copiedId, setCopiedId] = useState<string | null>(null)

  useEffect(() => {
    listSessions()
      .then((data) => setSessions(data.sessions))
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  const copyLink = (e: React.MouseEvent, sessionId: string) => {
    e.stopPropagation()
    const url = `${window.location.origin}/sessions/${sessionId}`
    navigator.clipboard.writeText(url).then(() => {
      setCopiedId(sessionId)
      setTimeout(() => setCopiedId(null), 2000)
    }).catch(() => {
      // Fallback
      const input = document.createElement('input')
      input.value = url
      document.body.appendChild(input)
      input.select()
      document.execCommand('copy')
      document.body.removeChild(input)
      setCopiedId(sessionId)
      setTimeout(() => setCopiedId(null), 2000)
    })
  }

  return (
    <div style={{ maxWidth: '600px', margin: '0 auto', padding: '20px' }}>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '12px',
          marginBottom: '24px',
        }}
      >
        <button
          onClick={onBack}
          style={{
            padding: '8px 16px',
            border: '1px solid #d1d5db',
            borderRadius: '8px',
            background: '#fff',
            cursor: 'pointer',
          }}
        >
          ← 返回
        </button>
        <h2 style={{ margin: 0 }}>历史问诊记录</h2>
      </div>

      {loading && <p style={{ color: '#6b7280' }}>加载中...</p>}

      {!loading && sessions.length === 0 && (
        <div style={{ color: '#6b7280', textAlign: 'center', marginTop: '40px' }}>
          <p>暂无问诊记录</p>
          <p style={{ fontSize: '14px' }}>
            开始一次新的问诊，完成后可在此查看和分享
          </p>
          <button
            onClick={onBack}
            style={{
              marginTop: '12px',
              padding: '10px 24px',
              background: '#2563eb',
              color: '#fff',
              border: 'none',
              borderRadius: '8px',
              cursor: 'pointer',
              fontSize: '14px',
            }}
          >
            开始问诊
          </button>
        </div>
      )}

      {sessions.map((s) => (
        <div
          key={s.session_id}
          onClick={() => onSelect(s.session_id)}
          style={{
            padding: '16px',
            marginBottom: '12px',
            border: '1px solid #e5e7eb',
            borderRadius: '10px',
            cursor: 'pointer',
            background: '#fff',
            transition: 'box-shadow 0.15s',
          }}
        >
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              marginBottom: '8px',
            }}
          >
            <span
              style={{
                padding: '2px 8px',
                borderRadius: '4px',
                fontSize: '12px',
                background:
                  s.status === 'completed' ? '#dcfce7' : '#fef3c7',
                color:
                  s.status === 'completed' ? '#166534' : '#92400e',
              }}
            >
              {s.status === 'completed' ? '已完成' : '进行中'}
            </span>
            <span style={{ fontSize: '13px', color: '#9ca3af' }}>
              {s.created_at
                ? new Date(s.created_at).toLocaleString('zh-CN')
                : ''}
            </span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span
              style={{
                fontSize: '12px',
                color: '#6b7280',
                fontFamily: 'monospace',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
              }}
            >
              /sessions/{s.session_id.slice(0, 8)}...
            </span>
            <button
              onClick={(e) => copyLink(e, s.session_id)}
              style={{
                fontSize: '11px',
                padding: '2px 8px',
                border: '1px solid #d1d5db',
                borderRadius: '4px',
                background: copiedId === s.session_id ? '#dcfce7' : '#fff',
                color: copiedId === s.session_id ? '#166534' : '#6b7280',
                cursor: 'pointer',
                marginLeft: 'auto',
              }}
            >
              {copiedId === s.session_id ? '已复制 ✓' : '复制链接'}
            </button>
          </div>
        </div>
      ))}
    </div>
  )
}
