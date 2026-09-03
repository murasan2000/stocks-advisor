#!/bin/bash
# SessionStart フック: Claude Code on the web のリモート環境でだけ、
# api/（uv）・web/（npm）の依存関係を自動インストールする。
#
# なぜ必要か:
#   ローカル開発は .devcontainer の postCreateCommand が `api/` の
#   `uv sync --group dev` のみを行い、`web/` の依存はインストールしない
#   （postCreateCommand は VS Code Dev Containers 用で、Claude Code on the web
#   のリモート環境では実行されない）。そのままだと web の
#   `npm run lint` / `npm run build` がリモートセッション開始直後は
#   実行できず、CLAUDE.md記載の検証コマンドが動かない状態になる。
#
# ローカル（devcontainer / 手元環境）では実行しない。ローカルは
# postCreateCommand や開発者自身の `uv sync` / `npm install` に任せる。
set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "${CLAUDE_PROJECT_DIR}/api"
uv sync --group dev

cd "${CLAUDE_PROJECT_DIR}/web"
npm install
