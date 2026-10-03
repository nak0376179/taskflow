#!/usr/bin/env bash
# TaskFlow のローカル開発を一括で起動する (macOS / Linux / Windows の Git Bash 共通)。
#   Floci (Cognito + DynamoDB, 4568) → backend (8050, REST + MCP) → frontend (5189)
# テーブル・ユーザープール・開発用ユーザー (admin / admin) は backend の起動時に自動で作られる。
# Ctrl+C で backend と frontend を止める (Floci は残す。止めるなら `bash scripts/floci.sh down`)。
set -euo pipefail
cd "$(dirname "$0")/.."

export AWS_ENDPOINT_URL="${AWS_ENDPOINT_URL:-http://localhost:${FLOCI_PORT:-4568}}"
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

# Floci (コンテナ環境の選び方は scripts/floci.sh)。
# WSL の Ubuntu の docker を使うときだけ、VM がアイドルで止まってコンテナが道連れにならないよう keep-alive を張る
if [ "$(bash scripts/floci.sh runtime)" = wsl ]; then
  wsl.exe -d "${WSL_DISTRO:-Ubuntu}" -- sleep infinity &
  PIDS+=($!)
fi
bash scripts/floci.sh up

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
