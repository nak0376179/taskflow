import {
  Alert,
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  IconButton,
  List,
  ListItem,
  ListItemText,
  Stack,
  Tab,
  Tabs,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material'
import ContentCopyIcon from '@mui/icons-material/ContentCopy'
import DeleteIcon from '@mui/icons-material/DeleteOutlined'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { api } from '../lib/api'
import type { IssuedToken } from '../lib/types'

function CopyBlock({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)
  return (
    <Box sx={{ position: 'relative' }}>
      <Box
        component="pre"
        sx={{
          m: 0,
          p: 1.5,
          pr: 5,
          bgcolor: 'action.hover',
          borderRadius: 1,
          fontSize: 12.5,
          overflowX: 'auto',
          whiteSpace: 'pre',
        }}
      >
        {text}
      </Box>
      <Tooltip title={copied ? 'コピーしました' : 'コピー'}>
        <IconButton
          size="small"
          sx={{ position: 'absolute', top: 4, right: 4 }}
          onClick={async () => {
            await navigator.clipboard.writeText(text)
            setCopied(true)
            setTimeout(() => setCopied(false), 1500)
          }}
        >
          <ContentCopyIcon fontSize="small" />
        </IconButton>
      </Tooltip>
    </Box>
  )
}

function snippets(url: string, token: string) {
  // PowerShell でもそのまま貼れるよう 1 行にする
  const claude = `claude mcp add --transport http taskflow ${url} --header "Authorization: Bearer ${token}"`
  const vscode = JSON.stringify(
    {
      inputs: [{ type: 'promptString', id: 'taskflow-token', description: 'TaskFlow のトークン', password: true }],
      servers: {
        taskflow: { type: 'http', url, headers: { Authorization: 'Bearer ${input:taskflow-token}' } },
      },
    },
    null,
    2,
  )
  return { claude, vscode }
}

export default function McpDialog({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient()
  const config = useQuery({ queryKey: ['auth-config'], queryFn: api.authConfig })
  const list = useQuery({ queryKey: ['tokens'], queryFn: api.listTokens })
  const [name, setName] = useState('Claude Code')
  const [issued, setIssued] = useState<IssuedToken | null>(null)
  const [tab, setTab] = useState(0)

  const issue = useMutation({
    mutationFn: () => api.issueToken(name),
    onSuccess: (t) => {
      setIssued(t)
      qc.invalidateQueries({ queryKey: ['tokens'] })
    },
  })
  const revoke = useMutation({
    mutationFn: (id: string) => api.revokeToken(id),
    onSettled: () => qc.invalidateQueries({ queryKey: ['tokens'] }),
  })

  const url = config.data?.mcp_url ?? `${location.protocol}//${location.hostname}:8050/mcp`
  const s = snippets(url, issued?.token ?? 'tfp_...')

  return (
    <Dialog open onClose={onClose} fullWidth maxWidth="md">
      <DialogTitle>MCP 連携 (Claude Code / GitHub Copilot)</DialogTitle>
      <DialogContent>
        <Stack spacing={2.5}>
          <Typography variant="body2" color="text.secondary">
            トークンを発行して MCP クライアントに登録すると、AI からこの画面と同じタスクを一覧・作成・更新・完了・削除できます。
            MCP の URL は <code>{url}</code> です。
          </Typography>

          <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}>
            <TextField
              size="small"
              label="トークンの名前 (用途)"
              value={name}
              onChange={(e) => setName(e.target.value)}
              sx={{ flex: 1 }}
            />
            <Button variant="contained" onClick={() => issue.mutate()} loading={issue.isPending}>
              発行
            </Button>
          </Stack>
          {issue.error && <Alert severity="error">{issue.error.message}</Alert>}

          {issued && (
            <Alert severity="success" variant="outlined">
              <Typography variant="body2" sx={{ mb: 1 }}>
                トークン「{issued.name}」を発行しました。<b>この画面を閉じると二度と表示されません。</b>
              </Typography>
              <CopyBlock text={issued.token} />
            </Alert>
          )}

          <Box>
            <Tabs value={tab} onChange={(_e, v) => setTab(v)} sx={{ mb: 1.5 }}>
              <Tab label="Claude Code" />
              <Tab label="GitHub Copilot (VS Code)" />
            </Tabs>
            {tab === 0 ? (
              <Stack spacing={1}>
                <Typography variant="body2">ターミナルで実行します (プロジェクトをまたいで使うなら <code>--scope user</code> を付ける)。</Typography>
                <CopyBlock text={s.claude} />
              </Stack>
            ) : (
              <Stack spacing={1}>
                <Typography variant="body2">
                  ワークスペースの <code>.vscode/mcp.json</code> に書き、Copilot Chat をエージェント モードにして使います。
                  トークンは初回起動時に VS Code が尋ねて、安全な場所に保存します。
                </Typography>
                <CopyBlock text={s.vscode} />
              </Stack>
            )}
          </Box>

          <Box>
            <Typography variant="subtitle2" sx={{ mb: 0.5 }}>
              発行済みのトークン
            </Typography>
            {list.data?.length === 0 && (
              <Typography variant="body2" color="text.secondary">
                まだありません
              </Typography>
            )}
            <List dense disablePadding>
              {list.data?.map((t) => (
                <ListItem
                  key={t.token_id}
                  divider
                  secondaryAction={
                    <Tooltip title="取り消す (このトークンの MCP クライアントは使えなくなります)">
                      <IconButton edge="end" onClick={() => revoke.mutate(t.token_id)} aria-label={`${t.name} を取り消す`}>
                        <DeleteIcon />
                      </IconButton>
                    </Tooltip>
                  }
                >
                  <ListItemText
                    primary={`${t.name}  (${t.hint}…)`}
                    secondary={`発行 ${new Date(t.created_at).toLocaleString()} ・ 最終利用 ${
                      t.last_used_at ? new Date(t.last_used_at).toLocaleString() : 'なし'
                    }`}
                  />
                </ListItem>
              ))}
            </List>
          </Box>
        </Stack>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>閉じる</Button>
      </DialogActions>
    </Dialog>
  )
}
