---
name: pr-comments
description: PR のレビューコメントを抽出し、コードベースの一次情報で妥当性を検証して、今対応が必要なものだけを修正・push・返信する。WHEN - PR の URL や番号を渡して「コメントを見て対応して」と言われた、レビュー指摘が妥当か判断したい、CodeRabbit などの bot 指摘を仕分けたい、PR の未解決スレッドを片付けたい。
---

# PR コメントの仕分けと対応

レビュー指摘を鵜呑みにして直す — それが既定の失敗。**指摘の妥当性をコードベースの一次情報で確かめ、今対応すべきものだけを直す。**

判定と実行を分ける。手順 1〜6 で全件を仕分けて人間の承認を取り、手順 7 以降で実行する。

## 承認を得るまで実行しない操作

次はユーザーの承認を得てから実行する。承認が得られなければ実行せず、レポートに「未実行」と記録して他を進める。

- `git push`（手順 8 で承認を取る）
- GitHub スレッドへの返信・PR コメント投稿（手順 9）
- `gh issue create`（手順 9）

`git commit` はローカルに閉じるので手順 7 の承認に含まれる。**スレッドの resolve はレビュアーが押すもの**として、返信までで手を止める。

## 手順 1 — 前提を固める

1. 引数の URL または番号から `owner` / `repo` / `number` を取る。
2. `git remote get-url origin` と `owner/repo` を照合する。**不一致なら手を止め、AskUserQuestion で確認する** — 別リポジトリのコードを読んで判定しても意味がない。
3. `gh pr view <number> --json headRefName,state,mergeable` と `git branch --show-current` を照合する。ブランチが違えば `gh pr checkout <number>` の実行可否を AskUserQuestion で確認する。
4. `git status --porcelain` が空でなければ、未コミットの変更をどう扱うか AskUserQuestion で確認する。

**完了条件**: 対象リポジトリ・対象ブランチ・作業ツリーの状態の 3 点すべてを確認済み。

## 手順 2 — スコープを確定する

`closingIssuesReferences` と PR 本文から「**この PR が達成するもの**」を 2〜3 行で書き出す。これが手順 5 で「今対応」と「別チケット」を分ける基準になる。

```bash
gh api graphql -f query='
query($owner:String!,$repo:String!,$number:Int!){
  repository(owner:$owner,name:$repo){ pullRequest(number:$number){
    title body baseRefName headRefName
    closingIssuesReferences(first:10){ nodes{ number title body } }
  }}}' -F owner=OWNER -F repo=REPO -F number=N
```

PR 本文にも連結 issue にも意図が書かれていなければ、`gh pr diff <number> --name-only` の範囲をスコープとし、**レポートに「PR に意図の記述が無いため diff 範囲をスコープとした」と明記する**。

**完了条件**: スコープが 2〜3 行の文になっており、その根拠（PR 本文 / issue 番号 / diff 範囲のいずれか）が書かれている。

## 手順 3 — コメントを抽出する

対象は **未解決のレビュースレッド**と**レビュー総評**。人間・bot の両方を拾い、`author.__typename` で `User` / `Bot` のラベルを付ける。

```bash
gh api graphql --paginate -f query='
query($owner:String!,$repo:String!,$number:Int!,$endCursor:String){
  repository(owner:$owner,name:$repo){ pullRequest(number:$number){
    reviews(first:50){ nodes{ author{login __typename} state body url submittedAt } }
    reviewThreads(first:50, after:$endCursor){
      pageInfo{ hasNextPage endCursor }
      nodes{
        id isResolved isOutdated path line originalLine diffSide
        comments(first:20){ nodes{ author{login __typename} body url diffHunk } }
      }
    }
  }}}' -F owner=OWNER -F repo=REPO -F number=N
```

仕分けの規則:

- `isResolved: true` のスレッドは対象外。件数だけ数えてレポートに載せる。
- `reviews` のうち `body` が空のもの（Approve のみ等）は対象外。
- 1 スレッド = 1 判定単位。スレッド内の後続コメント（レビュアー自身の補足や撤回）まで読んでから判定する。
- レビュー総評は 1 件 = 1 判定単位。総評に複数の論点があれば論点ごとに分ける。

**完了条件**: 判定単位の一覧ができており、各件に「スレッド ID / ファイルと行 / 人間か bot か / 本文」が揃っている。

## 手順 4 — 解消済みを先に仕分ける

サブエージェントに投げる前に、各判定単位について `diffHunk` と **HEAD の現在のコード**を照合する。

- 指摘された内容が現在のコードで既に直っている → **解消済み**
- `isOutdated: true` で、かつ指摘対象のコードが現在のコードから消えている → **解消済み**
- `isOutdated: true` だが指摘の本質（設計・命名・エラー処理の方針など）が現在のコードに残っている → **判定に進める**

