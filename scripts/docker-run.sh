#!/usr/bin/env bash
# 一键启动 dbskill 容器。可选：传端口或通过环境变量 SESSION_SECRET、CONFIG_PATH、DATA_PATH 覆盖默认。

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT_DIR"

IMAGE_NAME="${IMAGE_NAME:-dbskill}"
PORT="${PORT:-8000}"
CONFIG_PATH="${CONFIG_PATH:-$ROOT_DIR/config.yaml}"
DATA_PATH="${DATA_PATH:-$ROOT_DIR/data}"
SESSION_SECRET="${SESSION_SECRET:-dev-secret-change-in-production}"

if [[ ! -f "$CONFIG_PATH" ]]; then
  echo "警告: 未找到 config.yaml，将使用镜像内配置（如有）。建议复制 dbskill/config.example.yaml 为 config.yaml 并修改。" >&2
  CONFIG_MOUNT=""
else
  CONFIG_MOUNT="-v $CONFIG_PATH:/app/config.yaml"
fi

mkdir -p "$DATA_PATH"
docker rm -f dbskill 2>/dev/null || true

docker run -d --name dbskill \
  -p "$PORT:8000" \
  $CONFIG_MOUNT \
  -v "$DATA_PATH:/app/data" \
  -e SESSION_SECRET="$SESSION_SECRET" \
  "$IMAGE_NAME"

echo "已启动 dbskill，端口 $PORT。停止: docker stop dbskill"
