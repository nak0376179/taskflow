#!/usr/bin/env bash
# TaskFlow のローカル開発を一括で起動する (Git Bash / macOS 共通)。
#   Floci (Cognito + DynamoDB, 4568) → backend (8050, REST + MCP) → frontend (5189)
# テーブル・ユーザープール・開発用ユーザー (admin / admin) は backend の起動時に自動で作られる。
# Ctrl+C で backend と frontend を止める (Floci は残す。止めるなら `docker compose down` / `wslc stop taskflow-floci`)。
set -euo pipefail
cd "$(dirname "$0")/.."

export AWS_ENDPOINT_URL="${AWS_ENDPOINT_URL:-http://localhost:4568}"
export AWS_ACCESS_KEY_ID="${AWS_ACCESS_KEY_ID:-test}"
export AWS_SECRET_ACCESS_KEY="${AWS_SECRET_ACCESS_KEY:-test}"
export AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-ap-northeast-1}"
API_PORT="${API_PORT:-8050}"
WEB_PORT="${WEB_PORT:-5189}"

PIDS=()
cleanup() {
  for pid in "${PIDS[@]:-}"; do kill "$pid" 2>/dev/null || true; done
}
trap cleanup EXIT INT TERM

# Floci を動かすコンテナ環境は、見つかった順に
#   1. docker (Docker Desktop / Linux / macOS)       → docker-compose.yml
#   2. wslc (Windows の WSL コンテナ。WSL 3.0 以降)  → compose が無いので同じ設定を run で渡す
#   3. WSL の Ubuntu の中の docker                    → docker-compose.yml
WSLC="$(command -v wslc 2>/dev/null || true)"
[ -z "$WSLC" ] && [ -x "/c/Program Files/WSL/wslc.exe" ] && WSLC="/c/Program Files/WSL/wslc.exe"

compose_up() { # docker コマンド...
  # WSL の VM が起動した直後は docker デーモンの iptables の準備が間に合わず、
  # compose のネットワーク作成が失敗することがあるので、少し待って何度か試す
  until "$@" info >/dev/null 2>&1; do sleep 1; done
  for i in 1 2 3 4 5; do
    "$@" compose up -d && return 0
    echo "docker compose up を再試行します ($i)"; sleep 3
  done
  echo "docker compose up に失敗しました" >&2; exit 1
}

if command -v docker >/dev/null 2>&1; then
  compose_up docker
elif [ -n "$WSLC" ]; then
  # docker-compose.yml と同じ設定。名前付きボリュームは run が無ければ作る。
  # WSL の VM と違い、アイドルで止まらないので keep-alive は要らない
  echo "wslc で Floci を起動します"
  if "$WSLC" inspect taskflow-floci >/dev/null 2>&1; then
    "$WSLC" start taskflow-floci >/dev/null
  else
    "$WSLC" run -d --name taskflow-floci -p 4568:4566 \
      -e FLOCI_BASE_URL=http://localhost:4568 -e FLOCI_STORAGE_MODE=persistent \
      -v taskflow-floci-data:/app/data floci/floci:latest >/dev/null
  fi
else
  # WSL の VM はアイドルで止まりコンテナも道連れになるので、実行中は keep-alive を張る
  echo "docker が無いため WSL (Ubuntu) の docker を使います"
  wsl.exe -d Ubuntu -- sleep infinity &
  PIDS+=($!)
  compose_up wsl.exe -d Ubuntu docker
fi
echo "Floci を待っています ($AWS_ENDPOINT_URL) ..."
until curl -s -o /dev/null "$AWS_ENDPOINT_URL"; do sleep 0.5; done

# --reload は付けない (Windows では reload の子プロセスが親を止めても残り、ポートを握り続けることがある)
(cd backend && PYTHONUNBUFFERED=1 exec uv run uvicorn app.main:app --port "$API_PORT") &
PIDS+=($!)
(cd frontend && VITE_PROXY_TARGET="http://localhost:$API_PORT" exec pnpm dev --port "$WEB_PORT") &
PIDS+=($!)

echo ""
echo "  画面   : http://localhost:$WEB_PORT  (admin / admin)"
echo "  API    : http://localhost:$API_PORT/docs"
echo "  MCP    : http://localhost:$API_PORT/mcp"
echo "  Ctrl+C で停止"
wait
