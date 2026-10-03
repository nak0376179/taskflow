import type { Priority, Status, Task } from './types'

const PRIORITY_RANK: Record<Priority, number> = { high: 0, medium: 1, low: 2 }

/** ローカル時刻の今日 (YYYY-MM-DD) */
export function today(now = new Date()): string {
  const p = (n: number) => String(n).padStart(2, '0')
  return `${now.getFullYear()}-${p(now.getMonth() + 1)}-${p(now.getDate())}`
}

function daysBetween(from: string, to: string): number {
  return Math.round((Date.parse(to) - Date.parse(from)) / 86_400_000)
}

export type DueTone = 'overdue' | 'today' | 'soon' | 'later'

/** 期限の表示 (「今日」「明日」「3日遅れ」「10/12」など) と色分け */
export function dueInfo(task: Pick<Task, 'due_date' | 'status'>, now = today()): { label: string; tone: DueTone } | null {
  if (!task.due_date) return null
  const d = daysBetween(now, task.due_date)
  const [, m, day] = task.due_date.split('-').map(Number)
  const md = `${m}/${day}`
  if (task.status === 'done') return { label: md, tone: 'later' }
  if (d < 0) return { label: `${md} (${-d}日遅れ)`, tone: 'overdue' }
  if (d === 0) return { label: '今日', tone: 'today' }
  if (d === 1) return { label: '明日', tone: 'soon' }
  if (d <= 7) return { label: `${md} (あと${d}日)`, tone: 'soon' }
  return { label: md, tone: 'later' }
}

/** 列の中の並び: 期限の近い順 (なしは後) → 優先度 → 作成順。完了の列は完了の新しい順 */
export function compareTasks(a: Task, b: Task): number {
  if (a.status === 'done' && b.status === 'done') {
    return (b.completed_at ?? '').localeCompare(a.completed_at ?? '')
  }
  if (!!a.due_date !== !!b.due_date) return a.due_date ? -1 : 1
  if (a.due_date && b.due_date && a.due_date !== b.due_date) return a.due_date.localeCompare(b.due_date)
  if (a.priority !== b.priority) return PRIORITY_RANK[a.priority] - PRIORITY_RANK[b.priority]
  return a.created_at.localeCompare(b.created_at)
}

export function groupByStatus(tasks: Task[]): Record<Status, Task[]> {
  const g: Record<Status, Task[]> = { todo: [], in_progress: [], done: [] }
  for (const t of tasks) g[t.status].push(t)
  for (const k of Object.keys(g) as Status[]) g[k].sort(compareTasks)
  return g
}

export function matches(task: Task, query: string, tag: string | null): boolean {
  if (tag && !task.tags.includes(tag)) return false
  const q = query.trim().toLowerCase()
  if (!q) return true
  return (
    task.title.toLowerCase().includes(q) ||
    task.description.toLowerCase().includes(q) ||
    task.tags.some((t) => t.toLowerCase().includes(q))
  )
}

export function allTags(tasks: Task[]): string[] {
  return [...new Set(tasks.flatMap((t) => t.tags))].sort((a, b) => a.localeCompare(b, 'ja'))
}
