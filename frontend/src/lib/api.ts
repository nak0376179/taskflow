import type { AuthConfig, IssuedToken, Session, Task, TaskInput, TokenInfo } from './types'

const SESSION_KEY = 'taskflow.session'

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

export function loadSession(): Session | null {
  try {
    const raw = localStorage.getItem(SESSION_KEY)
    return raw ? (JSON.parse(raw) as Session) : null
  } catch {
    return null
  }
}

function saveSession(s: Session | null) {
  try {
    if (s) localStorage.setItem(SESSION_KEY, JSON.stringify(s))
    else localStorage.removeItem(SESSION_KEY)
  } catch {
    // 保存できなくても、この画面を開いている間はメモリ上のセッションで動く
  }
}

let session: Session | null = loadSession()
const listeners = new Set<(s: Session | null) => void>()

export function onSessionChange(fn: (s: Session | null) => void): () => void {
  listeners.add(fn)
  return () => listeners.delete(fn)
}

export function setSession(s: Session | null) {
  session = s
  saveSession(s)
  listeners.forEach((fn) => fn(s))
}

async function errorOf(res: Response): Promise<ApiError> {
  let msg = `${res.status} ${res.statusText}`
  try {
    const body = await res.json()
    if (typeof body.detail === 'string') msg = body.detail
    else if (Array.isArray(body.detail)) msg = body.detail.map((d: { msg: string }) => d.msg).join(', ')
  } catch {
    // 本文が JSON でない
  }
  return new ApiError(res.status, msg)
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw await errorOf(res)
  return res.json()
}

let refreshing: Promise<boolean> | null = null

/** アクセストークン (1 時間) が切れたらリフレッシュトークンで取り直す。同時に複数走らせない */
function refreshSession(): Promise<boolean> {
  if (!refreshing) {
    const rt = session?.refresh_token
    refreshing = (async () => {
      if (!rt) return false
      try {
        setSession(await post<Session>('/api/auth/refresh', { refresh_token: rt }))
        return true
      } catch {
        return false
      }
    })().finally(() => {
      refreshing = null
    })
  }
  return refreshing
}

async function request<T>(method: string, path: string, body?: unknown, retry = true): Promise<T> {
  const headers: Record<string, string> = {}
  if (session) headers.Authorization = `Bearer ${session.access_token}`
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  const res = await fetch(path, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) })
  if (res.status === 401 && retry && session) {
    if (await refreshSession()) return request(method, path, body, false)
    setSession(null)
  }
  if (!res.ok) throw await errorOf(res)
  return (res.status === 204 ? undefined : await res.json()) as T
}

export const api = {
  authConfig: () => request<AuthConfig>('GET', '/api/auth/config'),
  login: async (username: string, password: string) => {
    const s = await post<Session>('/api/auth/login', { username, password })
    setSession(s)
    return s
  },
  logout: () => setSession(null),

  listTasks: () => request<Task[]>('GET', '/api/tasks'),
  createTask: (t: Partial<TaskInput> & { title: string }) => request<Task>('POST', '/api/tasks', t),
  updateTask: (id: string, t: Partial<TaskInput>) => request<Task>('PATCH', `/api/tasks/${id}`, t),
  deleteTask: (id: string) => request<void>('DELETE', `/api/tasks/${id}`),

  listTokens: () => request<TokenInfo[]>('GET', '/api/tokens'),
  issueToken: (name: string) => request<IssuedToken>('POST', '/api/tokens', { name }),
  revokeToken: (id: string) => request<void>('DELETE', `/api/tokens/${id}`),
}
