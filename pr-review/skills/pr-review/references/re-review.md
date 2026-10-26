# 再レビューのとき

`pr-review` の手順 1 で、自分の submitted レビュー（`body` が空でないもの）が既にあると分かったときに読む。
手順 2・3・4・8 に、ここの作業を足す。

レビュー役は初回と同じ 3 体を（Standards 軸は本体が見る）、初回と同じ固定点 `origin/<baseRefName>` で立てて PR 全体を見る。
そのうえで、前回のあとに積まれた修正コミットを機能面のレビュー役に重点として渡す。

1. **修正コミットを切り出す（手順 2）。** `commits.txt` を書いた直後、レビュー役を立てる前に行う。
   前回レビューした head は、`body` が空でない自分の submitted レビューのうち最新のものの `commit.oid`。
   `git -C "$WT" merge-base --is-ancestor <commit.oid> HEAD` が通れば、
   `git -C "$WT" diff <commit.oid>..HEAD -- $(cat "$PRDIR/files.txt") > "$PRDIR/fix.diff"` として、
   機能面のレビュー役の入力に足す。PR のファイルに絞るのは、base を取り込むマージ（Update branch）の変更を除くため。
   通らなければ（rebase で履歴が書き換わった）、`fix.diff` は作らずに進める。
2. **由来を付ける（手順 3）。** `fix.diff` があるときは、台帳に「由来」の列を足し、指摘ごとに
   **修正コミット由来**（`fix.diff` に現れる行）か**前回の見落とし**（前回の head に既にあった行）かを書く。
   前回の見落としも、ほかの指摘と同じ基準で行き先を決める。`fix.diff` が無いときは由来を付けない。
3. **前回の判断をそろえる（手順 4）。** 手順 2 で退避した直近の `prev-*/ledger.md` を読む。前回不採用にした行と同じ論点は、
   根拠にした `path:line` が `fix.diff` に現れなければ、前回と同じ理由で不採用にする。現れていれば、コードが
   変わっているので改めて判定する。前回インラインや総評に出した論点は、手順 4 の「既出」に当たる。
4. **総評に由来ごとの件数を足す（手順 8）。** 書式は comment-format.md の「submit の総評」。

## 4 回目以降は A だけを出す

手順 1 の `submitted` のうち、`author.login` が `viewer.login` で、`state` が `COMMENTED` で、`body` が空でないレビューの件数を N とする。
`COMMENTED` に絞るのは、手順 8 の submit は必ず `COMMENTED` になり、追跡の approve（`APPROVED`）を数えないため。
初回を 1 回目と数え、今回は N+1 回目のレビューになる。**N が 3 以上なら**、上の 1〜4 に加えて次を行う。
3 回直しても指摘が収束しないなら、細かな指摘を重ねるより方針を見直すほうが早い
（Anthropic の Claude Code チームも 3 ラウンドで打ち切る: https://claude.dev/blog/solving-code-review-at-anthropic/ ）。

- **手順 4** — 区分 B・C の行は不採用にする。理由は「基準未満」、括弧内の根拠は review-standard.md の「4 回目以降のレビューでの B・C」と書く。
  A の行は通常どおり行き先を決める。
- **手順 8** — 総評に、方針の見直しを促す段落を足す。書式は comment-format.md の「submit の総評」。
