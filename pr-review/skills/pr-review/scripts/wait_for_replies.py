#!/usr/bin/env python3
"""submit したレビューへの反応を待ち、届いたらまとめて書き出して終わる。

反応として拾うもの（いずれも --since より後、自分以外が起こしたもの）:
  - 自分が立てたスレッドへの返信
  - PR の会話コメントのうち、PR の作者が書いたものか、自分へのメンションを含むもの（bot は除く）
  - 自分へのレビュー再依頼
  - 待っている間に、自分のスレッドを他人が resolve した
  - --head を渡したとき、PR の head がそれと違う（approve の後に push された）
  - PR のクローズ・マージ

最初の反応を拾っても、すぐには終わらない。--settle 秒のあいだ新しい反応が来なくなるまで
待ってから終わる。返信はまとめて投稿されることが多く、1 件目で起きると残りを取りこぼす。

判定はしない。何が届いたかを --out に JSON で書くだけ。

使い方:
  wait_for_replies.py --repo owner/repo --number 123 --since 2026-10-01T09:00:00Z --out events.json

  # 続けて待つときは、前回の出力の next_since を --since に渡す

  # approve した後、マージされるまで待つ（approve した commit から head が動いても起きる）
  wait_for_replies.py --repo owner/repo --number 123 --since 2026-10-01T09:00:00Z --out events.json --head <approve した commit>

  # 待たずに 1 回だけ問い合わせ、自分のスレッドの一覧を取る（終了コード 3 で終わる）
  wait_for_replies.py --repo owner/repo --number 123 --since 2026-10-01T09:00:00Z --out now.json --timeout 0

終了コード:
  0  反応が届いた、または PR がクローズ・マージされた（--out の reason を見る）
  3  --timeout まで何も届かなかった。同じ --since で呼び直す
  1  GitHub への問い合わせが続けて失敗した
"""

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone

QUERY = """
query($owner:String!,$repo:String!,$number:Int!,$after:String){
  viewer{ login }
  repository(owner:$owner,name:$repo){ pullRequest(number:$number){
    url state headRefOid author{ login }
    comments(last:50){ nodes{ author{ login __typename } body url createdAt } }
    timelineItems(last:20, itemTypes:[REVIEW_REQUESTED_EVENT]){ nodes{
      ... on ReviewRequestedEvent{ createdAt actor{ login } requestedReviewer{ ... on User{ login } } } } }
    reviewThreads(first:100, after:$after){ pageInfo{ hasNextPage endCursor }
      nodes{ id path line isResolved resolvedBy{ login } viewerCanResolve
        comments(first:50){ nodes{ author{ login } viewerDidAuthor body url createdAt } } } }
  }}}
"""

MAX_CONSECUTIVE_FAILURES = 5
EXIT_TIMEOUT = 3


def gh_graphql(query, variables):
    """gh api graphql を叩き、data を返す。GraphQL の errors も失敗として扱う。"""
    payload = json.dumps({"query": query, "variables": variables})
    proc = subprocess.run(
        ["gh", "api", "graphql", "--input", "-"],
        input=payload, capture_output=True, text=True,
    )
    body = proc.stdout.strip() or proc.stderr.strip()
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError:
        raise RuntimeError(f"gh の応答を JSON として読めなかった: {body[:400]}")
    if parsed.get("errors"):
        raise RuntimeError("; ".join(e.get("message", str(e)) for e in parsed["errors"]))
    if proc.returncode != 0:
        raise RuntimeError(f"gh が終了コード {proc.returncode} で失敗: {body[:400]}")
    return parsed["data"]


