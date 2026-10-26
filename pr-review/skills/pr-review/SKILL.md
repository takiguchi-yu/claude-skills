---
name: pr-review
description: PR をレビューし、指摘を pending（下書き）で GitHub に置いて、人の確認後に submit する。WHEN - PR の URL や番号とともにレビューを頼まれた（投稿すると明言されていなくても）、下書きのレビューを submit したい、submit したレビューへの返信を確かめて resolve・approve し、マージ後の後始末まで追跡したい。受けた指摘に対応する側は pr-comments を使う。
---

# PR をレビューして pending 経由で投稿する

**一度に公開しない。** 指摘を pending レビュー（下書き）として PR に置き、人が GitHub 上で
現物を見て納得してから submit する。pending は投稿者にしか見えないので、誤爆も的外れも
公開前に消せる。この 2 段構えが、このスキルの存在理由そのもの。

**指摘は基準で選ぶ。** 改善の余地は探せばキリがなく、レビューに使う時間とトークンは実装に回すほうが価値が高い。
そこで [`references/review-standard.md`](references/review-standard.md)（Google Engineering Practices の
The Standard of Code Review に沿った基準）を超える指摘だけを出す。レビュー役も採否も、毎回この同じ基準で選ぶ。

レビューの中身は、本体（Standards 軸。規約は `/code-review` が集める）、`/code-review`（Spec 軸）、`/security-review`（脆弱性）、同梱のエージェント
`pr-review-functionality`（Functionality・Complexity・Tests）が見る。このスキルの責務は、**指摘を台帳に集め、行き先を決め、
diff 上の正しい位置に結びつけ、下書きとして置き、承認を得て公開すること**。手順 7 で追跡が選ばれたら、
submit 後に返信を確かめて resolve し、approve し、マージを待って後始末するところまでを持つ（[`references/follow-up.md`](references/follow-up.md)）。

## 承認を得るまで実行しない操作

- **submit（手順 8）** — 実行した瞬間にレビュイーへ通知が飛ぶ。手順 7 で承認を取る。
- **既存 pending レビューの破棄（手順 1）** — 人が手で書いた下書きかもしれない。

pending への投稿（手順 6）は下書きなので承認は要らない。ただし手順 5 で必ず位置を検証してから投げる。
追跡の resolve・追い返信・approve・後始末は、手順 7 で「submit してマージまで追跡する」が選ばれた時点で承認済みとして扱い、
1 件ずつは聞かない。代わりに follow-up.md の歯止めに従う。

## 手順 1 — 前提を固める

1. 引数の URL または番号から `owner` / `repo` / `number` を取る。番号だけ渡されたら
   `git remote get-url origin` から `owner/repo` を補う。
2. PR の基本情報、**自分の既存レビュー**、**PR 上の既存スレッド**を 1 回で取る。

```bash
gh api graphql -f query='
query($owner:String!,$repo:String!,$number:Int!){
  viewer{ login }
  repository(owner:$owner,name:$repo){ pullRequest(number:$number){
    id number title url state isDraft body
    author{ login }
    baseRefName headRefName headRefOid
    closingIssuesReferences(first:10){ nodes{ number title body } }
    reviews(states:[PENDING], first:10){ nodes{ id url } }
    submitted: reviews(states:[COMMENTED,APPROVED,CHANGES_REQUESTED], last:20){
      nodes{ author{ login } state commit{ oid } submittedAt url body } }
    reviewThreads(first:100){ totalCount pageInfo{ hasNextPage endCursor }
      nodes{ path line isResolved isOutdated comments(first:1){ nodes{ author{ login } body url state } } } }
  }}}' -F owner=OWNER -F repo=REPO -F number=N
```

- `pullRequest.id` が手順 6 で要る PR の node ID。
- `author.login` が手順 8 のメンション先。
- `body` と `closingIssuesReferences` が PR の意図。手順 2 で `intent.md` に書き出してレビュー役に渡す。
- `reviews(states:[PENDING])` が空でなければ**既に自分の下書きがある**。pending レビューは
  作った本人にしか見えないので、ここに出るのは必ず自分のもの。新しく作ると二重になるため、
  AskUserQuestion で「そこへ足す / 破棄して作り直す / 中止」を確認する。
  破棄は `deletePullRequestReview(input:{pullRequestReviewId:$id})`。
