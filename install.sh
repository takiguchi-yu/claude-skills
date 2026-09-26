#!/usr/bin/env bash
# 各ディレクトリのスキルとエージェントを ~/.claude にリンクする。何度実行しても同じ状態になる。
#
#   <ディレクトリ>/skills/<名前>/  ->  ~/.claude/skills/<名前>
#   <ディレクトリ>/agents/*.md     ->  ~/.claude/agents/*.md
#
# リンク先に実体か別のリンクがあれば ~/.local/state/claude-skills/backup/<日時>/ に退避する。
# このリポジトリを指すリンクのうち、リンク先が無くなったもの（名前を変えた・消したもの）は外す。
# macOS 標準の bash 3.2 で動くように書く。
set -euo pipefail

REPO="$(cd "$(dirname "$0")" && pwd)"
TARGET="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
BACKUP_DIR="$HOME/.local/state/claude-skills/backup/$(date +%Y%m%d-%H%M%S)"

info() { printf '\033[1;34m==>\033[0m %s\n' "$*"; }

link() { # <リポジトリ内の実体> <ホームのリンク>
  local src="$1" dst="$2"
  if [ -L "$dst" ] && [ "$(readlink "$dst")" = "$src" ]; then return; fi
  if [ -e "$dst" ] || [ -L "$dst" ]; then
    mkdir -p "$BACKUP_DIR/$(basename "$(dirname "$dst")")"
    mv "$dst" "$BACKUP_DIR/$(basename "$(dirname "$dst")")/"
    info "退避しました: $dst -> $BACKUP_DIR/$(basename "$(dirname "$dst")")/"
  fi
  mkdir -p "$(dirname "$dst")"
  ln -s "$src" "$dst"
  info "リンクしました: $dst"
}

prune() { # <ディレクトリ>: このリポジトリを指す壊れたリンクを外す
  local entry
  for entry in "$1"/* "$1"/.[!.]*; do
    [ -L "$entry" ] && [ ! -e "$entry" ] || continue
    case "$(readlink "$entry")" in
      "$REPO"/*)
        rm "$entry"
        info "外しました（リンク先が無い）: $entry"
        ;;
    esac
  done
}

main() {
  local dir
  for dir in "$REPO"/*/skills/*/; do
    [ -f "$dir/SKILL.md" ] || continue
    dir="${dir%/}"
    link "$dir" "$TARGET/skills/$(basename "$dir")"
  done
  for dir in "$REPO"/*/agents/*.md; do
    [ -f "$dir" ] || continue
    link "$dir" "$TARGET/agents/$(basename "$dir")"
  done
  prune "$TARGET/skills"
  prune "$TARGET/agents"
}

main
