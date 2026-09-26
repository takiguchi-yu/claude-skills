#!/usr/bin/env python3
"""検証済みのインラインコメントを、PR の pending レビュー（下書き）として投稿する。

pending なので、submit するまで PR の参加者には見えない。投稿者だけが GitHub の
Files changed タブで "Pending" として確認できる。

空の pending レビューを作ってからスレッドを 1 件ずつ足す。まとめて渡す
`addPullRequestReview(threads:)` より API 呼び出しは増えるが、1 件が失敗しても
残りが落ちない。行を特定できない指摘をファイル単位（subjectType: FILE）へ
落とせるのもこちらだけ。

使い方:
  # 投稿せず、何を投げるかだけ確認する
  post_pending_review.py --pr-id <PR node ID> --comments validated.json --dry-run

  # 実際に pending として投稿する
  post_pending_review.py --pr-id <PR node ID> --comments validated.json

  # 既にある pending レビューへ足す（途中で失敗したときの再開）
  post_pending_review.py --review-id <review node ID> --comments validated.json

入力 JSON は配列、または validate_positions.py が出す {"valid": [...]} 形式。
1 件の形は validate_positions.py と同じ。`subject_type` に "FILE" を入れると
ファイル単位のコメントになり、line / side は無視される。
"""

import argparse
import json
import subprocess
import sys

ADD_REVIEW = """
mutation($prId:ID!){
  addPullRequestReview(input:{pullRequestId:$prId}){
    pullRequestReview{ id state }
  }}
"""

ADD_THREAD = """
mutation($reviewId:ID!,$path:String!,$body:String!,$line:Int,$side:DiffSide,
         $startLine:Int,$startSide:DiffSide,$subjectType:PullRequestReviewThreadSubjectType){
  addPullRequestReviewThread(input:{
    pullRequestReviewId:$reviewId, path:$path, body:$body, line:$line, side:$side,
    startLine:$startLine, startSide:$startSide, subjectType:$subjectType
  }){ thread{ id } }}
"""


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


def thread_variables(review_id, c):
    """コメント 1 件を addPullRequestReviewThread の変数へ写す。"""
    v = {
        "reviewId": review_id,
        "path": c["path"],
        "body": c["body"],
        "line": None, "side": None, "startLine": None, "startSide": None,
        "subjectType": None,
    }
    if str(c.get("subject_type", "")).upper() == "FILE":
        v["subjectType"] = "FILE"
        return v
    v["line"] = c["line"]
    v["side"] = c.get("side", "RIGHT")
    if c.get("start_line") is not None:
        v["startLine"] = c["start_line"]
        v["startSide"] = c.get("start_side", v["side"])
    return v


def load_comments(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    comments = data.get("valid", []) if isinstance(data, dict) else data
    if not isinstance(comments, list):
        sys.exit("--comments は JSON 配列か {\"valid\": [...]} でなければならない")
    if not comments:
        sys.exit("投稿するコメントが 0 件。validate_positions.py の結果を確認すること")
    return comments


def describe(c):
    if str(c.get("subject_type", "")).upper() == "FILE":
        return f"{c['path']} (ファイル単位)"
    span = f"{c.get('start_line')}-{c['line']}" if c.get("start_line") else c["line"]
    return f"{c['path']}:{span} ({c.get('side', 'RIGHT')})"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--comments", required=True, help="検証済みコメントの JSON")
    ap.add_argument("--pr-id", help="PR の node ID。新しく pending レビューを作る")
    ap.add_argument("--review-id", help="既存の pending レビューの node ID。そこへ足す")
    ap.add_argument("--dry-run", action="store_true", help="API を叩かず、投げる内容だけ表示する")
    args = ap.parse_args()

    if bool(args.pr_id) == bool(args.review_id):
        sys.exit("--pr-id か --review-id のどちらか一方を指定すること")

    comments = load_comments(args.comments)

    if args.dry_run:
        print(f"[dry-run] pending レビューに {len(comments)} 件を投稿する:\n")
        for i, c in enumerate(comments, 1):
            print(f"{i}. {describe(c)}")
            for line in c["body"].splitlines():
                print(f"     {line}")
            print()
        print("[dry-run] API は 1 回も呼んでいない。")
        return

    review_id = args.review_id
    if not review_id:
        data = gh_graphql(ADD_REVIEW, {"prId": args.pr_id})
        review = data["addPullRequestReview"]["pullRequestReview"]
        review_id = review["id"]
        if review["state"] != "PENDING":
            sys.exit(f"作成したレビューが PENDING でない (state={review['state']})。中止する")
        print(f"pending レビューを作成: {review_id}")

    failures = []
    for i, c in enumerate(comments, 1):
        label = describe(c)
        try:
            gh_graphql(ADD_THREAD, thread_variables(review_id, c))
            print(f"  ✓ {i}/{len(comments)} {label}")
        except (RuntimeError, KeyError) as e:
            print(f"  ✗ {i}/{len(comments)} {label} — {e}")
            failures.append({"comment": c, "error": str(e)})

    print(f"\n投稿: 成功 {len(comments) - len(failures)} 件 / 失敗 {len(failures)} 件")
    print(f"review_id={review_id}")
    if failures:
        print(
            "\n失敗した件は行がまだ diff 外の可能性がある。行を直すか subject_type を FILE にして、\n"
            f"  --review-id {review_id} で同じレビューへ足し直すこと。"
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