- `submitted` に、`author.login` が `viewer.login` で `body` が空でないレビューがあれば**再レビュー**。
  手順 2 に進む前に [`references/re-review.md`](references/re-review.md) を読む（手順 2・3・4・8 に足す作業がある）。
  スレッドへの返信だけのレビューは `body` が空なので、これで除ける。
- `reviewThreads` と、`submitted` の `body`（過去の総評）が PR 上の既存の指摘。手順 4 で「既出」の判定に使う。
  コメントの `state` が `PENDING` のスレッドは自分の下書きなので、既出の判定には使わない。
  `pageInfo.hasNextPage` が true なら、`reviewThreads(first:100, after:<endCursor>)` でページを送って全件取る。
- `state` が `MERGED` / `CLOSED`、または `isDraft` が true なら、レビューを投稿してよいか
  AskUserQuestion で確認する。

3. `git remote` が対象リポジトリを指していることを照合する。違えば手を止めて確認する。
   メインの作業ツリーはブランチも未コミットの変更もそのまま残す — レビューは手順 2 で作る worktree で行う。

**完了条件**: PR の node ID・author・URL・`headRefOid` が手元にあり、既存 pending レビューの有無、
再レビューかどうか、既存スレッドの一覧を確認済み。

## 手順 2 — diff を確保してレビューを回す

**レビューはメインの作業ツリーではなく worktree で行う。** `/code-review` は
`git diff <fixed-point>...HEAD` で差分を取り、周辺のコードもリポジトリから読む。HEAD が PR の head で
なければ、別の差分とコードをレビューしてしまう。一方でメインの作業ツリーで `gh pr checkout` すると、
進行中の作業のブランチと未コミットの変更を巻き込む。そこで PR の head を別の worktree に取り出す。
`$SCRATCH` はセッションの scratchpad ディレクトリ（システムプロンプトで与えられているパス）を指す。

ただし、今の作業ツリーの HEAD が `headRefOid` と一致し、`git status --porcelain` が空なら、worktree を作らずに
今の作業ツリーを `$WT` として使う（巻き込む作業が無く、同じコードを読むため）。手順 9 の片付けも要らない。

```bash
WT="$SCRATCH/pr-<number>-wt"
git fetch origin <baseRefName>
git worktree add --detach "$WT" origin/<baseRefName>
cd "$WT" && gh pr checkout <number> --detach && git rev-parse HEAD
```

`--detach` を付けるのは、head ブランチがメインの作業ツリーで既にチェックアウトされていると、
同じブランチを 2 つ目の worktree に出せないため。出力された HEAD が `headRefOid` と一致することを確かめる。
一致したら元のディレクトリへ戻る — 以降の `.scratch/` はメインの作業ツリー側に置く。
シェル変数は Bash の呼び出しをまたいで残らないので、以降の `$WT` と、下で作る `$PRDIR` は展開済みの絶対パスで書く。

diff は手順 5 の検証でも使うので、先にファイルへ落とす。**`git diff` ではなく `gh pr diff` を使う** —
GitHub がコメント位置を計算するのは PR の diff（マージベースとの比較）なので、
ここがずれると位置が全部ずれる。

```bash
PRDIR="$(pwd)/.scratch/pr-<number>"
if [ -n "$(ls -A "$PRDIR" 2>/dev/null | grep -v '^prev-')" ]; then  # 前回の実行のファイルを退避する
  P="$(mktemp -d "$PRDIR/prev-$(date +%Y%m%d-%H%M%S)-XXXX")"
  find "$PRDIR" -mindepth 1 -maxdepth 1 ! -name 'prev-*' -exec mv {} "$P"/ \;
fi
mkdir -p "$PRDIR"
gh pr diff <number> > "$PRDIR/pr.diff"
gh pr diff <number> --name-only > "$PRDIR/files.txt"
git -C "$WT" log --oneline origin/<baseRefName>..HEAD > "$PRDIR/commits.txt"
```

