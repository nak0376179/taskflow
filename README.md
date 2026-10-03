# TaskFlow

個人用のタスク管理アプリ。ブラウザの画面からだけでなく、**Claude Code や GitHub Copilot から MCP でタスクを操作できる**。

- フロントエンド: React + MUI (Vite, TypeScript)
- バックエンド: FastAPI (REST `/api`) + FastMCP (MCP `/mcp`、Streamable HTTP) を 1 プロセスで
- 認証: Amazon Cognito (ユーザー名はメールアドレス)
- データ: Amazon DynamoDB
- ローカル: [Floci](https://hub.docker.com/r/floci/floci) で Cognito と DynamoDB をエミュレート

```
ブラウザ (React/MUI) ──/api──┐
                             ├─ FastAPI + FastMCP ── DynamoDB (タスク・MCP トークン)
Claude Code / Copilot ─/mcp──┘          │
                                         └──────── Cognito (ログイン・JWT の検証)
```

## 動かす (ローカル)

必要なもの: Docker (Windows で docker が無ければ WSL の Ubuntu の docker を使う)、[uv](https://docs.astral.sh/uv/)、Node.js + pnpm

```sh
(cd backend && uv sync)
(cd frontend && pnpm install)
bash scripts/dev.sh
```

- 画面: http://localhost:5189 — **ローカルでは `admin` / `admin` でログインできる**
- API: http://localhost:8050/docs
- MCP: http://localhost:8050/mcp

初回起動時に、バックエンドが Floci の中にテーブル・ユーザープール・アプリクライアント・開発用ユーザー (`admin@example.com`) とサンプルのタスクを作る。Floci のデータは docker のボリュームに残る (消すときは `docker compose down -v`)。

### admin / admin について

本来のログイン ID はメールアドレスで、Cognito のパスワードポリシーもかかる。ローカルでの確認を楽にするため、**`AWS_ENDPOINT_URL` が設定されている (= Floci に向いている) ときだけ**、バックエンドが `admin` / `admin` を開発用ユーザーのメールアドレスとパスワードに読み替えてから Cognito に問い合わせる。Cognito を迂回するわけではないので、発行されるのは本物の JWT。本番 (エンドポイント未設定) ではこの読み替えは働かない。

## MCP で使う

1. 画面右上のメニュー →「MCP 連携」でトークン (`tfp_...`) を発行する。平文はこのときしか表示されない
2. クライアントに登録する

**Claude Code**

```sh
claude mcp add --transport http taskflow http://localhost:8050/mcp --header "Authorization: Bearer tfp_..."
```

このリポジトリで Claude Code を開く場合は、同梱の [.mcp.json](.mcp.json) が環境変数 `TASKFLOW_TOKEN` を読むので、それを設定しておけばよい。

**GitHub Copilot (VS Code)**

同梱の [.vscode/mcp.json](.vscode/mcp.json) をそのまま (他のワークスペースならコピーして) 使う。初回の起動時にトークンを尋ねられる。Copilot Chat をエージェント モードにすると taskflow のツールが使える。

### ツール

| ツール | 内容 |
|---|---|
| `list_tasks` | 一覧 (状態・タグ・キーワードで絞る。既定は未完了のみ) |
| `get_task` | 1 件を説明まで含めて |
| `create_task` | 作成 |
| `update_task` | 指定した項目だけ書き換え (`clear_due_date` で期限を消す) |
| `complete_task` | 完了にする |
| `delete_task` | 削除 |
| `task_summary` | 状態ごとの件数と期限切れの件数 |

画面は 10 秒ごとに取り直すので、MCP で変えた内容はそのまま画面にも出る。

### トークンの扱い

- MCP 用のトークンは長期の鍵なので、DynamoDB には SHA-256 だけを置く。取り消しは「MCP 連携」画面から
- トークンで新しいトークンは発行できない (画面からログインしたときだけ)
- `/mcp` は Cognito のアクセストークンも受け付ける

## 本番 (AWS) で動かすとき

`AWS_ENDPOINT_URL` を設定しなければ本番扱いになり、起動時の自動作成と admin/admin は無効になる。次を用意して環境変数で渡す。

| 環境変数 | 内容 |
|---|---|
| `COGNITO_USER_POOL_ID` / `COGNITO_CLIENT_ID` | ユーザープール (ユーザー名 = メールアドレス) と、シークレットなし・`ALLOW_USER_PASSWORD_AUTH` + `ALLOW_REFRESH_TOKEN_AUTH` のアプリクライアント |
| `TASKS_TABLE` | PK `owner_id` (S) / SK `task_id` (S)。既定 `TaskflowTasks` |
| `TOKENS_TABLE` | PK `token_hash` (S)、GSI `owner_index` (PK `owner_id`、ALL)。既定 `TaskflowTokens` |
| `PUBLIC_BASE_URL` | このサーバの外向きの URL (MCP の保護リソースのメタデータに出る) |
| `CORS_ORIGINS` | 画面のオリジン (JSON の配列) |

## 開発

```sh
cd backend && uv run pytest && uv run ruff check .     # moto で DynamoDB をモック
cd frontend && pnpm typecheck && pnpm test && pnpm lint
cd backend && uv run python scripts/mcp_smoke.py        # 起動中のサーバの /mcp を MCP クライアントで一通り叩く
```
