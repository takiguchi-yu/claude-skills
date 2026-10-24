---
max_turns: 200
timeout_seconds: 1800
allowed_tools: [Read, Glob, Grep, Skill, Agent, TodoWrite, Bash, Write, Edit]
---

カレントディレクトリの git リポジトリで、`feat/shop-search` ブランチを `main` に入れる PR をレビューしてほしい。pr-review スキルを使うこと。

この PR は GitHub には無く、この環境では `git` と `gh` が動かない（オフラインの検証環境）。手順 1・2 の `gh` と `git` の操作は、次で置き換えること。

- PR 番号は #1、作者は `@author-a`、base は `main`、head は `feat/shop-search`
- head はチェックアウト済み。worktree は作らず、カレントディレクトリをそのまま `$WT` として使う
- PR の diff（`gh pr diff` 相当）は `.pr/pr.diff`、変更ファイルの一覧は `.pr/files.txt`、コミットは `.pr/commits.txt` にある
- 既存のレビュー・スレッドは無い。再レビューではない
- レビュー役（`/code-review` の Standards・Spec、`pr-review-functionality`、セキュリティ）は手順どおりに立てること。レビュー役にも、`git diff` の代わりに `.pr/pr.diff` を読むよう伝えること

- スキルやエージェント定義に出てくる `~/.claude/skills/<名前>/…` と `~/.claude/agents/<名前>.md` は、この環境には無い。読み込まれたプラグインの `skills/<名前>/…` と `agents/<名前>.md` を読むこと（場所は Skill ツールが示すベースディレクトリから辿れる）。レビュー役にも、この読み替えを伝えること

PR 本文（intent.md に使う）:

> # 店名の部分一致検索を追加する
> 
> Closes #20
> 
> issue #20 の完了条件:
> - 検索語を含む店名の店舗を返す
> - 該当が無ければ空の配列を返す（nil ではなく `[]Shop{}`）

投稿はしないで、dry-run までで止めること（ユーザーに確認を求めず、そこで終える）。最後のメッセージに、採用した指摘の一覧（ファイル・行・ラベル・本文）と総評の下書きを全部書くこと。
