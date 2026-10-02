# submit 後の追跡 — 返信を確かめて resolve し、approve して、マージ後に後始末する

`pr-review` の手順 7 で「submit してマージまで追跡する」が選ばれたとき、手順 8 の submit の直後から読む。
submit 済みのレビューの追跡だけを頼まれたとき、中断した追跡を再開するときも、ここから入る（末尾の「入口」）。

**追跡の resolve・追い返信・approve・後始末は、人の確認を挟まずに実行する。** 手順 7 で追跡が選ばれた時点で承認済みとして扱う。
人が見ない分、次の 3 つの歯止めで外れを抑える。

- **approve は確かめた head に固定する。** `commitOID` に確かめたコミットを渡し、確かめていないコミットを承認しない（手順 F5）
- **自動の追い返信は 1 つの指摘につき 2 回まで。** 3 回目が要るなら、やり取りが噛み合っていない。手を止め、
  そのスレッドのやり取りと自分の判断を示して AskUserQuestion で方針を聞く（@DECIDE.md「2 回作り直しても通らない」）
- **approve の前に、レビュー後に積まれた差分を見直す。** スレッドごとの確認では、指摘箇所の外で壊れたものを拾えない（手順 F5）。
  approve の後に積まれたコミットも、マージを待つ間に同じく見直す（手順 F6）

自分が作者の PR は approve できない（GitHub が拒否する）ので、追跡しない。

## 手順 F1 — 追跡台帳を作る

自分のスレッドの一覧を 1 回だけ取る（`--timeout 0` で待たずに終わる。終了コード 3 は正常）。
`--since` には submit の時刻を渡す。手順 8 の `submitPullRequestReview` が返したレビューの `submittedAt` を使う。

```bash
python3 ~/.claude/skills/pr-review/scripts/wait_for_replies.py \
  --repo <owner>/<repo> --number <number> --since <submittedAt> \
  --out <PRDIR>/events.json --timeout 0
```

`<PRDIR>/follow.md` に追跡台帳を書く。台帳（`ledger.md`）の行き先がインラインと総評の行を、**1 指摘 = 1 行**で写す。
スレッドの行は `events.json` の `threads` と `path` / `line` / `root_summary` で突き合わせ、スレッド ID を入れる。
`threads` のうち、未解決なのに台帳に無いもの（前回までのレビューで立てたスレッド）も行に足す。ID は `prev-1` から振り、
ラベルは `root_summary` から取る — これを外すと、自分の未解決スレッドを残したまま approve してしまう。

```markdown
# 追跡: <PR の URL>

- 状態: 追跡中
- since: <submittedAt>
- レビュー時の head: <submit したレビューの commit.oid>
- 確かめた head: <同上>

| ID | 種別 | スレッド ID | 場所 | ラベル | 状態 | 追い返信 | 判定と根拠 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| std-1 | スレッド | PRRT_xxx | app.py:13 | issue (blocking) | 待ち | 0 | |
| spec-2 | 総評 | — | — | issue (blocking) | 待ち | 0 | |

## 申し送り

- <返信で、この PR の外で後から対応すると約束されたもの>（<返信の URL>）
```

- 状態は `待ち` → `resolve 済み`（スレッド）／`確認済み`（総評）のどちらかで終わる。追い返信したら `待ち` に戻す。
- 総評の行は resolve できないので、確かめた時点で `確認済み` にする。**ブロッキングでない総評の行**（提案・質問）は、
  返信が無くても approve を止めない。台帳に残すのは、返信が来たときに確かめる対象を見失わないため。
- `<PRDIR>` は手順 2 で作った `.scratch/pr-<number>/` の絶対パス。手順 9 では worktree を片付けずに残し、F7 で片付ける。

**完了条件**: `follow.md` があり、`ledger.md` の行き先がインラインと総評の全行と、`events.json` の未解決スレッドの全件が載り、
スレッドの行には全件スレッド ID が入っている。

## 手順 F2 — 待つ

`wait_for_replies.py` を **Bash の `run_in_background: true`、`timeout: 7200000`** で起動する。
終わると知らせが届くので、ポーリングを自分で回さない。

```bash
python3 ~/.claude/skills/pr-review/scripts/wait_for_replies.py \
  --repo <owner>/<repo> --number <number> --since <follow.md の since> \
  --out <PRDIR>/events.json
```

