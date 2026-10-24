#!/usr/bin/env bash
# eval の実行はサンドボックスの中で動き、シンボリックリンク先の付属物を読めない。
# そこで実行の前に、元のスキルとエージェントの実ファイルをこのプラグインへコピーする。
set -euo pipefail
cd "$(dirname "$0")"
SRC=../..
rm -rf skills agents
mkdir -p skills agents
rsync -a --exclude evals "$SRC/skills/pr-review/" skills/pr-review/
rsync -a "$HOME/.agents/skills/code-review/" skills/code-review/
# references/conditional-sources.md が Standards に渡す出典
rsync -a "$SRC/../oo-design/skills/oo-design/" skills/oo-design/
rsync -a "$HOME/.agents/skills/writing-for-agents/" skills/writing-for-agents/
cp "$SRC/agents/pr-review-functionality.md" agents/
# 構成 B などの変更は local.patch に置く。コピーし直すたびに当て直すので、sync.sh を流しても変更は消えない。
if [ -f local.patch ]; then
	patch -p0 --forward --quiet < local.patch
fi
