# 検証プレイブック: インフラ運用

成果物が AWS リソースまたは IaC 定義のとき、**参照系だけで**完了条件を検証する手順。

## 1. 実行してよい操作の境界

`~/.claude/AWS.md` の規定がそのまま効く。**この列挙は例示であり、列挙外なら安全という意味ではない。**

| 実行してよい | 承認を得るまで実行しない |
|---|---|
| `aws ... describe-*` / `list-*` / `get-*` | `create-*` `update-*` `put-*` `modify-*` `attach-*` `detach-*` `delete-*` `terminate-*` `remove-*` `stop-*` `reboot-*` `disable-*` |
| `terraform plan` `validate` `fmt` `show` | `terraform apply` `destroy` `import` `state rm` `taint` |
| `cdk synth` `diff` `ls` | `cdk deploy` `destroy` |
| `aws s3 ls` / `s3api head-object` | `s3 rm` `s3 rb` `s3 mv` `s3 sync` `s3 cp`（書き込み方向） |

参照系だと確信できないコマンドは**実行せず**、AskUserQuestion で確認する。

環境変数 `AWS_CA_BUNDLE` と `AWS_PAGER=""` は `~/.claude/settings.json` で設定済み — コマンドごとに付けない。SSL エラーやページャー待ちが起きたときだけ環境変数を疑う。

## 2. 完了条件のテンプレート

適用（apply / deploy）が承認されていない前提で立てる。

- [ ] `terraform validate` が通る
- [ ] `terraform fmt -check` で差分が出ない
- [ ] `terraform plan` の差分が**意図した変更だけ**（想定外の replace / destroy が 0 件）
- [ ] 参照系コマンドで現状を確認済み（変更前の状態が記録されている）
- [ ] 適用手順とロールバック手順が文書化されている
- [ ] 適用そのものはユーザーの承認待ちとして残課題に記載

## 3. plan の読み方

`terraform plan` の出力は、次の 3 点を必ず突合する。

1. **`Plan: N to add, M to change, K to destroy` の数字**が想定と一致するか
2. **`# ... must be replaced`** が出ていないか。出ていたら理由（forces replacement の行）を特定する。**リソースの再作成はダウンタイムとデータ喪失を伴う**
3. 変更対象に**本番リソースが混じっていないか**（名前・タグ・workspace・var ファイルを確認）

`-target` で範囲を絞った plan は、絞った事実を報告に明記する — 絞った外側の差分は検証していない。

## 4. 現状確認の記録

変更前の状態を参照系で取り、詳細ログに残す。あとで「変更前はどうだったか」を辿れないと、ロールバックの判断ができない。

```bash
aws sts get-caller-identity          # どのアカウント・ロールで見ているか
terraform workspace show             # どの環境か
terraform show -json | head -0       # state の存在確認（出力は詳細ログへ）
```

## 5. レビュー 3 視点の観点（インフラ向け）

- **A 正確性** — plan の差分と意図の一致、参照した環境が正しいか（アカウント ID / リージョン / workspace）、パラメータの値、依存リソースの整合
- **B 利用者目線** — 運用担当が手順書だけで実行できるか、失敗時の戻し方が書かれているか、監視・アラートが変更に追随しているか、権限が過剰でないか
- **C リスク・抜け漏れ** — replace / destroy によるダウンタイムとデータ喪失、本番への波及、IAM 権限の拡大、コスト増、ネットワーク到達性の変化、シークレットの平文露出、適用順序の依存

## 6. やってはいけない

- 「plan が通ったから大丈夫」で apply を実行する（apply は承認が必要）
- 参照系か判断がつかないコマンドを試しに叩く
- `describe` 系の出力に含まれるシークレットや個人情報を報告本文に貼る
- 本番と検証環境の取り違えを確認せずに進める
