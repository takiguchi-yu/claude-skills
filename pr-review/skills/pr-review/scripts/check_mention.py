#!/usr/bin/env python3
"""投稿する本文のメンション先が、PR の作者と一致するかを判定する。

総評・approve・総評への返信は、本文の最初のメンションで実装者に通知を届ける。
宛先を記憶や前の PR から写すと、別の人に通知が飛ぶ（自動レビューで実際に起きた）。
作者はこのスクリプト自身が GitHub から取り、本文と突き合わせる。投稿前にここで落とす。

入力:
  --repo    owner/repo
  --number  PR の番号
  --body    投稿する本文のファイル

判定: 本文の最初のメンション（行頭か空白の直後の @login）が PR の author.login と一致すること。
       メンションが 1 つも無い本文も不一致として扱う。

終了コード: 一致なら 0、不一致なら 1、作者を取得できなければ 2。

投稿コマンドを実行前に止めるフック（pretool_check_mention.py）も、判定はこのモジュールの
check() を使う。
"""

import argparse
import re
import subprocess
import sys

MENTION = re.compile(r"(?:^|(?<=\s))@([A-Za-z0-9](?:[A-Za-z0-9-]{0,38}))", re.MULTILINE)


class AuthorLookupError(Exception):
    pass


def _gh(args, cwd=None):
    result = subprocess.run(["gh", *args], capture_output=True, text=True, cwd=cwd)
    if result.returncode != 0 or not result.stdout.strip():
        raise AuthorLookupError(result.stderr.strip() or "gh の出力が空")
    return result.stdout.strip()


def fetch_author_by_number(number, repo=None, cwd=None):
    """PR の番号から作者の login を取る。repo を省くと cwd のリポジトリを使う。"""
    args = ["pr", "view", str(number), "--json", "author", "--jq", ".author.login"]
    if repo:
        args += ["--repo", repo]
    return _gh(args, cwd=cwd)


def fetch_author_by_node(node_id):
    """PR（PR_…）かレビュー（PRR_…）の node ID から、PR の作者の login を取る。"""
    query = (
        "query($id:ID!){ node(id:$id){"
        " ... on PullRequest{ author{ login } }"
        " ... on PullRequestReview{ pullRequest{ author{ login } } } } }"
    )
    jq = ".data.node | (.author.login // .pullRequest.author.login // empty)"
    return _gh(["api", "graphql", "-f", f"query={query}", "-f", f"id={node_id}", "--jq", jq])


def fetch_viewer():
    return _gh(["api", "user", "--jq", ".login"])


def check(body, author):
    """本文の最初のメンションが author か。(一致したか, 理由) を返す。"""
    match = MENTION.search(body)
    if match is None:
        return False, f"本文にメンションが無い。2 行目の先頭に @{author} を書く"
    mentioned = match.group(1)
    if mentioned.lower() != author.lower():
        return False, f"最初のメンションが @{mentioned} だが、PR の作者は @{author}。@{author} に直す"
    return True, f"最初のメンション @{mentioned} は PR の作者と一致する"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--number", required=True, type=int)
    parser.add_argument("--body", required=True)
    args = parser.parse_args()

    with open(args.body, encoding="utf-8") as f:
        body = f.read()

    try:
        author = fetch_author_by_number(args.number, repo=args.repo)
    except AuthorLookupError as e:
        sys.stderr.write(f"PR #{args.number} の作者を取得できなかった: {e}\n")
        sys.exit(2)

    ok, reason = check(body, author)
    print(("✓ " if ok else "✗ ") + f"PR #{args.number}: {reason}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