手順 1 で取った PR 本文と連結 issue を `$PRDIR/intent.md` に書く。本文が Jira などのチケットを
指していれば、その本文も読んで足す。

`.scratch/pr-<番号>/` を作業場所にする。`.gitignore` に載っていなければ、`.git/info/exclude` に `.scratch/` を足す。
前回の実行のファイルを `prev-<日時>/` へ移すのは、上書きや追記で前回の台帳が崩れるのを防ぐため。
レビュー役は `$WT` で動くので、`$PRDIR` 配下のファイルは**展開済みの絶対パス**で渡す。

### レビュー役を立てる

次の 3 体を**同じメッセージで並列に**立てる。Skill ツールで `code-review` を起動し、
`/code-review` の Process 4（Spawn both sub-agents in parallel）では **Spec のサブエージェントだけ**を立て、
同じメッセージで機能面とセキュリティのレビュー役も立てる。Standards 軸は、3 体の報告が返った後に本体が見る（下の「Standards 軸を本体で見る」）。

**メインセッションの cwd はメインの作業ツリーに置いたまま立てる**（立てる前に `pwd` で確かめる）。
レビュー役には `$WT` を絶対パスで渡すので、`$WT` へ `cd` する必要は無い。`/security-review` は起動時に
メインセッションの cwd が git リポジトリかを確かめて、違えば中止する。scratchpad の `$WT` へ `cd` すると cwd が
セッション開始時のディレクトリに戻されることがあり、戻った先がリポジトリの外だと中止になった。

| レビュー役 | 立て方 | 見るもの |
| --- | --- | --- |
| Spec（1 体） | `/code-review` が立てる。固定点は `origin/<baseRefName>` | 仕様との差分 |
| Standards（本体） | 下の「Standards 軸を本体で見る」 | 規約違反と smell |
| 機能面（1 体） | Agent ツールで `subagent_type: pr-review-functionality` | 正しさ・異常系／複雑さ／変更した挙動のテスト |
| セキュリティ（1 体） | Agent ツールで `subagent_type: general-purpose`・`model: opus`。中で `/security-review` を起動する | この PR で入った、悪用経路のある脆弱性 |

**機能面のレビュー役の prompt には入力だけを書く** — `$WT`、固定点 `origin/<baseRefName>`、
`$PRDIR` の `pr.diff` `files.txt` `commits.txt` `intent.md`。見方・基準・出力形式はエージェント定義が
持っているので、入力だけを渡せば毎回同じレビューになる。

**`/code-review` の SKILL.md は編集しない。** Spec に渡す brief は `/code-review` の
文面どおりに書き、その末尾に次の節を**この文面のまま**足す（`<worktree の絶対パス>` だけは展開して書く）。以前のレビューで出た指摘の一覧は
brief に入れない — 重複の整理は手順 3・4 で台帳がやる。

```markdown
## 報告のしかた（この節は、上の brief にある語数の上限・省略・引用の指示より優先する）

- 最初に ~/.claude/skills/pr-review/references/review-standard.md を読む。
- 返すのは ~/.claude/skills/pr-review/references/review-standard.md の「出すもの」A〜C に当たる指摘だけ。
  当たるものは全件返し、語数と件数の上限は無い。「出さないもの」は返さない。
- 出力形式は ~/.claude/agents/pr-review-functionality.md の「出力形式」節に従う。
  ID の接頭辞は spec。コードは貼らずに path:line で指す。
- git コマンドは `git -C <worktree の絶対パス>` で実行し、ファイルは worktree 配下の絶対パスで読む。
```

**PR が下の表（条件付きの標準の出典）の条件に当たれば、`/code-review` の Process 3 で集める標準の出典に、その行の出典を足す。**
当たった行があれば [`references/conditional-sources.md`](references/conditional-sources.md) を読み、その行の節に従って
出典を落とし、本体が Standards 軸を見るときに、その出典と添え書きも読む。