| 終了コード | 意味 | 次の一手 |
| --- | --- | --- |
| 0（`reason: events`） | 反応が届いた | F3 へ |
| 0（`reason: closed`） | approve の前に PR がクローズ・マージされた | F7 へ |
| 3 | 約 2 時間、何も届かなかった | 同じ `--since` で起動し直す |
| 1 | GitHub への問い合わせが 5 回続けて失敗した | 1 回だけ起動し直す。また 1 なら、台帳の状態を「停止（待機の失敗）」にし、stderr を添えて F7 へ |

起動したら、会話に 1 行だけ書く — 待っていること、**このセッションを閉じると待機が止まること**、再開のしかた
（`/pr-review <PR の URL> の追跡を再開して`）。

スクリプトは自分の書き込みを反応として拾わない。F4 で自分が返信・resolve しても、それで起き直すことはない。

**完了条件**: スクリプトが終了コード 0 で終わり、`events.json` を読んだ。

## 手順 F3 — 確かめる

`events.json` を読み、判定するものを集める。

- `threads[].new_comments` がある行 — その返信
- `resolved_by_others` に出た行 — 返信なしで他人が resolve したスレッド
- `conversation` — 総評への返信。本文から、どの総評の行（またはスレッドの行）への返信かを決める
- `review_requests` がある — 再依頼。返信の有無によらず、状態が `待ち` の全行を今の head で確かめ直す

**判定の前に worktree を今の head に合わせる。**

```bash
cd "<WT>" && gh pr checkout <number> --detach && git rev-parse HEAD
```

1 行ずつ、返信の中身で下の表を当てる。判定の根拠は**今の head のコードを読んだ結果**（`path:line`）か、
コミット SHA か issue 番号に限る — 返信の文面だけで OK にしない。基準は [`review-standard.md`](review-standard.md) を使う。

| 返信の中身 | OK とする条件 | OK でないときに返すこと |
| --- | --- | --- |
| 直した（コミットを示す） | そのコミットが今の head の祖先にあり（`git merge-base --is-ancestor`）、今の head のコードで指摘が解消している | まだ残っている点を `path:line` で |
| 別チケットに回す | issue が実在し、元の指摘がブロッキングでない | ブロッキングの指摘はマージ前に直すものなので、別チケット送りでは OK にしない。その理由 |
| 対応不要（反論） | 反論の出典を読み、指摘が事実でない、または review-standard.md の「出さないもの」に当たる | 反論の出典を読んだうえで、指摘が成り立つ根拠を `path:line` で |
| 質問が返ってきた | 答えた結果、指摘が要らなくなった | 質問への答えと、あらためて求める対応 |
| 自分の `question` への回答 | 回答で、review-standard.md の A・B に当たらないと決まった | 当たると分かった区分と、求める対応 |
| 返信なしで他人が resolve した | 今の head で指摘が解消している | `unresolveReviewThread` で開き直したうえで、残っている点 |

反論が正しかったなら、それは自分の指摘の誤り。OK として resolve し、台帳の判定の列に「指摘の誤り」と書く。

返信が、この PR の外で後から対応すると約束していれば（「issue の記述は別途訂正します」「別 PR で直します」など、
issue 番号が付いていないもの）、OK・OK でないとは別に、台帳の「申し送り」に返信の URL を添えて 1 行で書く。
マージで PR が閉じると誰も見返さなくなるので、F7 の報告で拾い直す。

**完了条件**: 判定するものの全件に OK か OK でないかが付き、それぞれに根拠（`path:line`・SHA・issue 番号）がある。

## 手順 F4 — resolve するか、追い返信する

**OK の行** — スレッドなら resolve する。総評の行は台帳の状態を `確認済み` にする。

```bash
gh api graphql -f query='
mutation($id:ID!){ resolveReviewThread(input:{threadId:$id}){ thread{ isResolved } } }' -f id=<スレッド ID>
```

返る `isResolved` が true なら成功。`viewer_can_resolve` が false のスレッドは resolve できないので、台帳に理由を書いて OK 扱いで進める。

**OK でない行** — 追い返信を書いて投稿する。書式は [`comment-format.md`](comment-format.md) の「追跡中の返信」。
本文はファイルに書き、`-F body=@<path>` で読ませる（手順 8 と同じ理由）。

