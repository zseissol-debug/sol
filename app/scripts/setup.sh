#!/usr/bin/env bash
# 安装 / 更新：后端环境、前端依赖、固定版本的开源引擎（版本见 scripts/engines.lock）。
#
#   scripts/setup.sh              后端 + 前端 + 两个引擎（不含本地转写）
#   scripts/setup.sh --full       再装本地转写（Apple 芯片用 mlx-whisper，体积大，第一次用还会下载模型）
#   scripts/setup.sh --daily-only 只装日报引擎
set -euo pipefail
cd "$(dirname "$0")/.."

FULL=0
DAILY_ONLY=0
for arg in "$@"; do
  case "$arg" in
    --full) FULL=1 ;;
    --daily-only) DAILY_ONLY=1 ;;
    *) echo "未知参数：$arg"; exit 2 ;;
  esac
done

lock() { awk -v n="$1" '$1==n {print $2, $3}' scripts/engines.lock; }

clone_engine() { # name
  local name="$1" url sha dir
  read -r url sha < <(lock "$name")
  dir="engines/$name"
  mkdir -p engines
  [ -d "$dir/.git" ] || git clone --quiet "$url" "$dir"
  git -C "$dir" fetch --quiet origin "$sha" 2>/dev/null || true
  git -C "$dir" checkout --quiet "$sha"
  echo "✓ $name @ ${sha:0:10}"
}

setup_daily() {
  clone_engine daily-newsletter
  local dir=engines/daily-newsletter
  [ -x "$dir/.venv/bin/python" ] || python3 -m venv "$dir/.venv"
  "$dir/.venv/bin/pip" install -q -r "$dir/requirements.txt"
  if [ "$FULL" = 1 ]; then "$dir/.venv/bin/pip" install -q -r "$dir/requirements-full.txt"; fi
  if [ ! -f "$dir/.env" ]; then
    echo "  → 日报引擎还没配置：cp $dir/.env.example $dir/.env，至少填一个 AI（DeepSeek key，或已登录的 claude / codex）"
  fi
}

if [ "$DAILY_ONLY" = 0 ]; then
  [ -x .venv/bin/python ] || python3 -m venv .venv
  .venv/bin/pip install -q --upgrade pip
  .venv/bin/pip install -q -r backend/requirements.txt

  read -r url sha < <(lock douyin-teardown)
  extra=""; [ "$FULL" = 1 ] && extra="[mlx]"
  .venv/bin/pip install -q "douyin-teardown${extra} @ git+${url}@${sha}"
  echo "✓ douyin-teardown @ ${sha:0:10}"

  (cd frontend && npm install --no-audit --no-fund --silent && npm run build --silent)
  echo "✓ 前端已构建"
fi

setup_daily

echo
echo "完成。启动：scripts/start.sh   然后打开 http://127.0.0.1:8000"
if [ "$FULL" = 0 ]; then
  echo "想在本机拆解视频，还需要：scripts/setup.sh --full（转写依赖）、抖音 cookies、一个 AI。"
  echo "在页面「拆解报告」里点「检查拆解环境」会逐项告诉你缺什么。"
fi
