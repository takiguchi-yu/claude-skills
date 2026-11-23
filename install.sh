#!/usr/bin/env bash
# このリポジトリをローカルのマーケットプレイス claude-skills として登録し、プラグイン my を user スコープで入れる。
# 何度実行しても同じ状態になる。CLAUDE_CONFIG_DIR があれば、そのプロファイルに入れる。
#
#   .claude-plugin/marketplace.json  ->  マーケットプレイス claude-skills（ディレクトリをそのまま読む）
#   .claude-plugin/plugin.json       ->  プラグイン my@claude-skills（各ディレクトリのスキル・エージェント・フックを列挙）
#
# ディレクトリのマーケットプレイスはキャッシュにコピーされないので、ここで編集すれば
# 次のセッション起動か /reload-plugins で反映される。
# marketplace.json に無くなった @claude-skills のプラグインと、以前の方式で ~/.claude/{skills,agents} に張った
# このリポジトリへのリンクは外す（二重に読まれないように）。
# macOS 標準の bash 3.2 で動くように書く。
set -euo pipefail

REPO="$(cd "$(dirname "$0")" && pwd)"
TARGET="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
MARKETPLACE=claude-skills

info() { printf '\033[1;34m==>\033[0m %s\n' "$*"; }

# plugin.json に列挙し忘れたスキルのディレクトリとエージェントがあれば止める（列挙が無いと読まれないため）
check_manifest() {
  python3 - "$REPO" <<'EOF'
import glob, json, os, sys
repo = sys.argv[1]
os.chdir(repo)
m = json.load(open(".claude-plugin/plugin.json"))
want = {f"./{p}" for p in glob.glob("*/skills")} | {f"./{p}" for p in glob.glob("*/agents/*.md")}
missing = sorted(want - set(m.get("skills", [])) - set(m.get("agents", [])))
if missing:
    sys.exit("plugin.json に列挙されていないもの: " + ", ".join(missing))
EOF
}

unlink_legacy() { # <ディレクトリ>: このリポジトリを指すリンクを外す
  local entry
  for entry in "$1"/* "$1"/.[!.]*; do
    [ -L "$entry" ] || continue
    case "$(readlink "$entry")" in
      "$REPO"/*)
        rm "$entry"
        info "外しました（旧方式のリンク）: $entry"
        ;;
    esac
  done
}

plugins() { # marketplace.json のプラグイン名
  python3 -c 'import json,sys; print(" ".join(p["name"] for p in json.load(open(sys.argv[1]))["plugins"]))' "$REPO/.claude-plugin/marketplace.json"
}

stale_plugins() { # 入っている @claude-skills のうち、marketplace.json に無いもの
  claude plugin list --json | python3 -c '
import json, sys
keep = {f"{n}@{sys.argv[1]}" for n in sys.argv[2].split()}
for p in json.load(sys.stdin):
    if p["id"].endswith("@" + sys.argv[1]) and p["id"] not in keep and p.get("scope") == "user":
        print(p["id"])
' "$MARKETPLACE" "$(plugins)"
}

main() {
  local plugin
  command -v claude >/dev/null || { echo "claude が見つかりません" >&2; exit 1; }
  check_manifest
  if claude plugin marketplace list --json |
    python3 -c 'import json,sys; sys.exit(0 if any(m["name"] == sys.argv[1] for m in json.load(sys.stdin)) else 1)' "$MARKETPLACE"; then
    claude plugin marketplace update "$MARKETPLACE"
  else
    claude plugin marketplace add "$REPO" --scope user
  fi
  for plugin in $(plugins); do
    claude plugin install "$plugin@$MARKETPLACE" --scope user
  done
  # 新しいものが入ってから古いものを外す。途中で失敗しても、どの方式でも読めない状態にしない
  # 外せなくても止めない（旧方式のリンクの撤去まで進める）。残ったものは手で外すよう知らせる
  for plugin in $(stale_plugins); do
    if claude plugin uninstall "$plugin" --scope user; then
      info "外しました（marketplace.json に無いプラグイン）: $plugin"
    else
      printf '\033[1;33m警告:\033[0m %s を外せませんでした。claude plugin uninstall %s --scope user で外してください\n' "$plugin" "$plugin" >&2
    fi
  done
  unlink_legacy "$TARGET/skills"
  unlink_legacy "$TARGET/agents"
  info "入れました。起動中のセッションには /reload-plugins で反映します"
}

main
