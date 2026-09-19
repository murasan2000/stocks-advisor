#!/bin/bash
# SessionStart フック: 依存関係（api/ の uv、web/ の npm）が入っていなければ入れる。
#
# なぜ必要か:
#   ローカル開発は .devcontainer の postCreateCommand が `api/` の
#   `uv sync --group dev` のみを行い、`web/` の依存はインストールしない。
#   そのままだと web の `npm run lint` / `npm run build` が実行できず、
#   AGENTS.md 記載の検証コマンドが動かない状態になる。
#
# Claude Code 版（.claude/hooks/session-start.sh）との違い:
#   Claude 版は `$CLAUDE_CODE_REMOTE` でリモート環境だけに絞り、`$CLAUDE_PROJECT_DIR`
#   を基点にしている。どちらも Codex では設定されないため、そのまま流用すると
#   このスクリプトは常に即 exit して何もしない。Codex にリモート環境の区別が無い
#   以上「絞り込み」自体が意味を持たないので、代わりに
#   「入っていなければ入れる」という冪等な判定にし、基点はリポジトリルート
#   （このスクリプトの位置から解決）にしている。
#
# フックの失敗でセッション開始を止めないため、各ステップの失敗は警告に留める。
set -uo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

warn() { printf '[session-start] %s\n' "$*" >&2; }

if [ -f "$repo_root/api/pyproject.toml" ] && [ ! -d "$repo_root/api/.venv" ]; then
  (cd "$repo_root/api" && uv sync --group dev) || warn "api: uv sync failed"
fi

if [ -f "$repo_root/web/package.json" ] && [ ! -d "$repo_root/web/node_modules" ]; then
  (cd "$repo_root/web" && npm install) || warn "web: npm install failed"
fi

exit 0