def parse_time(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def fetch(owner, repo, number):
    """PR の状態と、全スレッドを 1 つの dict にまとめて返す。"""
    variables = {"owner": owner, "repo": repo, "number": number, "after": None}
    data = gh_graphql(QUERY, variables)
    pr = data["repository"]["pullRequest"]
    threads = list(pr["reviewThreads"]["nodes"])
    page = pr["reviewThreads"]["pageInfo"]
    while page["hasNextPage"]:
        variables["after"] = page["endCursor"]
        more = gh_graphql(QUERY, variables)["repository"]["pullRequest"]["reviewThreads"]
        threads.extend(more["nodes"])
        page = more["pageInfo"]
    return {"viewer": data["viewer"]["login"], "pr": pr, "threads": threads}


def comment_view(c):
    return {"author": (c.get("author") or {}).get("login"), "created_at": c["createdAt"],
            "url": c["url"], "body": c["body"]}


def collect(snapshot, since):
    """since より後に、自分以外が起こした反応を拾う。"""
    viewer = snapshot["viewer"]
    pr = snapshot["pr"]
    pr_author = (pr.get("author") or {}).get("login")

    threads = []
    for t in snapshot["threads"]:
        comments = t["comments"]["nodes"]
        if not comments or not comments[0]["viewerDidAuthor"]:
            continue  # 自分が立てたスレッドだけを追う
        new = [comment_view(c) for c in comments
               if not c["viewerDidAuthor"] and parse_time(c["createdAt"]) > since]
        threads.append({
            "id": t["id"], "path": t["path"], "line": t["line"],
            "is_resolved": t["isResolved"],
            "resolved_by": (t.get("resolvedBy") or {}).get("login"),
            "viewer_can_resolve": t["viewerCanResolve"],
            "root_url": comments[0]["url"],
            "root_summary": (comments[0]["body"].splitlines() or [""])[0],
            "new_comments": new,
        })

    conversation = []
    for c in pr["comments"]["nodes"]:
        author = c.get("author") or {}
        if author.get("__typename") == "Bot" or author.get("login") == viewer:
            continue
        if parse_time(c["createdAt"]) <= since:
            continue
        if author.get("login") == pr_author or f"@{viewer}" in c["body"]:
            conversation.append(comment_view(c))

    review_requests = [
        {"created_at": e["createdAt"], "actor": (e.get("actor") or {}).get("login")}
        for e in pr["timelineItems"]["nodes"]
        if (e.get("requestedReviewer") or {}).get("login") == viewer
        and parse_time(e["createdAt"]) > since
    ]

    return {"threads": threads, "conversation": conversation, "review_requests": review_requests}


def count_events(found, resolved_by_others):
    return (sum(len(t["new_comments"]) for t in found["threads"])
            + len(found["conversation"]) + len(found["review_requests"]) + len(resolved_by_others))


def next_since(found, since):
    """次に --since へ渡す時刻。拾った反応のうち最も新しいもの（GitHub の時計）。"""
    stamps = [since]
    stamps += [parse_time(c["created_at"]) for t in found["threads"] for c in t["new_comments"]]
    stamps += [parse_time(c["created_at"]) for c in found["conversation"]]
    stamps += [parse_time(e["created_at"]) for e in found["review_requests"]]
    return max(stamps).strftime("%Y-%m-%dT%H:%M:%SZ")


def write_result(out, reason, since, snapshot, found, resolved_by_others, head_changed):
    pr = snapshot["pr"]
    result = {
        "reason": reason,
        "head_changed": head_changed,
        "checked_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "since": since.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "next_since": next_since(found, since),
        "pr": {"url": pr["url"], "state": pr["state"], "head_oid": pr["headRefOid"]},
        "unresolved": sum(1 for t in found["threads"] if not t["is_resolved"]),
        "resolved_by_others": resolved_by_others,
        **found,
    }
    with open(out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    replies = sum(len(t["new_comments"]) for t in found["threads"])
    replied = sum(1 for t in found["threads"] if t["new_comments"])
    print(f"{reason}: 返信 {replies} 件（スレッド {replied} 件）・会話 {len(found['conversation'])} 件・"
          f"再依頼 {len(found['review_requests'])} 件・他人の resolve {len(resolved_by_others)} 件・"
          f"push {'あり' if head_changed else 'なし'} / "
          f"自分のスレッド {len(found['threads'])} 件中 未解決 {result['unresolved']} 件 / "
          f"PR {pr['state']} head {pr['headRefOid'][:7]} → {out}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", required=True, help="owner/repo")
    ap.add_argument("--number", required=True, type=int, help="PR 番号")
    ap.add_argument("--since", required=True, help="これより後の反応を拾う（ISO 8601、例 2026-10-01T09:00:00Z）")
    ap.add_argument("--out", required=True, help="結果を書く JSON のパス")
    ap.add_argument("--interval", type=int, default=60, help="問い合わせの間隔（秒）")
    ap.add_argument("--settle", type=int, default=300, help="最後の反応からこの秒数だけ静かになったら終わる")
    ap.add_argument("--timeout", type=int, default=6900, help="この秒数で何も届かなければ終了コード 3 で終わる")
    ap.add_argument("--head", help="この commit から PR の head が動いたら反応として拾う（approve 後の待機で使う）")
    args = ap.parse_args()

    owner, _, repo = args.repo.partition("/")
    since = parse_time(args.since)
    started = time.monotonic()
    unresolved_at_start = None
    last_signature, last_change = None, None
    failures = 0

    while True:
        try:
            snapshot = fetch(owner, repo, args.number)
            failures = 0
        except RuntimeError as e:
            failures += 1
            print(f"問い合わせに失敗（{failures}/{MAX_CONSECUTIVE_FAILURES}）: {e}", file=sys.stderr)
            if failures >= MAX_CONSECUTIVE_FAILURES:
                sys.exit(1)
            time.sleep(args.interval)
            continue

        found = collect(snapshot, since)
        unresolved = {t["id"] for t in found["threads"] if not t["is_resolved"]}
        if unresolved_at_start is None:
            unresolved_at_start = unresolved
        resolved_by_others = [
            t["id"] for t in found["threads"]
            if t["id"] in unresolved_at_start and t["is_resolved"]
            and t["resolved_by"] != snapshot["viewer"]
        ]

        head = snapshot["pr"]["headRefOid"]
        head_changed = bool(args.head) and head != args.head

        if snapshot["pr"]["state"] != "OPEN":
            write_result(args.out, "closed", since, snapshot, found, resolved_by_others, head_changed)
            return

        count = count_events(found, resolved_by_others) + (1 if head_changed else 0)
        now = time.monotonic()
        # push が続く間も静まるのを待てるよう、件数と head の組で変化を見る
        signature = (count, head)
        if signature != last_signature:
            last_signature, last_change = signature, now
        if count and now - last_change >= args.settle:
            write_result(args.out, "events", since, snapshot, found, resolved_by_others, head_changed)
            return
        if not count and now - started >= args.timeout:
            write_result(args.out, "timeout", since, snapshot, found, resolved_by_others, head_changed)
            sys.exit(EXIT_TIMEOUT)

        time.sleep(args.interval)


if __name__ == "__main__":
    main()