| 条件 | conditional-sources.md の節 |
| --- | --- |
| `files.txt` にエージェントが読む文書がある — `SKILL.md`・`CLAUDE.md`・`AGENTS.md`、スキル・エージェント・ルールの定義とその参照先（`.claude/` や `skills/` `agents/` 配下の `.md` など） | writing-for-agents |
| `pr.diff` が設計に手を入れている — 新しいコードのファイル・モジュール・クラスの追加か、公開インターフェース（外から呼ばれる関数のシグネチャ・型・API・設定キー）の変更。`oo-design` 自身の発動条件に揃えてある | oo-design |
| `files.txt` に画面のファイルがある — 利用者が見る見た目・文言・操作を変えるもの（`.tsx` `.jsx` `.vue` `.svelte` `.css` `.scss` `.html`、サーバ側のテンプレートなど）。差分がフック・API 呼び出し・型定義だけなら当たらない | Web Interface Guidelines |
| 変更したファイルが属する `package.json` の依存に `react` か `next` があり、`pr.diff` がコンポーネント・ページ・データ取得・Server Action を変えている | React Best Practices |

**セキュリティのレビュー役の prompt は、次の文面のまま書く**（`<WT>` `<PRDIR>` は展開した絶対パス）。
`/security-review` は組み込みのスキルなので、中身はこのスキルに写さずに起動して使う。ただし、組み込みの指示に埋め込まれる
`git diff origin/HEAD...` などは、サブエージェントの `cd` 先ではなく**メインセッションの cwd で**実行される
（Claude Code 2.1.302 で、サブエージェントから起動して確かめた）。差分の基点も `origin/HEAD` で、PR のベースと限らない。
そこで差分は `$PRDIR` のファイルに差し替える。

```markdown
Skill ツールで `security-review` を起動し、その指示どおりにセキュリティレビューをする。ただし次を優先する。

- 指示に埋め込まれた GIT STATUS・FILES MODIFIED・COMMITS・DIFF CONTENT は別の作業ツリーの内容なので使わない。
  レビューする差分は <PRDIR>/pr.diff、変更ファイルの一覧は <PRDIR>/files.txt、コミットの一覧は <PRDIR>/commits.txt。
- コードは <WT> 配下の絶対パスで読み、git は `git -C <WT>` で実行する。
- 立てるサブタスクの prompt にも、埋め込みの 4 節の代わりに上の 3 ファイルと <WT> のパスを書く。
- 最終の返答は、脆弱性を探すサブタスクと、誤検知を除くサブタスクの結果がすべて返ってから書く。
- 最終の返答は /security-review の報告（markdown）だけにする。`security-review` を起動できなかったら、エラー文だけを返す。
```

`files.txt` が `.md` だけなら、セキュリティのレビュー役は立てない（`/security-review` は文書への指摘を除外する）。
手順 9 で「セキュリティは文書だけの PR のため未実施」と報告する。エラー文だけが返ったときも未実施として、エラー文を理由に控える。

Spec のサブエージェントは `model: opus` で立てる（`pr-review-functionality` は定義で opus に固定してある）。
手順 4・5 でコードを読み直すときも `$WT` 配下のパスを読む。

`/code-review` は Spec 軸のために `docs/agents/issue-tracker.md` を要求する。無いリポジトリでも、
PR 本文や連結 issue に完了条件が書いてあれば、それを spec として渡す。spec が何も無ければ
**Standards 軸だけで進め、手順 9 で「Spec 軸は spec が見つからず未実施」と報告する** — レビューは Spec 軸が無くても成立する。
`/code-review` が spec の場所を尋ねる場面でも、`intent.md` を spec として渡して進める。

### Standards 軸を本体で見る

3 体の報告が返ったら、本体が次の順で見る。

1. `/code-review` の Process 3（Identify the standards sources）で集めた規約文書と smell baseline、上の表で当たった出典と添え書きを読む
2. `$PRDIR/pr.diff` を、規約の 1 条ずつ・smell の 1 項目ずつと突き合わせ、`$PRDIR/standards-check.md` に 1 条 1 行で「該当」か「非該当」かを書く。該当 1 件を Standards の指摘 1 件とする
3. 指摘を `references/review-standard.md` の「出すもの」に当たるものに絞り、残った 1 件ずつに ID（`std-`）・場所（path:line）・要点（何が規約に反するか）・区分・根拠（規約のファイルと条）・直し方の案を控える。`standards-check.md` の該当の行には、その ID か、絞って外した理由を書き足す。他のレビュー役の報告と同じ項目なので、手順 3 の台帳にそのまま写せる

