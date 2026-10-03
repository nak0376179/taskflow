#!/usr/bin/env bash
# Floci (ローカルの Cognito + DynamoDB) を動かす。macOS / Linux / Windows (Git Bash) 共通。
#
#   bash scripts/floci.sh up       # 起動 (無ければ作る) して応答するまで待つ
#   bash scripts/floci.sh down     # 止める (データは残る)
#   bash scripts/floci.sh status   # 使うコンテナ環境と状態
#   bash scripts/floci.sh logs     # ログ
#   bash scripts/floci.sh reset    # コンテナとデータを消す (次の up で作り直し)
#   bash scripts/floci.sh runtime  # 使うコンテナ環境の名前だけ
#
# Floci 本体はコンテナでしか配られていないので、docker 互換の環境が要る。見つかった順に使う:
#   docker  … Docker Desktop / OrbStack / Colima (macOS)、Docker Engine (Linux)
#   podman  … Podman (Linux、macOS は podman machine)
#   wslc    … Windows の WSL コンテナ (WSL 3.0 以降)
#   wsl     … Windows で WSL の Ubuntu の中の docker
# FLOCI_RUNTIME=docker|podman|wslc|wsl で固定もできる。
#
# macOS 標準の bash 3.2 でも動くように書くこと (連想配列・${x,,}・mapfile を使わない)。
set -euo pipefail

NAME="${FLOCI_CONTAINER:-taskflow-floci}"
VOLUME="${FLOCI_VOLUME:-taskflow-floci-data}"
IMAGE=docker.io/floci/floci:latest
HOST_PORT="${FLOCI_PORT:-4568}"
ENDPOINT="http://localhost:$HOST_PORT"

die() { echo "floci.sh: $*" >&2; exit 1; }

wslc_path() {
  if command -v wslc >/dev/null 2>&1; then command -v wslc
  elif [ -x "/c/Program Files/WSL/wslc.exe" ]; then echo "/c/Program Files/WSL/wslc.exe"
  fi
}

detect_runtime() {
  if [ -n "${FLOCI_RUNTIME:-}" ]; then echo "$FLOCI_RUNTIME"; return; fi
  if command -v docker >/dev/null 2>&1; then echo docker; return; fi
  if command -v podman >/dev/null 2>&1; then echo podman; return; fi
  if [ -n "$(wslc_path)" ]; then echo wslc; return; fi
  if command -v wsl.exe >/dev/null 2>&1; then echo wsl; return; fi
  echo none
}

RUNTIME="$(detect_runtime)"

# 選んだコンテナ環境の CLI を呼ぶ
c() {
  case "$RUNTIME" in
    docker) docker "$@" ;;
    podman) podman "$@" ;;
    wslc) "$(wslc_path)" "$@" ;;
    wsl) MSYS_NO_PATHCONV=1 wsl.exe -d "${WSL_DISTRO:-Ubuntu}" docker "$@" ;;
    *) die "不明なコンテナ環境: $RUNTIME" ;;
  esac
}

no_runtime_help() {
  cat >&2 <<'EOF'
floci.sh: コンテナ環境が見つかりません。Floci はコンテナで動くので、次のどれかを入れてください。
  macOS  : OrbStack (brew install orbstack) / Docker Desktop / Colima (brew install colima docker && colima start)
  Linux  : Docker Engine (https://docs.docker.com/engine/install/) または Podman (sudo apt install podman など)
  Windows: wsl --update で WSL 3.0 以降にすると wslc が使える
EOF
  exit 1
}

# デーモンに届くか。届かなければ OS ごとの直し方を出して止める (無限に待たない)
ensure_daemon() {
  [ "$RUNTIME" = none ] && no_runtime_help
  [ "$RUNTIME" = wslc ] && return 0 # wslc はセッションを自動で立てる
  local i
  for i in $(seq 1 30); do
    c info >/dev/null 2>&1 && return 0
    # WSL の VM は起動直後しばらく docker が応答しないので待つ。それ以外はすぐ判断する
    [ "$RUNTIME" = wsl ] || break
    sleep 1
  done
  local err
  err="$(c info 2>&1 >/dev/null | tail -1 || true)"
  echo "floci.sh: $RUNTIME のデーモンに接続できません: $err" >&2
  case "$(uname -s)" in
    Darwin)
      if [ "$RUNTIME" = podman ]; then echo "  → podman machine start" >&2
      else echo "  → Docker Desktop / OrbStack を起動する (Colima なら colima start)" >&2; fi ;;
    Linux)
      if [ "$RUNTIME" = podman ]; then echo "  → rootless なら systemctl --user start podman.socket" >&2
      elif printf '%s' "$err" | grep -qi "permission denied"; then
        echo "  → このユーザーが docker グループに入っていない: sudo usermod -aG docker \$USER のあと再ログイン" >&2
      else echo "  → sudo systemctl start docker" >&2; fi ;;
    *) echo "  → Docker Desktop を起動する。WSL の docker なら wsl -d Ubuntu で一度入る" >&2 ;;
  esac
  exit 1
}

exists() { c inspect "$NAME" >/dev/null 2>&1; }

wait_ready() {
  local i
  for i in $(seq 1 120); do
    curl -s -o /dev/null "$ENDPOINT" && return 0
    sleep 0.5
  done
  die "Floci が $ENDPOINT で応答しません (bash scripts/floci.sh logs で確認)"
}

up() {
  ensure_daemon
  if exists; then
    c start "$NAME" >/dev/null
  else
    echo "Floci のコンテナを作ります ($RUNTIME, $IMAGE)"
    # 127.0.0.1 にだけ出す (Linux の docker は既定で LAN にも公開してしまう)。
    # FLOCI_BASE_URL はホスト側の URL。Cognito の JWT の iss になり、backend の検証と一致させる
    c run -d --name "$NAME" \
      -p "127.0.0.1:$HOST_PORT:4566" \
      -e "FLOCI_BASE_URL=$ENDPOINT" \
      -e FLOCI_STORAGE_MODE=persistent \
      -v "$VOLUME:/app/data" \
      "$IMAGE" >/dev/null
  fi
  wait_ready
  echo "Floci: $ENDPOINT ($RUNTIME)"
}

case "${1:-up}" in
  up) up ;;
  down) ensure_daemon; c stop "$NAME" >/dev/null 2>&1 || true; echo "stopped" ;;
  status)
    echo "runtime: $RUNTIME"
    ensure_daemon
    if exists; then c inspect -f '{{.State.Status}}' "$NAME" 2>/dev/null || c inspect "$NAME" | grep -m1 -i '"status"'
    else echo "container: なし"; fi
    if curl -s -o /dev/null "$ENDPOINT"; then echo "endpoint: $ENDPOINT -> 応答あり"
    else echo "endpoint: $ENDPOINT -> 応答なし"; fi
    ;;
  logs) ensure_daemon; c logs "$NAME" ;;
  reset)
    ensure_daemon
    c rm -f "$NAME" >/dev/null 2>&1 || { c stop "$NAME" >/dev/null 2>&1 || true; c remove "$NAME" >/dev/null 2>&1 || true; }
    c volume rm "$VOLUME" >/dev/null 2>&1 || c volume remove "$VOLUME" >/dev/null 2>&1 || true
    echo "removed $NAME and $VOLUME"
    ;;
  runtime) echo "$RUNTIME" ;;
  *) die "使い方: floci.sh up|down|status|logs|reset|runtime" ;;
esac
