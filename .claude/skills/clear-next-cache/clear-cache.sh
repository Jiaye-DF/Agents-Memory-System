#!/usr/bin/env bash
# 清除前端 Next.js / Turbopack 的 build cache
# 對應 docs/Tasks/v1.1/fixed.md §5 Turbopack 404 修法

set -euo pipefail

# ── 1. 找到 repo 根目錄（含 frontend/ 與 docker-compose.dev.yml）─────────
find_repo_root() {
  local dir="$PWD"
  while [[ "$dir" != "/" && "$dir" != "" ]]; do
    if [[ -d "$dir/frontend" && -f "$dir/docker-compose.dev.yml" ]]; then
      echo "$dir"
      return 0
    fi
    dir="$(dirname "$dir")"
  done
  return 1
}

REPO_ROOT="$(find_repo_root || true)"
if [[ -z "$REPO_ROOT" ]]; then
  echo "❌ 找不到含 frontend/ 與 docker-compose.dev.yml 的 repo 根目錄" >&2
  echo "   請在 Agents-Memory-System 任意子目錄執行" >&2
  exit 1
fi
cd "$REPO_ROOT"

COMPOSE_FILE="docker-compose.dev.yml"
SERVICE="frontend"
NEXT_DIR="frontend/.next"
TSBUILD="frontend/tsconfig.tsbuildinfo"

echo "📂 Repo: $REPO_ROOT"

# ── 2. 偵測 frontend container 狀態 ────────────────────────────────────
container_running=false
if command -v docker >/dev/null 2>&1; then
  if docker compose -f "$COMPOSE_FILE" ps --status running --services 2>/dev/null | grep -qx "$SERVICE"; then
    container_running=true
  fi
fi

# ── 3. 若 container 在跑，先停（避免 next dev 還活著時 .next 被刪 → ENOENT log race）
if $container_running; then
  echo "🛑 先停 $SERVICE container（避免 next dev process 寫 log 時 .next 已消失）"
  docker compose -f "$COMPOSE_FILE" stop "$SERVICE" >/dev/null
fi

# ── 4. 清除 cache（一律從 host 清；frontend bind mount 即 host frontend/）─
cleared=()

if [[ -d "$NEXT_DIR" ]]; then
  rm -rf "$NEXT_DIR"
  cleared+=("host:.next")
fi

if [[ -f "$TSBUILD" ]]; then
  rm -f "$TSBUILD"
  cleared+=("host:tsconfig.tsbuildinfo")
fi

# ── 5. 若先前 container 在跑，重新啟動 ────────────────────────────────
if $container_running; then
  echo "▶️  重新啟動 $SERVICE container"
  docker compose -f "$COMPOSE_FILE" start "$SERVICE" >/dev/null
fi

# ── 6. 摘要 ────────────────────────────────────────────────────────────
echo ""
if [[ ${#cleared[@]} -eq 0 ]]; then
  echo "ℹ️  沒有 cache 需要清除（已乾淨）"
else
  echo "✅ 已清除："
  for item in "${cleared[@]}"; do
    echo "   - $item"
  done
  echo ""
  if $container_running; then
    echo "⏳ 下一步：等 next dev 在 container 重新編譯（首次編譯較慢，正常）"
  else
    echo "⏳ 下一步：執行 docker compose -f $COMPOSE_FILE up frontend 啟動，或本機 npm run dev"
  fi
fi