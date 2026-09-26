---
name: pr-review
description: PR をレビューして GitHub に投稿する。/code-review で指摘を出し、まず pending レビュー（下書き）としてインラインコメントを付け、人が確認してから実装者にメンション付きで submit する。WHEN - PR の URL や番号を渡して「レビューして」「レビューコメントを投稿して」「インラインでコメントを付けて」と言われた、下書きレビューを submit したい、レビュー結果を会話に出すだけでなく PR に書き込む必要がある。レビュー依頼で PR 番号や URL が出てきたら、投稿すると明言されていなくてもこのスキルを検討する。受け取った指摘に対応する側は pr-comments を使う。
---

# PR をレビューして pending 経由で投稿する

**一度に公開しない。** 指摘を pending レビュー（下書き）として PR に置き、人が GitHub 上で
現物を見て納得してから submit する。pending は投稿者にしか見えないので、誤爆も的外れも
公開前に消せる。この 2 段構えが、このスキルの存在理由そのもの。

レビューの中身は `/code-review` に任せる。このスキルの責務は **指摘を diff 上の正しい位置に
結びつけ、下書きとして置き、承認を得て公開すること**。

## 承認を得るまで実行しない操作

- **submit（手順 7）** — 実行した瞬間にレビュイーへ通知が飛ぶ。手順 6 で承認を取る。
- **既存 pending レビューの破棄（手順 1）** — 人が手で書いた下書きかもしれない。

pending への投稿（手順 5）は下書きなので承認は要らない。ただし手順 4 で必ず位置を検証してから投げる。

## 手順 1 — 前提を固める

1. 引数の URL または番号から `owner` / `repo` / `number` を取る。番号だけ渡されたら
   `git remote get-url origin` から `owner/repo` を補う。
2. PR の基本情報と、**自分の既存レビュー**を 1 回で取る。

```bash
gh api graphql -f query='
query($owner:String!,$repo:String!,$number:Int!){
  repository(owner:$owner,name:$repo){ pullRequest(number:$number){
    id number title url state isDraft
    author{ login }
    baseRefName headRefName headRefOid
    reviews(states:[PENDING], first:10){ nodes{ id url } }
  }}}' -F owner=OWNER -F repo=REPO -F number=N
```

- `pullRequest.id` が手順 5 で要る PR の node ID。
- `author.login` が手順 7 のメンション先。
- `reviews(states:[PENDING])` が空でなければ**既に自分の下書きがある**。pending レビューは
  作った本人にしか見えないので、ここに出るのは必ず自分のもの。新しく作ると二重になるため、
  AskUserQuestion で「そこへ足す / 破棄して作り直す / 中止」を確認する。
  破棄は `deletePullRequestReview(input:{pullRequestReviewId:$id})`。
- `state` が `MERGED` / `CLOSED`、または `isDraft` が true なら、レビューを投稿してよいか
  AskUserQuestion で確認する。

3. `git remote` が対象リポジトリを指していることを照合する。違えば手を止めて確認する。
   メインの作業ツリーはブランチも未コミットの変更もそのまま残す — レビューは手順 2 で作る worktree で行う。

**完了条件**: PR の node ID・author・URL・`headRefOid` が手元にあり、既存 pending レビューの有無を確認済み。

## 手順 2 — diff を確保して `/code-review` を回す

**レビューはメインの作業ツリーではなく worktree で行う。** `/code-review` は
`git diff <fixed-point>...HEAD` で差分を取り、周辺のコードもリポジトリから読む。HEAD が PR の head で
なければ、別の差分とコードをレビューしてしまう。一方でメインの作業ツリーで `gh pr checkout` すると、
進行中の作業のブランチと未コミットの変更を巻き込む。そこで PR の head を別の worktree に取り出す。
`$SCRATCH` はセッションの scratchpad ディレクトリ（システムプロンプトで与えられているパス）を指す。

```bash
WT="$SCRATCH/pr-<number>-wt"
git fetch origin <baseRefName>
git worktree add --detach "$WT" origin/<baseRefName>
cd "$WT" && gh pr checkout <number> --detach && git rev-parse HEAD
```

`--detach` を付けるのは、head ブランチがメインの作業ツリーで既にチェックアウトされていると、
同じブランチを 2 つ目の worktree に出せないため。出力された HEAD が `headRefOid` と一致することを確かめる。
一致したら元のディレクトリへ戻る — 以降の `.scratch/` はメインの作業ツリー側に置く。
シェル変数は Bash の呼び出しをまたいで残らないので、以降の `$WT` は展開済みの絶対パスで書く。

diff は手順 4 の検証でも使うので、先にファイルへ落とす。**`git diff` ではなく `gh pr diff` を使う** —
GitHub がコメント位置を計算するのは PR の diff（マージベースとの比較）なので、
ここがずれると位置が全部ずれる。

```bash
mkdir -p .scratch/pr-<number>
gh pr diff <number> > .scratch/pr-<number>/pr.diff
```

