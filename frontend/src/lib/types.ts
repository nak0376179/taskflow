export type Status = 'todo' | 'in_progress' | 'done'
export type Priority = 'low' | 'medium' | 'high'

export interface Task {
  task_id: string
  title: string
  description: string
  status: Status
  priority: Priority
  due_date: string | null // YYYY-MM-DD
  tags: string[]
  created_at: string
  updated_at: string
  completed_at: string | null
}

export type TaskInput = Pick<Task, 'title' | 'description' | 'status' | 'priority' | 'due_date' | 'tags'>

export interface UserInfo {
  sub: string
  email: string
}

export interface Session {
  access_token: string
  id_token: string
  refresh_token: string | null
  expires_in: number
  user: UserInfo
}

export interface AuthConfig {
  dev_login: boolean
  mcp_url: string
}

export interface TokenInfo {
  token_id: string
  name: string
  hint: string
  created_at: string
  last_used_at: string | null
}

export interface IssuedToken extends TokenInfo {
  token: string
}

export const STATUSES: { value: Status; label: string }[] = [
  { value: 'todo', label: '未着手' },
  { value: 'in_progress', label: '進行中' },
  { value: 'done', label: '完了' },
]

export const PRIORITIES: { value: Priority; label: string; color: 'default' | 'warning' | 'error' }[] = [
  { value: 'high', label: '高', color: 'error' },
  { value: 'medium', label: '中', color: 'warning' },
  { value: 'low', label: '低', color: 'default' },
]
