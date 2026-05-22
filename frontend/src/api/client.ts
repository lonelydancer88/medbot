import type { CreateSessionResponse, ChatResponse, SessionData, StreamCallbacks } from '../types'

const BASE = '/api'

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${url}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

export function createSession(): Promise<CreateSessionResponse> {
  return request('/sessions', { method: 'POST' })
}

export function sendMessage(
  sessionId: string,
  text: string
): Promise<ChatResponse> {
  return request(`/sessions/${sessionId}/chat`, {
    method: 'POST',
    body: JSON.stringify({ text }),
  })
}

export function getSession(sessionId: string): Promise<SessionData> {
  return request(`/sessions/${sessionId}`)
}

export function listSessions(): Promise<{ sessions: SessionData[] }> {
  return request('/sessions')
}

function dispatchStreamEvent(
  eventType: string,
  rawData: string,
  callbacks: StreamCallbacks
): void {
  try {
    switch (eventType) {
      case 'thinking': {
        const delta = JSON.parse(rawData) as string
        if (delta) callbacks.onThinking(delta)
        break
      }
      case 'text': {
        const delta = JSON.parse(rawData) as string
        if (delta) callbacks.onText(delta)
        break
      }
      case 'done':
        callbacks.onDone(JSON.parse(rawData))
        break
      case 'diagnosis':
        callbacks.onDiagnosis(JSON.parse(rawData))
        break
      case 'phase':
        callbacks.onPhase(JSON.parse(rawData))
        break
      case 'medical_record':
        callbacks.onMedicalRecord(JSON.parse(rawData))
        break
      case 'error': {
        const msg = JSON.parse(rawData) as string
        callbacks.onError(msg)
        break
      }
    }
  } catch (e) {
    console.error('SSE event parse error:', eventType, rawData, e)
  }
}

export async function streamChat(
  sessionId: string,
  text: string,
  callbacks: StreamCallbacks
): Promise<void> {
  const response = await fetch(`${BASE}/sessions/${sessionId}/chat/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text }),
  })

  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new Error(body.detail || `HTTP ${response.status}`)
  }

  callbacks.onConnected()

  const reader = response.body?.getReader()
  if (!reader) throw new Error('ReadableStream not available')

  const decoder = new TextDecoder()
  let buffer = ''

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })

      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      let currentEvent = ''
      for (const line of lines) {
        if (line.startsWith('event: ')) {
          currentEvent = line.slice(7).trim()
        } else if (line.startsWith('data: ')) {
          dispatchStreamEvent(currentEvent, line.slice(6), callbacks)
          currentEvent = ''
        }
      }
    }
  } finally {
    reader.releaseLock()
  }
}
