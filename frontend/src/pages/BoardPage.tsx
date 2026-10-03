import {
  Alert,
  AppBar,
  Avatar,
  Badge,
  Box,
  Button,
  Chip,
  CircularProgress,
  Divider,
  IconButton,
  InputAdornment,
  ListItemIcon,
  Menu,
  MenuItem,
  Paper,
  Snackbar,
  Stack,
  Tab,
  Tabs,
  TextField,
  Toolbar,
  Typography,
  useColorScheme,
  useMediaQuery,
  useTheme,
} from '@mui/material'
import AddIcon from '@mui/icons-material/Add'
import DarkModeIcon from '@mui/icons-material/DarkModeOutlined'
import HubIcon from '@mui/icons-material/HubOutlined'
import LightModeIcon from '@mui/icons-material/LightModeOutlined'
import LogoutIcon from '@mui/icons-material/Logout'
import SearchIcon from '@mui/icons-material/Search'
import TaskAltIcon from '@mui/icons-material/TaskAlt'
import { useMemo, useState } from 'react'
import McpDialog from '../components/McpDialog'
import TaskCard from '../components/TaskCard'
import TaskDialog from '../components/TaskDialog'
import { allTags, groupByStatus, matches, today } from '../lib/tasks'
import { STATUSES, type Status, type Task, type UserInfo } from '../lib/types'
import { useTaskMutations, useTasks } from '../lib/useTasks'

type Editing = { task: Task | null; status: Status } | null

function QuickAdd({ onAdd }: { onAdd: (title: string) => void }) {
  const [title, setTitle] = useState('')
  return (
    <TextField
      size="small"
      placeholder="＋ タスクを追加 (Enter)"
      value={title}
      onChange={(e) => setTitle(e.target.value)}
      onKeyDown={(e) => {
        if (e.key === 'Enter' && !e.nativeEvent.isComposing && title.trim()) {
          onAdd(title.trim())
          setTitle('')
        }
      }}
      fullWidth
      sx={{ '& .MuiInputBase-root': { bgcolor: 'background.paper' } }}
    />
  )
}