`.scratch/pr-<番号>/` を作業場所にする。`.gitignore` に載っていなければコミットに巻き込まないよう注意する。

そのうえで **`cd "$WT"` してから Skill ツールで `code-review` を起動し**、報告を受け取ったら
元のディレクトリへ戻る。固定点（fixed point）は PR のベースなので `origin/<baseRefName>` を渡す。
手順 3 でコードを読み直すときも `$WT` 配下のパスを読む。`/code-review` は Standards 軸と Spec 軸を並列サブエージェントで
回して両方の報告を返す。**`/code-review` 側は一切変更しない** — 呼ぶだけ。

`/code-review` は Spec 軸のために `docs/agents/issue-tracker.md` を要求する。無いリポジトリでは
Spec 軸が立たないので、**Standards 軸だけで進め、手順 8 で「Spec 軸は spec が見つからず未実施」と
報告する**。ここでユーザーに `/setup-matt-pocock-skills` を促して止まらない — レビューは
Standards 軸だけでも成立する。PR 本文や連結 issue に完了条件が書いてあれば、それを spec として渡す。

**完了条件**: HEAD が `headRefOid` と一致した状態で、`pr.diff` が存在し、`/code-review` の報告が手元にある（Spec 軸は未実施でもよい。
その場合は理由が控えてある）。

## 手順 3 — 指摘をインラインコメントに変換する

ここがこのスキルの中身。`/code-review` が返すのは散文の報告なので、**1 指摘 = 1 スレッド**に
ばらし、diff 上の位置を決める。

投稿候補を JSON 配列で `.scratch/pr-<number>/candidates.json` に書く。

```json
[
  {
    "id": "std-1",
    "path": "app.py",
    "line": 13,
    "side": "RIGHT",
    "body": "issue (blocking): b が 0 のとき ZeroDivisionError で落ちる\n\n同じモジュールの `mul` は `app.py:8` で 0 を弾いている。"
  }
]
```

- `line` は **指摘が当たるコードの行**。`/code-review` が引用したハンクの先頭ではない。
- `side` は変更後のコードなら `RIGHT`、**削除されたコードへの指摘なら `LEFT`**。
- 範囲で指すなら `start_line`（+ 必要なら `start_side`）を足す。`line` が範囲の終わり。
- `id` は自分がレポートで指すための名前。API には送られない。

本文の書式は [`references/comment-format.md`](references/comment-format.md) に従う（Conventional Comments）。

### 投稿するものとしないものを分ける

全部インラインにするとノイズになり、本当に直してほしい指摘が埋もれる。

**インラインに投稿する** — 行を特定でき、根拠（`path:line` か仕様 URL）があり、レビュイーが
その場で行動できる指摘。

**総評（手順 7）に回す** — 行に紐づかないもの。ファイル横断の設計上の指摘、diff に現れない
不足（テストが無い、ドキュメント未更新）、PR 全体の所感。

**捨てる** — 根拠を示せないもの、リポジトリの既存の慣習と衝突するだけのもの（@PRACTICE.md:
一般論より既存の慣習が勝つ）、`/code-review` が「judgement call」と断ったうえで具体案が無いもの。

捨てた件数は手順 8 の報告に残す。黙って落とさない。

**完了条件**: `candidates.json` が存在し、全件に `path` / `line` / `side` / `body` があり、
総評へ回した指摘と捨てた指摘を別に控えてある。

## 手順 4 — 位置を検証する

GitHub は **diff のハンク内に現れる行**にしかコメントを付けられない。範囲外の行を投げると
GraphQL がエラーを返すが、どの件が悪かったかは返ってこない。投げる前にここで落とす。

```bash
python3 ~/.claude/skills/pr-review/scripts/validate_positions.py \
  --diff .scratch/pr-<number>/pr.diff \
  --comments .scratch/pr-<number>/candidates.json \
  --out .scratch/pr-<number>/validated.json
```

無効な件には理由と「近い有効行」が出る。**近い有効行に機械的に寄せない** — 指摘が当たるのは
その行かを確かめ、違うなら位置を取り直す。

行を直しても収まらないときの逃げ道は 2 つあり、**どちらを使えるかは「そのファイルが diff に
含まれるか」で決まる**。

- **ファイルは diff にあるが、行を 1 つに絞れない**（ファイル全体の構成、複数箇所にまたがる話）
  → その件に `"subject_type": "FILE"` を付ける。ファイル単位のコメントになり、`line` / `side` は無視される。
- **ファイルが diff に含まれない**（`このパスは diff に含まれない` と出た件）
  → **`subject_type: FILE` でも投稿できない。** インラインを諦めて総評（手順 7）へ回す。
  diff に無いファイルへの指摘は、そもそもこの PR の変更ではないものを指している可能性が高いので、
  総評へ回す前に「本当にこの PR で言うべきか」を一度考える。

全件が有効になるまで `candidates.json` を直して回し直す。終了コード 0 が通過の合図。

