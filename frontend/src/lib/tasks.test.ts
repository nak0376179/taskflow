import { describe, expect, it } from 'vitest'
import { allTags, compareTasks, dueInfo, groupByStatus, matches, today } from './tasks'
import type { Task } from './types'

function task(p: Partial<Task>): Task {
  return {
    task_id: p.title ?? 'x',
    title: 'x',
    description: '',
    status: 'todo',
    priority: 'medium',
    due_date: null,
    tags: [],
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    completed_at: null,
    ...p,
  }
}

describe('today', () => {
  it('ローカル時刻で YYYY-MM-DD', () => {
    expect(today(new Date(2026, 0, 5, 23, 59))).toBe('2026-01-05')
  })
})

describe('dueInfo', () => {
  const now = '2026-10-03'
  it('期限なしは null', () => expect(dueInfo(task({}), now)).toBeNull())
  it('遅れ・今日・明日・1週間以内・先', () => {
    expect(dueInfo(task({ due_date: '2026-10-01' }), now)).toEqual({ label: '10/1 (2日遅れ)', tone: 'overdue' })
    expect(dueInfo(task({ due_date: '2026-10-03' }), now)?.tone).toBe('today')
    expect(dueInfo(task({ due_date: '2026-10-04' }), now)).toEqual({ label: '明日', tone: 'soon' })
    expect(dueInfo(task({ due_date: '2026-10-10' }), now)).toEqual({ label: '10/10 (あと7日)', tone: 'soon' })
    expect(dueInfo(task({ due_date: '2026-10-11' }), now)).toEqual({ label: '10/11', tone: 'later' })
  })
  it('完了したものは遅れ扱いしない', () => {
    expect(dueInfo(task({ due_date: '2026-09-01', status: 'done' }), now)?.tone).toBe('later')
  })
})

describe('compareTasks / groupByStatus', () => {
  it('期限の近い順 → 期限なし、同じなら優先度', () => {
    const a = task({ title: 'a', due_date: '2026-10-05', priority: 'low' })
    const b = task({ title: 'b', due_date: '2026-10-05', priority: 'high' })
    const c = task({ title: 'c', due_date: '2026-10-04' })
    const d = task({ title: 'd', priority: 'high' })
    expect([d, a, b, c].sort(compareTasks).map((t) => t.title)).toEqual(['c', 'b', 'a', 'd'])
  })
  it('完了は完了の新しい順', () => {
    const g = groupByStatus([
      task({ title: 'old', status: 'done', completed_at: '2026-01-01T00:00:00Z' }),
      task({ title: 'new', status: 'done', completed_at: '2026-02-01T00:00:00Z' }),
      task({ title: 't' }),
    ])
    expect(g.done.map((t) => t.title)).toEqual(['new', 'old'])
    expect(g.todo.map((t) => t.title)).toEqual(['t'])
    expect(g.in_progress).toEqual([])
  })
})

describe('matches / allTags', () => {
  const t = task({ title: 'Report', description: '月次の資料', tags: ['仕事'] })
  it('タイトル・説明・タグの部分一致 (大文字小文字を区別しない)', () => {
    expect(matches(t, 'report', null)).toBe(true)
    expect(matches(t, '資料', null)).toBe(true)
    expect(matches(t, '仕', null)).toBe(true)
    expect(matches(t, 'zzz', null)).toBe(false)
  })
  it('タグで絞る', () => {
    expect(matches(t, '', '仕事')).toBe(true)
    expect(matches(t, '', '家')).toBe(false)
  })
  it('タグの一覧は重複なし', () => {
    expect(allTags([t, task({ tags: ['仕事', 'A'] })])).toEqual(['A', '仕事'])
  })
})
