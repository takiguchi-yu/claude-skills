#!/usr/bin/env python3
"""PR への投稿コマンドを、メンション先が PR の作者と一致しないときに止める PreToolUse フック（Bash）。

SKILL.md 手順 8 の照合（check_mention.py）を、手順を飛ばしても掛かるようにするためのもの。
ユーザー設定（~/.claude/settings.json）の PreToolUse・matcher "Bash" に登録して使う。

対象にする投稿:
  - gh api graphql の submitPullRequestReview / addPullRequestReview（本文を -F body=@<file> で渡すもの）
  - gh pr comment / gh pr review（本文を --body-file / -F <file> で渡すもの）
本文を持たない呼び出し（pending レビューの作成など）とスレッドへの返信は対象にしない。
作者が自分の PR は対象にしない（自分の PR ではレビュアーをメンションするため）。

判定できないとき（PR か本文ファイルを特定できない、作者を取得できない）は止める。
止めた理由は permissionDecisionReason でエージェントに返る。
"""

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from check_mention import (  # noqa: E402
    AuthorLookupError,
    check,
    fetch_author_by_node,
    fetch_author_by_number,
    fetch_viewer,
)

REVIEW_MUTATION = re.compile(r"\b(submitPullRequestReview|addPullRequestReview)\s*\(")
GH_PR_POST = re.compile(r"\bgh\s+pr\s+(comment|review)\b")
BODY_FILE_VAR = re.compile(r"-F\s+body=@(\"[^\"]+\"|'[^']+'|\S+)")
BODY_INLINE_VAR = re.compile(r"-[fF]\s+body=(?!@)")
BODY_FILE_FLAG = re.compile(r"(?:--body-file|-F)[\s=](\"[^\"]+\"|'[^']+'|\S+)")
NODE_ID = re.compile(r"\b(PRR_[A-Za-z0-9_-]+|PR_[A-Za-z0-9_-]+)")
PR_NUMBER = re.compile(r"\bgh\s+pr\s+(?:comment|review)\s+(?:\S*/pull/)?(\d+)\b")
REPO_FLAG = re.compile(r"(?:--repo|-R)[\s=](\S+)")


def deny(reason):
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": f"メンション先の照合（pr-review の check_mention）: {reason}",
        }
    }, ensure_ascii=False))
    sys.exit(0)


def resolve_path(raw, cwd):
    path = raw.strip("\"'")
    if "$" in path or "`" in path:
        deny(f"本文ファイルのパスにシェル変数がある（{path}）。展開済みのパスで渡す")
    if not os.path.isabs(path):
        path = os.path.join(cwd, path)
    if not os.path.isfile(path):
        deny(f"本文ファイルが見つからない（{path}）。絶対パスで渡す")
    return path


def target_of(command, cwd):
    """(作者を取る関数, 本文ファイルのパス) を返す。投稿でなければ None。"""
    if "gh" not in command:
        return None

    if REVIEW_MUTATION.search(command) and "graphql" in command:
        file_match = BODY_FILE_VAR.search(command)
        if file_match is None:
            if BODY_INLINE_VAR.search(command):
                deny("本文が -f body= で直接渡されている。ファイルに書いて -F body=@<file> で渡す")
            return None  # 本文なし（pending レビューの作成など）
        node = NODE_ID.search(command)
        if node is None:
            deny("PR を特定できない。PR かレビューの node ID（PR_… / PRR_…）をリテラルで渡す")
        body_path = resolve_path(file_match.group(1), cwd)
        return (lambda: fetch_author_by_node(node.group(1))), body_path

    if GH_PR_POST.search(command):
        file_match = BODY_FILE_FLAG.search(command)
        if file_match is None:
            return None  # 本文ファイルなし（--body の直書きは、レビュー以外の用途もあるので対象にしない）
        number = PR_NUMBER.search(command)
        if number is None:
            deny("PR の番号を特定できない。gh pr comment <番号> の形で渡す")
        repo = REPO_FLAG.search(command)
        body_path = resolve_path(file_match.group(1), cwd)
        return (lambda: fetch_author_by_number(number.group(1), repo=repo.group(1) if repo else None, cwd=cwd)), body_path

    return None


def main():
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)
    command = (payload.get("tool_input") or {}).get("command") or ""
    cwd = payload.get("cwd") or os.getcwd()

    target = target_of(command, cwd)
    if target is None:
        sys.exit(0)
    get_author, body_path = target

    try:
        author = get_author()
        viewer = fetch_viewer()
    except AuthorLookupError as e:
        deny(f"PR の作者を取得できない（{e}）")

    if author.lower() == viewer.lower():
        sys.exit(0)

    with open(body_path, encoding="utf-8") as f:
        ok, reason = check(f.read(), author)
    if not ok:
        deny(reason)
    sys.exit(0)


if __name__ == "__main__":
    main()
