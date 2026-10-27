#!/usr/bin/env python3
"""リポジトリの open の PR から、自分がレビューする対象を列挙する。

対象にするもの（作者が自分の PR は除く）:
  - requested: 自分個人がレビュー依頼先（reviewRequests）に入っている
  - reviewed:  自分の submit 済みレビュー（COMMENTED・APPROVED・CHANGES_REQUESTED）がある
チーム宛てだけの依頼は、--include-team を付けたときだけ requested に含める。
draft の PR も対象にし、理由に draft を足す（落とすと件数にも表れず、取りこぼしに気付けない）。

検索 API（gh search prs の review-requested:@me など）は使わない。依頼中の PR が結果に出ないことがあった
（2026-10-27、個人宛ての依頼を 3 回の監視で取りこぼした。原因は未確認で、索引の遅れと推測）。
ここでは PR の reviewRequests と reviews を GraphQL で直接読み、open の PR を全ページ見る。

標準出力の最後の行に、見た PR の件数と対象の件数を必ず出す。対象が 0 件のときも、
「何を何件見て 0 件だったか」を報告に書けるようにするため。標準出力にアカウント名は出さない
（報告にそのまま写すため）。作者などは --out の JSON にだけ書く。

使い方:
  list_review_targets.py --repo owner/repo
  list_review_targets.py --repo owner/repo --out targets.json --include-team

終了コード:
  0  問い合わせが成功した（対象が 0 件でも 0）
  1  GitHub への問い合わせに失敗した
"""

import argparse
import json
import subprocess
import sys

QUERY = """
query($owner:String!,$repo:String!,$after:String){
  viewer{ login }
  repository(owner:$owner,name:$repo){
    pullRequests(states:OPEN, first:50, after:$after, orderBy:{field:CREATED_AT,direction:DESC}){
      pageInfo{ hasNextPage endCursor }
      nodes{ number url title isDraft headRefOid author{ login }
        reviewRequests(first:20){ nodes{ requestedReviewer{
          __typename ... on User{ login } ... on Team{ slug } } } }
        reviews(first:100, states:[COMMENTED,APPROVED,CHANGES_REQUESTED]){ nodes{ author{ login } state submittedAt } }
      } } } }
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


def fetch_open_prs(owner, repo):
    """open の PR を全ページ取り、(viewer の login, PR の一覧) を返す。"""
    prs, after, viewer = [], None, None
    while True:
        data = gh_graphql(QUERY, {"owner": owner, "repo": repo, "after": after})
        viewer = data["viewer"]["login"]
        conn = data["repository"]["pullRequests"]
        prs.extend(conn["nodes"])
        if not conn["pageInfo"]["hasNextPage"]:
            return viewer, prs
        after = conn["pageInfo"]["endCursor"]


def classify(pr, viewer, include_team):
    """PR が対象なら理由の一覧を、対象でなければ空の一覧を返す。"""
    if (pr["author"] or {}).get("login") == viewer:
        return []
    reasons = []
    for node in pr["reviewRequests"]["nodes"]:
        r = node["requestedReviewer"] or {}
        if r.get("__typename") == "User" and r.get("login") == viewer:
            reasons.append("requested")
        elif r.get("__typename") == "Team" and include_team:
            reasons.append(f"requested-team:{r.get('slug')}")
    if any((rv["author"] or {}).get("login") == viewer for rv in pr["reviews"]["nodes"]):
        reasons.append("reviewed")
    if reasons and pr["isDraft"]:
        reasons.append("draft")
    return reasons


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", required=True, help="owner/repo")
    ap.add_argument("--out", help="対象の一覧を JSON で書き出す先")
    ap.add_argument("--include-team", action="store_true", help="チーム宛ての依頼も requested に含める")
    args = ap.parse_args()

    owner, _, repo = args.repo.partition("/")
    try:
        viewer, prs = fetch_open_prs(owner, repo)
    except RuntimeError as e:
        print(f"問い合わせに失敗: {e}", file=sys.stderr)
        sys.exit(1)

    targets = []
    for pr in prs:
        reasons = classify(pr, viewer, args.include_team)
        if not reasons:
            continue
        mine = [rv for rv in pr["reviews"]["nodes"] if (rv["author"] or {}).get("login") == viewer]
        targets.append({
            "number": pr["number"], "url": pr["url"], "title": pr["title"],
            "author": (pr["author"] or {}).get("login"), "head": pr["headRefOid"],
            "reasons": reasons, "my_reviews": [{"state": rv["state"], "submittedAt": rv["submittedAt"]} for rv in mine],
        })

    if args.out:
        with open(args.out, "w") as f:
            json.dump({"repo": args.repo, "viewer": viewer, "open_prs": len(prs), "targets": targets},
                      f, ensure_ascii=False, indent=2)

    for t in targets:
        print(f"#{t['number']} {','.join(t['reasons'])} {t['title']}")
    print(f"{args.repo}: open の PR {len(prs)} 件を GraphQL の reviewRequests・reviews で確認 → 対象 {len(targets)} 件")


if __name__ == "__main__":
    main()
