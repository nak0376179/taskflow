import { Box, Card, CardActionArea, Checkbox, Chip, Stack, Tooltip, Typography } from '@mui/material'
import EventIcon from '@mui/icons-material/EventOutlined'
import NotesIcon from '@mui/icons-material/NotesOutlined'
import { dueInfo, type DueTone } from '../lib/tasks'
import { PRIORITIES, type Task } from '../lib/types'

const TONE_COLOR: Record<DueTone, 'error' | 'warning' | 'info' | 'default'> = {
  overdue: 'error',
  today: 'warning',
  soon: 'info',
  later: 'default',
}

interface Props {
  task: Task
  onOpen: (t: Task) => void
  onToggleDone: (t: Task) => void
  onTagClick: (tag: string) => void
}

export default function TaskCard({ task, onOpen, onToggleDone, onTagClick }: Props) {
  const due = dueInfo(task)
  const pr = PRIORITIES.find((p) => p.value === task.priority)!
  const done = task.status === 'done'

  return (
    <Card
      variant="outlined"
      draggable
      onDragStart={(e) => {
        e.dataTransfer.setData('text/x-task-id', task.task_id)
        e.dataTransfer.effectAllowed = 'move'
      }}
      sx={{
        cursor: 'grab',
        opacity: done ? 0.7 : 1,
        borderLeft: 4,
        borderLeftColor: task.priority === 'high' ? 'error.main' : task.priority === 'medium' ? 'warning.main' : 'divider',
        '&:active': { cursor: 'grabbing' },
      }}
    >
      <Stack direction="row" sx={{ alignItems: 'flex-start' }}>
        <Tooltip title={done ? '未完了に戻す' : '完了にする'}>
          <Checkbox
            checked={done}
            onChange={() => onToggleDone(task)}
            size="small"
            sx={{ mt: 0.5, ml: 0.5 }}
            slotProps={{ input: { 'aria-label': `${task.title} を完了にする` } }}
          />
        </Tooltip>
        <CardActionArea onClick={() => onOpen(task)} sx={{ p: 1.25, pl: 0.5, minWidth: 0 }}>
          <Typography
            variant="body2"
            sx={{ fontWeight: 600, textDecoration: done ? 'line-through' : 'none', wordBreak: 'break-word' }}
          >
            {task.title}
          </Typography>
          <Stack direction="row" spacing={0.75} useFlexGap sx={{ mt: 0.75, flexWrap: 'wrap', alignItems: 'center' }}>
            <Chip label={`優先度 ${pr.label}`} size="small" color={pr.color} variant="outlined" />
            {due && (
              <Chip
                icon={<EventIcon />}
                label={due.label}
                size="small"
                color={TONE_COLOR[due.tone]}
                variant={due.tone === 'overdue' || due.tone === 'today' ? 'filled' : 'outlined'}
              />
            )}
            {task.description && (
              <Tooltip title="説明あり">
                <NotesIcon fontSize="small" color="action" />
              </Tooltip>
            )}
            {task.tags.map((tag) => (
              <Box
                key={tag}
                component="span"
                role="button"
                tabIndex={0}
                onClick={(e) => {
                  e.stopPropagation()
                  onTagClick(tag)
                }}
                onMouseDown={(e) => e.stopPropagation()}
                sx={{ fontSize: 12, color: 'primary.main', '&:hover': { textDecoration: 'underline' } }}
              >
                #{tag}
              </Box>
            ))}
          </Stack>
        </CardActionArea>
      </Stack>
    </Card>
  )
}
