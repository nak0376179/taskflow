import { useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { api, loadSession, onSessionChange } from './lib/api'
import type { Session } from './lib/types'
import BoardPage from './pages/BoardPage'
import LoginPage from './pages/LoginPage'

export default function App() {
  const [session, setSession] = useState<Session | null>(loadSession)
  const qc = useQueryClient()

  useEffect(
    () =>
      onSessionChange((s) => {
        setSession(s)
        if (!s) qc.clear()
      }),
    [qc],
  )

  if (!session) return <LoginPage />
  return <BoardPage user={session.user} onLogout={api.logout} />
}