`⚠` で出る警告は**エラーではないので止まらない**。リネームされたファイルの旧パスを指したときに出る。
GitHub がリネーム時に旧パス・新パスのどちらを受け付けるかは公式ドキュメントに記載が無いため
（[REST docs](https://docs.github.com/en/rest/pulls/comments?apiVersion=2022-11-28) の `path` は
「コメント対象ファイルの相対パス」としか書かれていない）、投稿してみて 422 で落ちたら
警告が示す新パスに差し替える。

**完了条件**: 検証が終了コード 0 で通り、`validated.json` ができている。

## 手順 5 — pending として投稿する

```bash
# 何を投げるか先に目視する（API は呼ばれない）
python3 ~/.claude/skills/pr-review/scripts/post_pending_review.py \
  --pr-id <PR node ID> --comments .scratch/pr-<number>/validated.json --dry-run

# 投稿する
python3 ~/.claude/skills/pr-review/scripts/post_pending_review.py \
  --pr-id <PR node ID> --comments .scratch/pr-<number>/validated.json
```

空の pending レビューを作ってからスレッドを 1 件ずつ足すので、1 件失敗しても残りは残る。
失敗があればスクリプトが `review_id` を出すので、直してから `--review-id <id>` で同じ
レビューへ足し直す。**失敗のたびに新しいレビューを作らない** — 下書きが二重になる。

最後に出る `review_id` を控える。手順 7 で要る。

**完了条件**: 全件が投稿され、`review_id` が手元にある。

## 手順 6 — 手を止めて確認してもらう

**ここで止まる。** 確認先の URL を出す。pending コメントは Files changed タブに "Pending" として
表示され、投稿者にしか見えない。

```
<PR の URL>/files
```

会話には投稿した指摘の一覧（`path:line` とラベルと要点の 1 行）と、総評に回した指摘、
捨てた件数を出す。そのうえで **AskUserQuestion で submit の可否を取る**。選択肢は
「submit する / 指摘を直してから submit / 破棄する」。

- 「直してから」なら手順 3〜5 に戻る。既存スレッドの本文修正は
  `updatePullRequestReviewComment`、削除は `deletePullRequestReviewComment`。
- 「破棄」なら `deletePullRequestReview(input:{pullRequestReviewId:$reviewId})` を実行し、
  手順 8 で「破棄した」と報告して終わる。

**完了条件**: ユーザーの判断を得ている。得られていなければ submit しない。

## 手順 7 — submit する

submit の `body` がそのままメンション付きコメントになり、**同時に pending が解除**されて
インラインコメントが公開される。1 回の操作で両方が起きる。

総評の書式は [`references/comment-format.md`](references/comment-format.md) の「submit の総評」に従う。
**本文はファイルに書き、`-F body=@<path>` でファイルから読ませる。** `$(cat ...)` で渡すと、
本文に含まれるバッククォートをシェルがコマンド置換として実行してしまう。

```bash
gh api graphql -f query='
mutation($reviewId:ID!,$body:String!){
  submitPullRequestReview(input:{pullRequestReviewId:$reviewId, event:COMMENT, body:$body}){
    pullRequestReview{ url state }
  }}' -f reviewId="<review_id>" -F body=@.scratch/pr-<number>/summary.md
```

**`event` は `COMMENT` を使う。** `APPROVE` と `REQUEST_CHANGES` はマージ可否に効く重い判定で、
人が押すもの。指摘の深刻度は本文のラベル（`issue (blocking)` 等）で伝わる。
ユーザーが明示的に承認や変更要求を求めた場合だけ、その値を使う。

返る `state` が `COMMENTED` なら成功。`PENDING` のままなら submit が効いていない。

**完了条件**: `state` が `COMMENTED` になり、レビューの URL が返っている。

## 手順 8 — 報告する

報告の前に、手順 2 で作った worktree を `git worktree remove "$WT"` で片付ける。

- 投稿したインラインコメントの件数（ラベル別）と、レビューの URL
- 総評に回した指摘と、その理由
- 捨てた指摘の件数と、捨てた基準
- `/code-review` の軸ごとの所見のうち、投稿に載せなかったもの

`.scratch/pr-<number>/` に候補・検証結果・総評が残っているので、次に開く人が辿れる（@ISSUE.md）。

## dry-run で止めたいとき

ユーザーが「投稿はしないで内容だけ見せて」と言ったら、**手順 5 の dry-run までで止める**。
手順 1〜4 は GitHub を読むだけで書き込まない。dry-run の出力と、総評の下書きを会話に出し、手順 2 の worktree を `git worktree remove "$WT"` で片付けて終わる。

## 同梱物

| ファイル | 役割 |
| --- | --- |
| `scripts/validate_positions.py` | diff と投稿候補を突き合わせ、位置の妥当性を判定する。`gh` も GitHub も知らないので単体で試せる |
| `scripts/post_pending_review.py` | pending レビューを作り、スレッドを 1 件ずつ足す。`--dry-run` あり |
| `references/comment-format.md` | Conventional Comments に沿った本文の書式と、submit の総評の型 |
