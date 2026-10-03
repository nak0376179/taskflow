import {
  Autocomplete,
  Button,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  MenuItem,
  Stack,
  TextField,
  Typography,
} from '@mui/material'
import DeleteIcon from '@mui/icons-material/DeleteOutlined'
import { useState, type FormEvent } from 'react'
import { PRIORITIES, STATUSES, type Status, type Task, type TaskInput } from '../lib/types'

interface Props {
  /** null なら新規 */
  task: Task | null
  initialStatus?: Status
  tagOptions: string[]
  onClose: () => void
  onSave: (input: TaskInput) => Promise<unknown>
  onDelete?: (t: Task) => void
}

function blank(status: Status): TaskInput {
  return { title: '', description: '', status, priority: 'medium', due_date: null, tags: [] }
}

export default function TaskDialog({ task, initialStatus = 'todo', tagOptions, onClose, onSave, onDelete }: Props) {
  const [form, setForm] = useState<TaskInput>(() =>
    task
      ? {
          title: task.title,
          description: task.description,
          status: task.status,
          priority: task.priority,
          due_date: task.due_date,
          tags: task.tags,
        }
      : blank(initialStatus),
  )
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const set = <K extends keyof TaskInput>(k: K, v: TaskInput[K]) => setForm((f) => ({ ...f, [k]: v }))

  async function submit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await onSave({ ...form, title: form.title.trim() })
      onClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog open onClose={onClose} fullWidth maxWidth="sm" slotProps={{ paper: { component: 'form', onSubmit: submit } }}>
      <DialogTitle>{task ? 'タスクを編集' : '新しいタスク'}</DialogTitle>
      <DialogContent>
        <Stack spacing={2.25} sx={{ pt: 1 }}>
          <TextField
            label="タイトル"
            value={form.title}
            onChange={(e) => set('title', e.target.value)}
            required
            autoFocus={!task}
            slotProps={{ htmlInput: { maxLength: 200 } }}
          />
          <TextField
            label="説明"
            value={form.description}
            onChange={(e) => set('description', e.target.value)}
            multiline
            minRows={3}
            maxRows={12}
          />
          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2}>
            <TextField
              select
              label="状態"
              value={form.status}
              onChange={(e) => set('status', e.target.value as Status)}
              fullWidth
            >
              {STATUSES.map((s) => (
                <MenuItem key={s.value} value={s.value}>
                  {s.label}
                </MenuItem>
              ))}
            </TextField>
            <TextField
              select
              label="優先度"
              value={form.priority}
              onChange={(e) => set('priority', e.target.value as TaskInput['priority'])}
              fullWidth
            >
              {PRIORITIES.map((p) => (
                <MenuItem key={p.value} value={p.value}>
                  {p.label}
                </MenuItem>
              ))}
            </TextField>
            <TextField
              label="期限"
              type="date"
              value={form.due_date ?? ''}
              onChange={(e) => set('due_date', e.target.value || null)}
              fullWidth
              slotProps={{ inputLabel: { shrink: true } }}
            />
          </Stack>
          <Autocomplete
            multiple
            freeSolo
            options={tagOptions}
            value={form.tags}
            onChange={(_e, v) => set('tags', [...new Set(v.map((t) => t.trim()).filter(Boolean))])}
            renderValue={(value, getItemProps) =>
              value.map((tag, index) => {
                const { key, ...rest } = getItemProps({ index })
                return <Chip key={key} label={tag} size="small" {...rest} />
              })
            }
            renderInput={(params) => <TextField {...params} label="タグ" placeholder="入力して Enter" />}
          />
          {task && (
            <Typography variant="caption" color="text.secondary">
              作成 {new Date(task.created_at).toLocaleString()}・更新 {new Date(task.updated_at).toLocaleString()}
              {task.completed_at && `・完了 ${new Date(task.completed_at).toLocaleString()}`}
            </Typography>
          )}
          {error && (
            <Typography color="error" variant="body2">
              {error}
            </Typography>
          )}
        </Stack>
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2 }}>
        {task && onDelete && (
          <Button color="error" startIcon={<DeleteIcon />} onClick={() => onDelete(task)} sx={{ mr: 'auto' }}>
            削除
          </Button>
        )}
        <Button onClick={onClose}>キャンセル</Button>
        <Button type="submit" variant="contained" loading={busy}>
          保存
        </Button>
      </DialogActions>
    </Dialog>
  )
}