行がずれただけのものを解消済みに落とすと、本質が未解決の指摘を取りこぼす。**判断の根拠は「現在のコードを読んだ結果」に限る** — `isOutdated` フラグ単独では解消済みにしない。

**完了条件**: 全判定単位が「解消済み」または「判定に進める」に振り分けられ、解消済みの各件に現在のコードの該当箇所（`path:line`）が根拠として付いている。

## 手順 5 — 並列で検証する

`pr-comment-verifier` サブエージェントに、判定に進める件を **3〜5 件ずつ束ねて**投げる。同じファイルに関する指摘は同じ束にまとめ、同じファイルを何度も読ませない。

各サブエージェントへ渡すもの:

- 手順 2 のスコープ（2〜3 行）
- 束に含む各件の本文・`path:line`・`diffHunk`・人間 / bot ラベル

サブエージェントは**事実と出典だけを返す**。分類は返させず、手順 6 で自分が決める。

**完了条件**: 判定に進めた全件について、サブエージェントから事実と出典（`path:line`）が返ってきている。返って来ない件があれば自分で調べて埋める。

## 手順 6 — 分類してレポートを書く

各件を 4 分類のいずれかに置く。

| 分類 | 条件 | 手順 9 での行動 |
| --- | --- | --- |
| **今対応** | 指摘が妥当で、かつ手順 2 のスコープの内側 | 修正し、コミット SHA を添えて返信 |
| **別チケット** | 指摘が妥当だが、スコープの外側（別の機能・既存の技術的負債・大きなリファクタリング） | 起票し、issue リンクを添えて返信 |
| **対応不要** | 指摘が現在のコードに当たらない、誤検知、またはこのリポジトリの既存の慣習と衝突する | 却下理由と出典を添えて返信 |
| **判断保留** | 妥当性がコードだけでは決まらない（仕様の意図、チームの方針、外部の制約に依存する） | 質問として返信 |

判定に効く規則:

- **出典が無い主張は「今対応」に置かない。** 妥当と判断した根拠は必ず `path:line` か外部仕様の URL で示す。bot の指摘も人間の指摘も同じ基準（@EVIDENCE.md）。
- **一般論と既存の慣習が食い違えば既存の慣習が勝つ**（@PRACTICE.md）。同型のコードがリポジトリに存在することを出典に「対応不要」と判定できる。bot が持ち込む一般論はここで落ちることが多い。
- スコープ外かどうかは**手順 2 で書いたスコープの文と照らして**決める。diff に含まれるファイルであっても、PR の目的と無関係な指摘はスコープ外。

レポートを `.scratch/pr-<番号>/report.md` に書く。中身は分類表（1 行 1 件、スレッド ID・分類・根拠・出典）と、手順 4 の解消済み一覧、手順 2 のスコープ。`.scratch/` が `.gitignore` に載っていなければ、手順 7 のコミットに巻き込まないよう `git add` はソース差分のみを対象にする。

書き終えたら分類表を会話に提示し、**AskUserQuestion で「どれを対応するか」の承認を取る**。ユーザーが分類を覆したらレポートを更新してから進む。

**完了条件**: 全件が 4 分類または解消済みに置かれ、各件に出典が付き、レポートがファイルに存在し、承認を得ている。

## 手順 7 — 修正してコミットする

「今対応」の各件を修正する。**1 コメント = 1 コミット**。

- コミットメッセージの書式は `git log --oneline -20` で既存の慣習に合わせる。
- 本文にスレッドの URL を 1 行入れ、どの指摘への対応かを辿れるようにする。
- 修正が他箇所に波及する識別子・設定値・ドキュメントに触れたら `consistency-check` スキルを回す。

**完了条件**: 「今対応」の全件がコミット済み。テストコマンドがリポジトリにあれば実行し、結果をレポートに記録する。

## 手順 8 — push の承認を取る

`git log --oneline <base>..HEAD` と `git diff --stat <base>..HEAD` を提示し、**AskUserQuestion で push の承認を取る**。承認後に `git push` する。

**完了条件**: push 済み、または未承認としてレポートに記録済み。

## 手順 9 — 返信と起票

返信文とコマンドは [`references/reply.md`](references/reply.md) に従う。

**完了条件**: 4 分類の全件に返信済み（または未承認として記録済み）、「別チケット」の全件が起票済み。

## 手順 10 — 報告する

レポートへ実行結果を書き戻してから報告する（@ISSUE.md）。報告に含めるもの:

- 分類ごとの件数と、解消済みで落とした件数
- push したコミットの範囲
- 起票した issue の番号
- 「判断保留」に置いた件と、ユーザーに判断してもらう論点
- 承認が得られず未実行にした操作