export default function BoardPage({ user, onLogout }: { user: UserInfo; onLogout: () => void }) {
  const theme = useTheme()
  const wide = useMediaQuery(theme.breakpoints.up('md'))
  const { mode, systemMode, setMode } = useColorScheme()
  const dark = (mode === 'system' ? systemMode : mode) === 'dark'

  const tasks = useTasks()
  const { create, update, remove } = useTaskMutations()
  const [query, setQuery] = useState('')
  const [tag, setTag] = useState<string | null>(null)
  const [editing, setEditing] = useState<Editing>(null)
  const [mcpOpen, setMcpOpen] = useState(false)
  const [menu, setMenu] = useState<HTMLElement | null>(null)
  const [mobileTab, setMobileTab] = useState<Status>('todo')
  const [dragOver, setDragOver] = useState<Status | null>(null)
  const [toast, setToast] = useState<string | null>(null)

  const all = useMemo(() => tasks.data ?? [], [tasks.data])
  const tags = useMemo(() => allTags(all), [all])
  const groups = useMemo(() => groupByStatus(all.filter((t) => matches(t, query, tag))), [all, query, tag])
  const overdue = all.filter((t) => t.status !== 'done' && t.due_date && t.due_date < today()).length

  const fail = (e: Error) => setToast(e.message)
  const setStatus = (t: Task, status: Status) => {
    if (t.status !== status) update.mutate({ id: t.task_id, patch: { status } }, { onError: fail })
  }
  const deleteTask = (t: Task) => {
    if (!confirm(`「${t.title}」を削除しますか?`)) return
    remove.mutate(t.task_id, { onError: fail })
    setEditing(null)
  }

  const column = (status: Status) => {
    const label = STATUSES.find((s) => s.value === status)!.label
    const items = groups[status]
    return (
      <Paper
        key={status}
        variant="outlined"
        onDragOver={(e) => {
          e.preventDefault()
          setDragOver(status)
        }}
        onDragLeave={() => setDragOver(null)}
        onDrop={(e) => {
          e.preventDefault()
          setDragOver(null)
          const id = e.dataTransfer.getData('text/x-task-id')
          const t = all.find((x) => x.task_id === id)
          if (t) setStatus(t, status)
        }}
        sx={{
          flex: 1,
          minWidth: 0,
          p: 1.5,
          bgcolor: dragOver === status ? 'action.selected' : 'action.hover',
          borderStyle: dragOver === status ? 'dashed' : 'solid',
          transition: 'background-color .15s',
        }}
      >
        {wide && (
          <Stack direction="row" sx={{ alignItems: 'center', mb: 1.5, px: 0.5 }}>
            <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>
              {label}
            </Typography>
            <Chip label={items.length} size="small" sx={{ ml: 1 }} />
          </Stack>
        )}
        <Stack spacing={1}>
          {status !== 'done' && (
            <QuickAdd onAdd={(title) => create.mutate({ title, status, tags: tag ? [tag] : [] }, { onError: fail })} />
          )}
          {items.map((t) => (
            <TaskCard
              key={t.task_id}
              task={t}
              onOpen={(task) => setEditing({ task, status: task.status })}
              onToggleDone={(task) => setStatus(task, task.status === 'done' ? 'todo' : 'done')}
              onTagClick={setTag}
            />
          ))}
          {items.length === 0 && (
            <Typography variant="body2" color="text.secondary" sx={{ textAlign: 'center', py: 3 }}>
              {query || tag ? '該当なし' : 'ここにドラッグ'}
            </Typography>
          )}
        </Stack>
      </Paper>
    )
  }

  return (
    <Box sx={{ minHeight: '100dvh', display: 'flex', flexDirection: 'column' }}>
      <AppBar position="sticky" color="inherit" elevation={0} sx={{ borderBottom: 1, borderColor: 'divider' }}>
        <Toolbar sx={{ gap: 1.5 }}>
          <TaskAltIcon color="primary" />
          <Typography variant="h6" sx={{ fontWeight: 700, display: { xs: 'none', sm: 'block' } }}>
            TaskFlow
          </Typography>
          <TextField
            size="small"
            placeholder="検索"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            sx={{ ml: { sm: 2 }, flex: 1, maxWidth: 420 }}
            slotProps={{
              input: {
                startAdornment: (
                  <InputAdornment position="start">
                    <SearchIcon fontSize="small" />
                  </InputAdornment>
                ),
              },
            }}
          />
          <Box sx={{ flex: 1 }} />
          <Button
            variant="contained"
            startIcon={<AddIcon />}
            onClick={() => setEditing({ task: null, status: wide ? 'todo' : mobileTab })}
            sx={{ display: { xs: 'none', sm: 'inline-flex' } }}
          >
            新規タスク
          </Button>
          <IconButton onClick={(e) => setMenu(e.currentTarget)} aria-label="メニュー">
            <Badge color="error" variant="dot" invisible={overdue === 0}>
              <Avatar sx={{ width: 32, height: 32, bgcolor: 'primary.main', fontSize: 15 }}>
                {(user.email || '?')[0].toUpperCase()}
              </Avatar>
            </Badge>
          </IconButton>
          <Menu anchorEl={menu} open={!!menu} onClose={() => setMenu(null)}>
            <MenuItem disabled>{user.email}</MenuItem>
            <Divider />
            <MenuItem
              onClick={() => {
                setMenu(null)
                setMcpOpen(true)
              }}
            >
              <ListItemIcon>
                <HubIcon fontSize="small" />
              </ListItemIcon>
              MCP 連携
            </MenuItem>
            <MenuItem onClick={() => setMode(dark ? 'light' : 'dark')}>
              <ListItemIcon>{dark ? <LightModeIcon fontSize="small" /> : <DarkModeIcon fontSize="small" />}</ListItemIcon>
              {dark ? 'ライトモード' : 'ダークモード'}
            </MenuItem>
            <MenuItem onClick={onLogout}>
              <ListItemIcon>
                <LogoutIcon fontSize="small" />
              </ListItemIcon>
              ログアウト
            </MenuItem>
          </Menu>
        </Toolbar>
      </AppBar>

      <Box sx={{ p: { xs: 1.5, md: 3 }, flex: 1, width: '100%', maxWidth: 1400, mx: 'auto' }}>
        <Stack direction="row" spacing={1} useFlexGap sx={{ mb: 2, flexWrap: 'wrap', alignItems: 'center' }}>
          {overdue > 0 && <Chip color="error" size="small" label={`期限切れ ${overdue} 件`} />}
          {tags.map((t) => (
            <Chip
              key={t}
              label={`#${t}`}
              size="small"
              color={tag === t ? 'primary' : 'default'}
              variant={tag === t ? 'filled' : 'outlined'}
              onClick={() => setTag(tag === t ? null : t)}
              onDelete={tag === t ? () => setTag(null) : undefined}
            />
          ))}
        </Stack>

        {tasks.isPending && (
          <Box sx={{ display: 'grid', placeItems: 'center', py: 8 }}>
            <CircularProgress />
          </Box>
        )}
        {tasks.error && <Alert severity="error">{tasks.error.message}</Alert>}

        {tasks.data &&
          (wide ? (
            <Stack direction="row" spacing={2} sx={{ alignItems: 'flex-start' }}>
              {STATUSES.map((s) => column(s.value))}
            </Stack>
          ) : (
            <>
              <Tabs value={mobileTab} onChange={(_e, v) => setMobileTab(v)} variant="fullWidth" sx={{ mb: 1 }}>
                {STATUSES.map((s) => (
                  <Tab key={s.value} value={s.value} label={`${s.label} ${groups[s.value].length}`} />
                ))}
              </Tabs>
              {column(mobileTab)}
            </>
          ))}
      </Box>

      {editing && (
        <TaskDialog
          key={editing.task?.task_id ?? 'new'}
          task={editing.task}
          initialStatus={editing.status}
          tagOptions={tags}
          onClose={() => setEditing(null)}
          onDelete={deleteTask}
          onSave={(input) =>
            editing.task
              ? update.mutateAsync({ id: editing.task.task_id, patch: input })
              : create.mutateAsync(input)
          }
        />
      )}
      {mcpOpen && <McpDialog onClose={() => setMcpOpen(false)} />}
      <Snackbar open={!!toast} autoHideDuration={4000} onClose={() => setToast(null)}>
        <Alert severity="error" onClose={() => setToast(null)}>
          {toast}
        </Alert>
      </Snackbar>
    </Box>
  )
}
