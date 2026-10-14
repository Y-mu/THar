#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_root"

if [[ ! -x env/bin/langgraph ]]; then
  printf '%s\n' "缺少 env/bin/langgraph；请先创建 env 并安装：env/bin/python -m pip install -e '.[dev]'" >&2
  exit 1
fi

exec env/bin/langgraph dev --config langgraph.json --host 127.0.0.1 --port 2024 "$@"
