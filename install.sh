#!/usr/bin/env bash
# このリポジトリをローカルのマーケットプレイス claude-skills として登録し、全プラグインを user スコープで入れる。
# 何度実行しても同じ状態になる。CLAUDE_CONFIG_DIR があれば、そのプロファイルに入れる。
#
#   .claude-plugin/marketplace.json  ->  マーケットプレイス claude-skills（ディレクトリをそのまま読む）
#   <ディレクトリ>/                   ->  プラグイン <ディレクトリ>@claude-skills
#
# ディレクトリのマーケットプレイスはキャッシュにコピーされないので、ここで編集すれば
# 次のセッション起動か /reload-plugins で反映される。
# 以前の方式で ~/.claude/{skills,agents} に張ったこのリポジトリへのリンクは外す（二重に読まれないように）。
# macOS 標準の bash 3.2 で動くように書く。
set -euo pipefail

REPO="$(cd "$(dirname "$0")" && pwd)"
TARGET="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
MARKETPLACE=claude-skills

info() { printf '\033[1;34m==>\033[0m %s\n' "$*"; }

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

main() {
  local plugin
  command -v claude >/dev/null || { echo "claude が見つかりません" >&2; exit 1; }
  if claude plugin marketplace list --json |
    python3 -c 'import json,sys; sys.exit(0 if any(m["name"] == sys.argv[1] for m in json.load(sys.stdin)) else 1)' "$MARKETPLACE"; then
    claude plugin marketplace update "$MARKETPLACE"
  else
    claude plugin marketplace add "$REPO" --scope user
  fi
  for plugin in $(python3 -c 'import json,sys; print(" ".join(p["name"] for p in json.load(open(sys.argv[1]))["plugins"]))' "$REPO/.claude-plugin/marketplace.json"); do
    claude plugin install "$plugin@$MARKETPLACE" --scope user
  done
  # 全プラグインが入ってから外す。途中で失敗しても、どちらの方式でも読めない状態にしない
  unlink_legacy "$TARGET/skills"
  unlink_legacy "$TARGET/agents"
  info "入れました。起動中のセッションには /reload-plugins で反映します"
}

main
