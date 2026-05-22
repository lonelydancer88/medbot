import { useState, useEffect, useCallback } from 'react'
import { ChatView } from './components/ChatView'
import { SessionList } from './components/SessionList'

type View = 'chat' | 'history'

function parseUrl(): { view: View; sessionId: string | null } {
  const path = window.location.pathname
  if (path === '/sessions' || path === '/sessions/') {
    return { view: 'history', sessionId: null }
  }
  const match = path.match(/^\/sessions\/([a-f0-9-]+)$/)
  if (match) {
    return { view: 'chat', sessionId: match[1] }
  }
  return { view: 'chat', sessionId: null }
}

function navigateUrl(view: View, sessionId: string | null) {
  const url = view === 'history'
    ? '/sessions'
    : sessionId
      ? `/sessions/${sessionId}`
      : '/'
  window.history.pushState({}, '', url)
}

export default function App() {
  const [{ view, sessionId }, setRoute] = useState(parseUrl)

  // Sync URL changes (browser back/forward)
  useEffect(() => {
    const handler = () => setRoute(parseUrl())
    window.addEventListener('popstate', handler)
    return () => window.removeEventListener('popstate', handler)
  }, [])

  const navigate = useCallback((v: View, sid: string | null) => {
    navigateUrl(v, sid)
    setRoute({ view: v, sessionId: sid })
  }, [])

  return (
    <div style={{ background: '#f9fafb', minHeight: '100vh' }}>
      {view === 'chat' ? (
        <ChatView
          key={sessionId || 'new'}
          sessionId={sessionId}
          onSessionChange={(id) => navigate('chat', id)}
          onBack={() => navigate('history', null)}
        />
      ) : (
        <SessionList
          onSelect={(id) => navigate('chat', id)}
          onBack={() => navigate('chat', null)}
        />
      )}
    </div>
  )
}