```bash
# スレッドの行
gh api graphql -f query='
mutation($id:ID!,$body:String!){
  addPullRequestReviewThreadReply(input:{pullRequestReviewThreadId:$id, body:$body}){ comment{ url } } }' \
  -f id=<スレッド ID> -F body=@<PRDIR>/reply-<ID>.md

# 総評の行（スレッドが無いので PR の会話コメントにする）
gh pr comment <number> --body-file <PRDIR>/reply-<ID>.md
```

投稿したら、台帳の追い返信の数を 1 増やし、状態を `待ち` に戻す。**投稿の前に数を見る** — 既に 2 なら投稿せず、
冒頭の歯止めのとおり AskUserQuestion で聞く。

台帳の判定の列に、判定と根拠と、投稿した返信の URL を書く。`since` を `events.json` の `next_since` に進める。

**完了条件**: 判定した全行が resolve 済み・確認済み・追い返信済みのどれかになり、台帳の `since` が `next_since` に進んでいる。
状態が `待ち` の行が残っていれば F2 へ戻る。残っていなければ F5 へ。

## 手順 F5 — approve する

**最後の見直し。** スレッドごとの確認は指摘箇所しか見ていない。レビュー時の head から今の head までの差分を、
今の PR のファイルに絞って読む（base を取り込むマージの変更を除くため）。

```bash
gh pr diff <number> --name-only > <PRDIR>/files-now.txt
git -C "<WT>" diff <レビュー時の head>..HEAD -- $(cat <PRDIR>/files-now.txt)
```

rebase で `レビュー時の head` が今の履歴から消えていれば（`git merge-base --is-ancestor` が通らない）、
先に `git range-diff <旧 base>..<レビュー時の head> <新 base>..<今の head>` で、レビューしたコミットが rebase 後も
同じ中身か（行頭が `=`）を確かめる。旧 base は手順 2 の `origin/<baseRefName>`、新 base は
`git merge-base origin/<baseRefName> HEAD`。全部 `=` なら、読むのは rebase 後に積まれたコミットの差分だけでよい。
`!` が混じるか対応が取れなければ、`gh pr diff <number>` の全体を読む。

見るのは review-standard.md の **A（壊れる）だけ**。B・C は初回のレビューの範囲で、追跡で新たに出すと終わりが来ない。

- A が無い → 下の approve へ
- A がある → 関係するスレッドがあれば unresolve してそこへ、無ければ PR の会話コメントで `issue (blocking)` を返す
  （F4 と同じ書式）。台帳に行を足し（ID は `fu-1` から振る）、F2 へ戻る

**approve の直前に head を取り直す。** 見直した head と違えば、新しいコミットが積まれている。F3 からやり直す。

本文は [`comment-format.md`](comment-format.md) の「approve の本文」に沿って `<PRDIR>/approve.md` に書く。

```bash
gh api graphql -f query='
mutation($prId:ID!,$oid:GitObjectID!,$body:String!){
  addPullRequestReview(input:{pullRequestId:$prId, commitOID:$oid, event:APPROVE, body:$body}){
    pullRequestReview{ url state commit{ oid } } } }' \
  -f prId=<PR の node ID> -f oid=<見直した head> -F body=@<PRDIR>/approve.md
```

返る `state` が `APPROVED` で、`commit.oid` が見直した head なら成功。台帳の状態を「approve 済み（マージ待ち）」にし、
確かめた head を更新する。

**完了条件**: `state` が `APPROVED` になり、レビューの URL が返っている。F6 へ。

## 手順 F6 — マージを待つ

approve した後も、PR がマージかクローズされるまで待つ。F2 と同じく **Bash の `run_in_background: true`、
`timeout: 7200000`** で起動し、`--head` に approve した commit を渡す — approve の後の push で起きるようにするため。

```bash
python3 ~/.claude/skills/pr-review/scripts/wait_for_replies.py \
  --repo <owner>/<repo> --number <number> --since <follow.md の since> \
  --head <follow.md の確かめた head> --out <PRDIR>/events.json
```

| 終わり方 | 次の一手 |
| --- | --- |
| 0（`reason: closed`） | F7 へ |
| 0（`head_changed: true`） | 下の「approve の後に push されたとき」。返信も届いていれば、その後に次の行と同じに扱う |
| 0（返信・会話・再依頼） | F3・F4 と同じに扱う。台帳の行が `待ち` に戻れば F2 へ、戻らなければ `since` を進めて F6 を起動し直す |
| 3 | 同じ引数で起動し直す |
| 1 | F2 と同じ |

