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
# references/conditional-sources.md で本体が Standards 軸に使う出典
rsync -a "$SRC/../oo-design/skills/oo-design/" skills/oo-design/
rsync -a "$HOME/.agents/skills/writing-for-agents/" skills/writing-for-agents/
cp "$SRC/agents/pr-review-functionality.md" agents/
# 今のスキルとの違い（arm-a なら旧構成 A に戻す差分）は local.patch に置く。コピーし直すたびに当て直すので、sync.sh を流しても変更は消えない。
if [ -f local.patch ]; then
	patch -p0 --forward --quiet < local.patch
fi
# 元のスキルは、エージェントとスキルをプラグイン名付き（my:pr-review-functionality・my:oo-design）で呼ぶ。
# このプラグインでは全部がこのプラグイン名の下に入るので、呼び名を付け替える。
PLUGIN="$(python3 -c 'import json; print(json.load(open(".claude-plugin/plugin.json"))["name"])')"
{ grep -rlE 'my:(pr-review-functionality|oo-design)' skills agents || true; } | while IFS= read -r f; do
	sed -i '' -E "s/my:(pr-review-functionality|oo-design)/$PLUGIN:\1/g" "$f"
done