**完了条件**: HEAD が `headRefOid` と一致し、`$PRDIR` に `pr.diff` `files.txt` `commits.txt` `intent.md`
があり、3 体の報告が手元にある（Spec 軸とセキュリティは未実施でもよい。その場合は理由が控えてある）。
`standards-check.md` に規約文書の全条と smell baseline の全項目が載り、該当の行にはすべて `std-` の ID か外した理由がある。
条件付きの標準の出典の表の全行について、当たったかと、当たった行の出典と添え書きを本体の Standards 軸で読んだか（読めなかったなら理由）が控えてある。
機能面の報告の「網羅」に `files.txt` の全ファイルが載っている。欠けたファイルがあれば、機能面のレビュー役を
入力の「対象ファイル」に欠けた一覧を渡して 1 回だけ立て直す（それでも欠けたら、手順 9 で欠けたファイルを報告する）。

## 手順 3 — 台帳に集める

3 体の報告に出た指摘と、本体が控えた Standards の指摘を、**1 指摘 = 1 行**の台帳 `.scratch/pr-<number>/ledger.md` に集める。
このレビューの指摘の置き場所は台帳だけにする。報告は保存しないので、コメント本文を書くのに要る根拠と
直し方の案も台帳に写す。手順 4 以降は台帳から読む。

```markdown
| ID | 出所 | 場所 | 要点 | 区分 | 根拠・直し方 | 行き先 | 理由 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| std-1 | Standards | app.py:13 | 規約で禁じた層をまたぐ import | B | architecture.md の層規約。usecase 経由にする | | |
| fn-2 = spec-3 | 機能面, Spec | app.py:40 | 空配列で先頭要素を参照して panic する | A | 呼び出し元 api.py:22 は空を渡しうる。len を検査 | | |
```

- ID は報告の ID（`std-` `spec-` `fn-`）をそのまま使う。`/security-review` の `Vuln <N>` は `sec-<N>` にする。
  立て直したレビュー役は番号を 1 から振ってくるので、台帳に足すときに接頭辞ごとの続き番号へ振り直す。
  区分は review-standard.md の A〜C（`/code-review` の報告に区分が無ければ、ここで当てる。`sec-` は A。
  A〜C のどれにも当たらない行は「—」）。
- 報告の指摘は全部載せる。行き先と理由の列は手順 4 で埋める。
- 同じ場所・同じ論点が複数の報告から出たら 1 行にまとめ、ID の列に全部の ID を `=` でつないで書く。
  同じ種類の誤りを複数箇所まとめた指摘は、残りの箇所の `path:line` を根拠・直し方の列に写す。
  別の報告の指摘がその残りの箇所の 1 つを指していれば、それも同じ行にまとめる。

**完了条件**: 3 体の報告と本体の Standards の指摘が、すべて台帳のどこかの行にある（まとめた行は ID の列に全部の ID があり、同じ種類の誤りをまとめた行は残りの箇所が根拠・直し方の列にある）。

## 手順 4 — 行き先を決めてインラインコメントに変換する

**台帳の全行に行き先を 1 つ付ける。** レビュー役の指摘の採否を決めるのはこの手順だけ（人による却下は手順 7）。

| 行き先 | 当てはまるもの |
| --- | --- |
| インライン | 行を特定できる指摘。行を 1 つに絞れずファイル単位でしか言えないものも含む（手順 5 の `subject_type: FILE`） |
| 総評（手順 8） | 行に紐づかないもの。ファイル横断の設計上の指摘、diff に現れない不足（テストが無い、ドキュメント未更新）、PR 全体の所感 |
| 不採用 | 下の 5 つの理由のどれかに当たるものだけ |

不採用にするときは、理由と、括弧内の根拠を理由の列に書く。

