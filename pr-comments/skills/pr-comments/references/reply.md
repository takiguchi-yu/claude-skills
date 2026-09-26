# 返信と起票

`pr-comments` の手順 9 から読む。返信・起票はいずれも**外部への発信**なので、実行前に AskUserQuestion で承認を取る。返信文をまとめて提示し、1 回の承認で全件を送る形にする。

## 返信の共通形式

**1 行目に disclaimer を置く。** レビュアーが文面の成り立ちを誤解しないようにする。

```
🤖 Claude Code が判定・作成した返信です（内容は投稿者が確認済み）。
```

2 行目以降に分類ごとの本文を書く。**根拠には `path:line` かコミット SHA か issue 番号を必ず入れる。**

## 分類ごとの本文

**今対応** — 何をどう直したかと、コミット SHA。

```
指摘のとおりでした。<何をどう直したか> を <SHA> で修正しました。
```

**別チケット** — 妥当と認めたうえで、この PR で直さない理由と issue リンク。

```
妥当な指摘ですが、<スコープ外である理由> のためこの PR の範囲外と判断しました。
#<issue番号> に起票しました。
```

**対応不要** — 却下理由と出典。**「不要です」だけで終わらせず、レビュアーが検証できる出典を示す。**

```
<却下理由>。根拠: <path:line または仕様 URL>
```

**判断保留** — 何が決まれば判定できるかを書いて質問にする。

```
判定に <不足している情報> が必要でした。<質問> をご確認いただけますか。
```

## 送信コマンド

レビュースレッドへの返信（手順 3 で取得した `id` を使う）:

```bash
gh api graphql -f query='
mutation($threadId:ID!,$body:String!){
  addPullRequestReviewThreadReply(input:{pullRequestReviewThreadId:$threadId, body:$body}){
    comment{ url }
  }}' -F threadId=THREAD_ID -F body="$(cat /path/to/reply.md)"
```

レビュー総評への返信はスレッドが無いため、PR の会話コメントとして送り、宛先のレビュアーを冒頭で名指しする:

```bash
gh pr comment <number> --body-file /path/to/reply.md
```

**スレッドの resolve はレビュアーが押す。** 返信までで手を止める。

## 起票

トラッカーの選択:

- **GitHub で管理されているリポジトリ** — `gh issue create` で同リポジトリに起票する。
- **GitHub 以外で管理されている、または issue が無効** — `.scratch/<feature>/` に markdown を置く（@ISSUE.md）。1 チケット 1 ファイル、冒頭の説明の下に `**Status:**` と `**Blocked by:**` を書く。

`gh issue list --limit 1` が `Issues are disabled` などで失敗したら後者に倒す。

issue 本文に入れるもの（@ISSUE.md）:

- **満たせたか判定できる完了条件** — チェックボックスの一覧
- **見つけたときの状況** — 元の PR とスレッドの URL、指摘の要約、なぜこの PR で直さないか
- **着手できる条件** — 何が終われば始められるか
