# TaskFlow — AI 向けメモ

使い方と構成は [README.md](README.md)。ここは触るときの要点だけ。**public リポジトリなので、絶対パス・ホスト名・秘密情報をコミットしない。**

## 構成

- `backend/app/` (パッケージ `app`、`uvicorn app.main:app`)
  - `tasks.py` — タスクの保存・取得。**REST (`api.py`) と MCP (`mcp_server.py`) はどちらもここを通す**。項目を足すときは `TaskCreate` / `TaskUpdate` / `Task`、MCP の `create_task` / `update_task` の引数、frontend の `lib/types.ts` を揃える
  - `auth.py` — Cognito のログイン (USER_PASSWORD_AUTH をバックエンドが代行) と Bearer の検証 (Cognito アクセストークン or `tfp_` の個人トークン)。admin/admin の読み替え (`resolve_dev_login`) もここ
  - `tokens.py` — MCP 用の個人トークン。平文は保存しない (SHA-256)
  - `bootstrap.py` — 起動時。ローカル (AWS_ENDPOINT_URL あり) ならテーブル・プール・クライアント・開発用ユーザーを冪等に作る
  - `main.py` — FastAPI に FastMCP の http_app をルート (`/`) にマウント。FastAPI のルートが先に一致する。lifespan は `combine_lifespans` で両方回す
- `frontend/src/` — React + MUI v9 + TanStack Query。`lib/api.ts` がセッション (localStorage) と 401 時のリフレッシュを持つ。`/api` は Vite のプロキシで backend へ
- ポート: frontend 5189 / backend 8050 / Floci 4568 (他プロジェクトの Floci 4566・4567 と同時に動かせるようにずらしている)

## 注意

- **Floci の JWT の `iss` は `FLOCI_BASE_URL` から作られる**。scripts/floci.sh で `http://localhost:4568` にしてあり、backend は `AWS_ENDPOINT_URL/<pool>` を期待する。ポートを変えるときは両方直す (ずれると全リクエストが 401)
- Floci は `FLOCI_STORAGE_MODE=persistent` + ボリュームでデータを残している。プールを作り直すと sub が変わり、既存のタスクの持ち主が見つからなくなる (タスクは sub で持つ)
- FastMCP は 4.x。`fastmcp.server.auth.TokenVerifier` を継承して `verify_token` で検証し、ツールの中では `get_access_token().claims["sub"]` で持ち主を取る
- **Floci の起動設定は scripts/floci.sh の 1 か所だけ** (docker / podman / wslc / WSL の docker で同じ `run` を使う。wslc に compose が無いので compose ファイルは置かない)。macOS 標準の bash 3.2 でも動くように書く (連想配列・`${x,,}`・mapfile を使わない)
- uvicorn に `--reload` を付けない (Windows で子プロセスがポートを握ったまま残ることがある)

## 検証

```sh
cd backend && uv run pytest && uv run ruff check . && uv run ruff format --check .
cd frontend && pnpm typecheck && pnpm test && pnpm lint && pnpm build
cd backend && uv run python scripts/mcp_smoke.py   # 起動中のサーバに対して (ログイン → トークン発行 → MCP 一通り → 取り消し)
```