- **反証済み** — コードを読み、指摘の主張が事実でないと確かめた（確かめた `path:line`）
- **基準未満** — review-standard.md の「出さないもの」のどれかに当たる（どの項目か。既存と同型なら同型コードの `path:line`、
  作者が判断済みなら PR 本文の該当箇所）。レビュー役が基準で選んでいても、ここでもう一度当てる
- **重複** — 台帳の別の行と同じ論点（まとめ先の ID）
- **既出** — 手順 1 で取った既存スレッドか過去の総評が、同じ論点を既に扱っている（そのスレッドかレビューの URL）。
  resolved 済みのスレッドなら、理由の列にそう書く — 直っていないのに resolve された可能性を、手順 7 で人が見られるように
- **却下** — 手順 7 で人が下書きから外した（外した日と、人が述べた理由）

ラベルは区分から決める。対応は review-standard.md の「出すもの」表のラベル列、書式は
[`references/comment-format.md`](references/comment-format.md) に従う。
レビュイーに出すかどうかの最終判断は、手順 7 で人がする。

### インラインコメントに変換する

レビュー役が返すのは散文の報告なので、行き先がインラインの行を
**1 指摘 = 1 スレッド**にばらし、diff 上の位置を決める。

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

- `line` は **指摘が当たるコードの行**。レビュー役が引用したハンクの先頭ではない。
- `side` は変更後のコードなら `RIGHT`、**削除されたコードへの指摘なら `LEFT`**。
- 範囲で指すなら `start_line`（+ 必要なら `start_side`）を足す。`line` が範囲の終わり。
- `id` は台帳の ID をそのまま使う（まとめた行は先頭の ID）。API には送られない。

本文の書式は [`references/comment-format.md`](references/comment-format.md) に従う（Conventional Comments）。

**完了条件**: 台帳の全行に行き先があり、不採用の行には 5 つの理由のどれかと根拠がある。
`candidates.json` が存在し、行き先がインラインの行が 1 件ずつ入っていて、全件に `path` / `body` がある。
行を指す件には `line` / `side`、ファイル単位の件には `"subject_type": "FILE"` がある。

## 手順 5 — 位置を検証する

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
  → **`subject_type: FILE` でも投稿できない。** インラインを諦めて、台帳の行き先を総評（手順 8）に直す。
  diff に無いファイルへの指摘は、そもそもこの PR の変更ではないものを指している可能性が高いので、
  総評へ回す前に、手順 4 に戻って「基準未満」（PR の前からある問題）に当たらないかを確かめ直す。

全件が有効になるまで `candidates.json` を直して回し直す。終了コード 0 が通過の合図。

