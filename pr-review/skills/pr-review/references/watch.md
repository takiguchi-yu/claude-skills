# レビュー依頼を探す・監視する

`pr-review` の SKILL.md の「レビュー依頼を探すとき・監視するとき」から読む。自分宛てのレビュー依頼を探すとき、
`/loop` などで定期的に監視するときの、対象の集め方と報告の型。

## 対象を集める

依頼の正本は、PR の `reviewRequests` と `reviews`。`scripts/list_review_targets.py` がこれを GraphQL で直接読み、open の PR を全ページ見る。
検索 API（`gh search prs` の `review-requested:@me` など）の結果には、依頼中の PR が出ないことがある
（個人宛ての依頼を 3 回の監視で取りこぼした。原因は未確認）。

```bash
python3 ~/.claude/skills/pr-review/scripts/list_review_targets.py --repo <owner>/<repo> --out <scratchpad>/targets.json
```

チーム宛てだけの依頼は、ユーザーが対象に含めると言ったときだけ `--include-team` で拾う。

## 振り分ける

`reasons` の値で決める。

| `reasons` | 次の一手 |
| --- | --- |
| `requested` か `requested-team:<slug>` を含む | 前回のレビューの有無に関わらず、SKILL.md の手順 1 から回す。再依頼かどうかは手順 1 が判定する（自分が submit すると依頼先から外れるので、`requested` と `reviewed` が両方付くのは再依頼）。`draft` も付いていれば、手順 1 の `isDraft` の扱いに従う |
| `draft` を除くと `reviewed` だけ | 一覧として報告する。追跡は、ユーザーに頼まれたときか、監視の指示で追跡まで任されたときだけ、`.scratch/pr-<number>/follow.md` の状態を見て [`follow-up.md`](follow-up.md) の「入口」から入る |

監視の 1 回の中で追跡するときは、F2・F6 の待機を起動せず、`wait_for_replies.py` を `--timeout 0 --settle 0 --interval 5` で 1 回だけ実行する
（`--interval` は問い合わせに失敗したときの再試行の間隔）。終了コードの読み方は F2 の表に従う — 3 は反応なしで、確認の失敗は 1。

結果が既知の事実と食い違ったら（依頼中のはずの PR が出ない、など）、報告の前に `gh pr view <number> --repo <owner>/<repo> --json reviewRequests` で突き合わせる。

**完了条件**: 報告に、`list_review_targets.py` の最後の行（open の PR を何件見て対象が何件か）がそのまま入っている。
終了コードが 0 以外の回は、代わりに標準エラーの内容と「確認に失敗した」が入っている。