起動したら、会話に 1 行だけ書く — マージを待っていること、セッションを閉じると止まること、再開のしかた。

### approve の後に push されたとき

worktree を今の head に合わせ、確かめた head から今の head までの差分を F5 の「最後の見直し」と同じやり方で読む
（rebase されていれば `range-diff` から）。見るのは A（壊れる）だけ。

- A がある → F5 と同じく指摘を返し、台帳の状態を「追跡中」に戻して F2 へ
- A が無い → 自分の approve がまだ有効かを確かめる。ブランチ保護で「push で approve を取り消す」設定なら、`DISMISSED` になっている

```bash
gh api graphql -f query='
query($owner:String!,$repo:String!,$number:Int!){ viewer{ login }
  repository(owner:$owner,name:$repo){ pullRequest(number:$number){
    latestOpinionatedReviews(first:20){ nodes{ author{ login } state commit{ oid } } } } } }' \
  -F owner=<owner> -F repo=<repo> -F number=<number>
```

自分（`viewer.login`）のレビューが `APPROVED` ならそのままでよい。`DISMISSED` なら、F5 の approve を今の head で出し直す
（本文は comment-format.md の「approve の本文」の、出し直しの形）。どちらでも、台帳の確かめた head を今の head に更新し、
F6 を起動し直す。

**完了条件**: スクリプトが `reason: closed` で終わった。

## 手順 F7 — 後始末して報告する

**片付けるのは、このスキルが作ったものだけ。** 作者のブランチ・連結 issue・他人のレビューには触れず、状態を報告するだけにする。

1. 手順 2 で worktree を作ったなら `git worktree remove "<WT>"` で消す。消えなければ（中に変更がある等）`--force` を付けずに、
   理由を報告に書く。続けて `git worktree prune` を実行する。
2. 待機スクリプトが動いていないことを確かめる（`closed` で終わっていれば止まっている）。
3. PR と連結 issue の状態を取る（`gh pr view --json closingIssuesReferences` は issue の `state` を返さないので GraphQL で取る）。

```bash
gh api graphql -f query='
query($owner:String!,$repo:String!,$number:Int!){ repository(owner:$owner,name:$repo){ pullRequest(number:$number){
  state mergedAt closingIssuesReferences(first:10){ nodes{ number state } } } } }' \
  -F owner=<owner> -F repo=<repo> -F number=<number>
```

4. 台帳の状態を「マージ済み（<mergedAt>）」か「クローズ（未マージ）」、または F2・F4 で止めた理由にする。`.scratch/pr-<number>/` は
   記録として残す（@ISSUE.md）。

`<PRDIR>/follow.md` に結果を書き戻してから報告する。

- 終わり方 — マージされた（日時）／マージされずにクローズされた／追い返信の上限で止めた／待機が失敗した
- approve の URL と、承認した commit（出し直したなら両方）
- resolve した件数と、そのうち「指摘の誤り」だった件
- 追い返信した行と、その返信の URL
- F5・F6 の見直しで足した指摘
- 後始末したもの（worktree）と、触れずに状態だけ確かめたもの（連結 issue が閉じているか）
- 申し送り — 台帳の「申し送り」の全件を、返信の URL を添えて。マージ後に誰が拾うかを人が決められるようにする
- 台帳のパス（`<PRDIR>/follow.md`）

## 入口

| 状況 | 入り方 |
| --- | --- |
| 手順 7 で「submit してマージまで追跡する」が選ばれた | 手順 8 の submit の直後に F1 から |
| submit 済みのレビューの追跡だけを頼まれた（`follow.md` が無い） | 手順 1 で PR の情報を取り、手順 2 の worktree を作ってから F1 へ。`ledger.md` が無ければ、自分のスレッドを 1 行ずつ台帳にし、ラベルは各スレッドの 1 行目から取る |
| 中断した追跡の再開を頼まれた（`follow.md` の状態が「追跡中」） | worktree が無ければ手順 2 のとおり作り直し、F2 から。中断していた間の返信は、台帳の `since` より後なので拾える |
| 中断したマージ待ちの再開を頼まれた（`follow.md` の状態が「approve 済み（マージ待ち）」） | worktree が無ければ作り直し、F6 から。中断していた間の push も `--head` との差で拾える |