`⚠` で出る警告は**エラーではないので止まらない**。リネームされたファイルの旧パスを指したときに出る。
GitHub がリネーム時に旧パス・新パスのどちらを受け付けるかは公式ドキュメントに記載が無いため
（[REST docs](https://docs.github.com/en/rest/pulls/comments?apiVersion=2022-11-28) の `path` は
「コメント対象ファイルの相対パス」としか書かれていない）、投稿してみて 422 で落ちたら
警告が示す新パスに差し替える。

**完了条件**: 検証が終了コード 0 で通り、`validated.json` ができている。

## 手順 6 — pending として投稿する

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

手順 1 で既存の pending レビューに「そこへ足す」を選んだなら、`--pr-id` の代わりに `--review-id <その id>` で投稿する。

最後に出る `review_id` を控える。手順 8 で要る。

**完了条件**: 全件が投稿され、`review_id` が手元にある。

## 手順 7 — 手を止めて確認してもらう

**ここで止まる。** 確認先の URL を出す。pending コメントは Files changed タブに "Pending" として
表示され、投稿者にしか見えない。

```
<PR の URL>/files
```

会話には、台帳を行き先ごとに**全件**出す。

- インライン — `path:line` とラベルと要点の 1 行
- 総評 — 要点の 1 行
- 不採用 — 要点と、理由と根拠

不採用も件数に畳まずに 1 件ずつ出す。人が拾い直せるのはここだけ。
総評も comment-format.md の「submit の総評」に沿って `.scratch/pr-<number>/summary.md` に書き、全文を会話に出す。
そのうえで **AskUserQuestion で submit の可否を取る**。選択肢は
「submit してマージまで追跡する / submit する / 指摘を直してから submit / 破棄する」。
追跡を選ぶと、返信の確認・resolve・追い返信・approve・マージ後の後始末を人の確認なしで進めることを、選択肢の説明に書く。

**自分が作者の PR**（`author.login` が `viewer.login`）なら、選択肢の先頭に「投稿せずに直接直す」を足し、
「submit してマージまで追跡する」を外す（自分の PR は approve できない）。
自分宛てのレビューを公開しても受け手がいない。選ばれたら pending レビューを破棄し、指摘をコードか PR 本文で直す
（コミット・push はユーザーの承認の範囲で行う）。台帳の理由の列に、どう直したかを書く。

- 「直してから」なら手順 4〜6 に戻る。不採用からの拾い直しもここで受ける。既存スレッドの本文修正は
  `updatePullRequestReviewComment`、削除は `deletePullRequestReviewComment`。新しく足すスレッドだけを
  別の候補ファイルに入れて手順 5 で検証し、手順 6 は `--review-id <review_id>` で同じ pending レビューへ足す —
  `--pr-id` だけで回し直すと、投稿済みのスレッドが二重になる。拾い直した行は台帳の行き先を直し、
  下書きから外した行は行き先を不採用（却下）にする。
- 「破棄」なら `deletePullRequestReview(input:{pullRequestReviewId:$reviewId})` を実行し、
  手順 9 で「破棄した」と報告して終わる。

submit の直前に pending レビューのコメントを取り直し（`node(id:<review_id>){ ... on PullRequestReview{ comments(first:100){ nodes{ path line body } } } }`）、
人が GitHub の画面で消したスレッドがあれば、その行の行き先を不採用（却下）にし、総評の件数も合わせる。

**完了条件**: ユーザーの判断を得ている。得られていなければ submit しない。

## 手順 8 — submit する

submit の `body` がそのままメンション付きコメントになり、**同時に pending が解除**されて
インラインコメントが公開される。1 回の操作で両方が起きる。

総評の書式は [`references/comment-format.md`](references/comment-format.md) の「submit の総評」に従う。
**本文はファイルに書き、`-F body=@<path>` でファイルから読ませる。** `$(cat ...)` で渡すと、
本文に含まれるバッククォートをシェルがコマンド置換として実行してしまう。

**メンション先は、本文を書く直前に、その PR の `author.login` から取る。** 前の PR の作者や記憶から写さない —
同じ作者の PR が続いたあとに別の作者の PR が来ると、前の人に通知が飛ぶ（自動レビューで実際に起きた）。
書いたら、submit の前に照合する。この照合は、本文の最初のメンションを実装者に届ける投稿すべてに掛ける
（submit の総評、追跡の approve と総評への返信）。

```bash
python3 ~/.claude/skills/pr-review/scripts/check_mention.py \
  --repo <owner>/<repo> --number <number> --body .scratch/pr-<number>/summary.md
```

終了コード 0 が通過の合図。1 なら出力が示す login に直して照合し直す。2（作者を取得できない）なら投稿しない。

同じ照合は、PreToolUse フック `scripts/pretool_check_mention.py` が投稿コマンドの実行前にも掛ける（ユーザー設定に登録している場合）。
フックに止められたら、理由に示された宛先・渡し方に直して投稿し直す。本文は `-F body=@<file>` / `--body-file <file>` で、
PR は node ID（`PR_…` / `PRR_…`）か番号をリテラルで渡す — 変数で渡すとフックが特定できずに止める。

```bash
gh api graphql -f query='
mutation($reviewId:ID!,$body:String!){
  submitPullRequestReview(input:{pullRequestReviewId:$reviewId, event:COMMENT, body:$body}){
    pullRequestReview{ url state submittedAt commit{ oid } }
  }}' -f reviewId="<review_id>" -F body=@.scratch/pr-<number>/summary.md
```

**`event` は `COMMENT` を使う。** 指摘の深刻度は本文のラベル（`issue (blocking)` 等）で伝わる。
`APPROVE` はマージ可否に効く判定なので、指摘への対応を確かめた後に追跡（follow-up.md の F5）で出す。
`REQUEST_CHANGES` は、ユーザーが明示的に求めた場合だけ使う。

返る `state` が `COMMENTED` なら成功。`PENDING` のままなら submit が効いていない。
`submittedAt` と `commit.oid` は追跡の F1 で使うので控える。

**完了条件**: `check_mention.py` が終了コード 0 で通った本文で submit し、`state` が `COMMENTED` になり、レビューの URL が返っている。追跡が選ばれていれば、手順 9 の報告の後に
[`references/follow-up.md`](references/follow-up.md) の F1 へ進む。

## 手順 9 — 報告する

報告の前に、手順 2 で worktree を作ったなら `git worktree remove "$WT"` で片付ける。
追跡するなら worktree は残す — 返信の確認で今の head のコードを読む。片付けは追跡の F7 で行う。

- 投稿したインラインコメントの件数（ラベル別）と、レビューの URL
- 総評に回した指摘と、その理由
- 不採用の件数（理由別）
- Spec 軸・セキュリティを実施しなかったなら、その理由
- 条件付きで足した標準の出典（当たった行が無ければ「なし」、落とせなかった行は理由）
- 台帳のパス（`.scratch/pr-<number>/ledger.md`）

`.scratch/pr-<number>/` に台帳・候補・検証結果・総評が残っているので、次に開く人が辿れる（@ISSUE.md）。

## 追跡だけを頼まれたとき

submit 済みのレビューへの返信の追跡、または中断した追跡の再開を頼まれたら、手順 1 で PR の情報を取ったあと、
手順 2 は worktree の作成だけを行い、手順 3〜8 と再レビューの判定を飛ばして [`references/follow-up.md`](references/follow-up.md) の「入口」に従う。

## dry-run で止めたいとき

ユーザーが「投稿はしないで内容だけ見せて」と言ったら、**手順 6 の dry-run までで止める**。
手順 1〜5 は GitHub を読むだけで書き込まない。dry-run の出力と、台帳と、総評の下書きを会話に出し、手順 2 で worktree を作ったなら `git worktree remove "$WT"` で片付けて終わる。

## 同梱物

| ファイル | 役割 |
| --- | --- |
| `scripts/validate_positions.py` | diff と投稿候補を突き合わせ、位置の妥当性を判定する。`gh` も GitHub も知らないので単体で試せる |
| `scripts/check_mention.py` | 本文の最初のメンションが PR の作者と一致するかを判定する。作者は自分で `gh` から取る |
| `scripts/pretool_check_mention.py` | PreToolUse フック（matcher `Bash`）。submit・approve・`gh pr comment` の本文を `check_mention.py` で照合し、不一致なら実行させない。作者が自分の PR は対象外 |
| `scripts/post_pending_review.py` | pending レビューを作り、スレッドを 1 件ずつ足す。`--dry-run` あり |
| `scripts/wait_for_replies.py` | submit 後の反応（自分のスレッドへの返信・会話コメント・再依頼・他人の resolve・`--head` からの push・クローズ／マージ）が届くまで待ち、JSON に書き出す。判定はしない |
| `references/follow-up.md` | submit 後の追跡。返信を確かめて resolve か追い返信をし、approve し、マージを待って後始末するまでの手順と歯止め |
| `references/comment-format.md` | Conventional Comments に沿った本文の書式と、submit の総評・追い返信・approve の本文の型 |
| `references/re-review.md` | 再レビューのときに手順 2・3・4・8 に足す作業（修正コミットの切り出し、由来、前回の判断との整合） |
| `references/review-standard.md` | 指摘を出す基準（Google Engineering Practices に沿う）。レビュー役と手順 4 が読む |
| `references/conditional-sources.md` | 条件付きの標準の出典の落とし方と、本体が Standards 軸で読む添え書き。手順 2 で表の行に当たったときに読む |
| `pr-review-functionality`（リポジトリの `pr-review/agents/`） | 機能面のレビュー役。手順 2 で立てる |
