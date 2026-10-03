import { Alert, Box, Button, Card, CardContent, Stack, TextField, Typography } from '@mui/material'
import TaskAltIcon from '@mui/icons-material/TaskAlt'
import { useQuery } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { api } from '../lib/api'

export default function LoginPage() {
  const config = useQuery({ queryKey: ['auth-config'], queryFn: api.authConfig })
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function submit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await api.login(username, password)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Box sx={{ minHeight: '100dvh', display: 'grid', placeItems: 'center', p: 2 }}>
      <Card sx={{ width: '100%', maxWidth: 380 }} variant="outlined">
        <CardContent sx={{ p: 4 }}>
          <Stack component="form" spacing={2.5} onSubmit={submit}>
            <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}>
              <TaskAltIcon color="primary" fontSize="large" />
              <Typography variant="h5" sx={{ fontWeight: 700 }}>
                TaskFlow
              </Typography>
            </Stack>
            {config.data?.dev_login && (
              <Alert severity="info" variant="outlined">
                ローカル環境です。<b>admin / admin</b> でログインできます。
              </Alert>
            )}
            <TextField
              label="メールアドレス"
              autoComplete="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              autoFocus
            />
            <TextField
              label="パスワード"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
            {error && <Alert severity="error">{error}</Alert>}
            <Button type="submit" variant="contained" size="large" loading={busy}>
              ログイン
            </Button>
          </Stack>
        </CardContent>
      </Card>
    </Box>
  )
}
