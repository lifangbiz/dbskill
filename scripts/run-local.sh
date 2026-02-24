#!/usr/bin/env bash
# 本地启动 dbskill（不使用 Docker）。可选：传端口或通过环境变量 SESSION_SECRET、CONFIG_PATH、PORT 覆盖默认。

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT_DIR"

PORT="${PORT:-9000}"
CONFIG_PATH="${CONFIG_PATH:-$ROOT_DIR/config.yaml}"
SESSION_SECRET="${SESSION_SECRET:-dev-secret-change-in-production}"

if [[ ! -f "$CONFIG_PATH" ]]; then
  echo "警告: 未找到 config.yaml，建议复制 dbskill/config.example.yaml 为 config.yaml 并修改。" >&2
fi

export SESSION_SECRET
# 可选：API 读取配置路径
export CONFIG_PATH

echo "启动 dbskill 本地服务，端口 $PORT ..."
exec python -m uvicorn api.main:app --host 0.0.0.0 --port "$PORT"
