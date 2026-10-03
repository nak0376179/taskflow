import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from './api'
import type { Task, TaskInput } from './types'

const KEY = ['tasks']

/** MCP (Claude / Copilot) からの変更も拾えるよう、開いている間は定期的に取り直す */
export function useTasks() {
  return useQuery({ queryKey: KEY, queryFn: api.listTasks, refetchInterval: 10_000 })
}

export function useTaskMutations() {
  const qc = useQueryClient()
  const done = () => qc.invalidateQueries({ queryKey: KEY })

  const create = useMutation({
    mutationFn: (t: Partial<TaskInput> & { title: string }) => api.createTask(t),
    onSettled: done,
  })

  // ドラッグで状態を変えたときにカードがもたつかないよう、先に画面へ反映する
  const update = useMutation({
    mutationFn: ({ id, patch }: { id: string; patch: Partial<TaskInput> }) => api.updateTask(id, patch),
    onMutate: async ({ id, patch }) => {
      await qc.cancelQueries({ queryKey: KEY })
      const prev = qc.getQueryData<Task[]>(KEY)
      qc.setQueryData<Task[]>(KEY, (old) => old?.map((t) => (t.task_id === id ? { ...t, ...patch } : t)))
      return { prev }
    },
    onError: (_e, _v, ctx) => ctx?.prev && qc.setQueryData(KEY, ctx.prev),
    onSettled: done,
  })

  const remove = useMutation({
    mutationFn: (id: string) => api.deleteTask(id),
    onMutate: async (id) => {
      await qc.cancelQueries({ queryKey: KEY })
      const prev = qc.getQueryData<Task[]>(KEY)
      qc.setQueryData<Task[]>(KEY, (old) => old?.filter((t) => t.task_id !== id))
      return { prev }
    },
    onError: (_e, _v, ctx) => ctx?.prev && qc.setQueryData(KEY, ctx.prev),
    onSettled: done,
  })

  return { create, update, remove }
}
