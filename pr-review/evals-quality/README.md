# pr-review のレビュー品質 eval

pr-review のレビュー役の構成を変えたとき（例: `/code-review` の Standards 軸を本体に統合する）に、
欠陥を拾う力が落ちていないかを比べるための eval。既存の `skills/pr-review/evals/evals.json` は
位置の検証と投稿の止め方を見るもので、こちらはレビューの中身を見る。

## 構成

| パス | 役割 |
| --- | --- |
| `arm-a/` | 今の構成（レビュー役 4 体）を載せたテスト用プラグイン |
| `arm-a/sync.sh` | 元のスキル・エージェント（pr-review・pr-review-functionality・code-review と、Standards に渡す出典の oo-design・writing-for-agents）を `arm-a/skills` `arm-a/agents` へコピーする。実行前に毎回走らせる。コピーを直しても元のスキルは変わらない |
| `arm-a/evals/_shared/base-repo.sh` | 3 ケース共通の fixture（規約文書と既存コードを持つ小さな Go サービス） |
| `arm-a/evals/<case>/` | `scaffold.sh` が PR ブランチを積み、`prompt.md` が PR 情報を渡し、`graders/` が採点する |

| ケース | 拾うべき欠陥 | 拾ったら誤検知 |
| --- | --- | --- |
| `c1-coupon` | 上限 1000 円の未実装（仕様）、`%w` でラップしていない（規約 1）、テスト欠落、**割引率 10 の直書き（規約 6）** | `amt` の命名などの Nit |
| `c2-shop-search` | `fmt.Sprintf` による SQL インジェクション、`rows.Err()` の未確認、**`doc.go` の関数一覧に未追記（規約 8）** | 既存と同型の `[]Shop{}`・`defer rows.Close()` |
| `c3-user-page` | 1 始まりの page で offset が 1 ページずれる、ログにメールアドレス（規約 2）、**`log` パッケージの使用（規約 7）** | PR 以前からある `List` の上限なし |

太字の欠陥は、機能にも issue の完了条件にも現れず、`docs/CODING_RULES.md` を読まないと違反と分からない。ただし Standards 軸の有無を見分けられるのは c1 の `rate-literal` と c2 の `doc-index` の 2 件だけ。c3 の `slog` はメールアドレスの指摘と同じ行に出るため、Standards 役が無くても他の役が拾う（実測）。

全ケースに `reviewers-spawned`（Agent が 4 回以上呼ばれたか）を入れている。満たさなければ、比べたい構成が動いていない。

## 実行

```bash
cd pr-review/evals-quality/arm-a
./sync.sh
claude plugin eval . --tag quality --runs 3 -j 3 --ablation none --scaffold \
  --allow-tools Bash Write Edit --trust-plugin --no-publish --max-cost-usd 25 --threshold 0 --judge-model sonnet \
  --json <出力先>.json
```

- `--ablation none`: 既定の「プラグインなし」の比較を付けない（実行回数が倍になるため）
- `--no-publish`: 既定ではレポートを claude.ai に公開するので止める

構成 B（Standards 軸を本体に統合した版）を比べるとき:

1. `arm-a` を `evals/results/` を除いて `arm-b` に複製する
2. `arm-b/.claude-plugin/plugin.json` の `name` を `pr-review-eval-arm-b` に変える（結果で区別するため）
3. B の変更を `arm-b/local.patch`（`arm-b` から見た相対パスの `patch -p0` 形式。例: `skills/pr-review/SKILL.md` への差分）に置く。`sync.sh` はコピーし直した後でこれを当てるので、上の実行コマンドを `./sync.sh` からそのまま流してよい
4. 各ケースの `graders/reviewers-spawned.md` の `min` を 3 にする。B の結果でこれが PASS かつ Agent が 4 回でないことを見て、B の変更が効いていたことを確かめる
5. **A も同じ graders・同じ `--judge-model` で流し直す。** 下の基準値は判定役が haiku で、c1 の `no-nit`・`rate-literal` を直す前の文面で取ったものなので、そのまま B と比べない
6. 結果 JSON の `cases[].arms.with[].graders` から、採点項目ごとに PASS の回数（例: A 3/3、B 1/3）を数えて比べる。回ごとの突き合わせはしない（各回は独立で、対応が無い）。`rate-literal` か `doc-index` の PASS 回数が下がったら、Standards 軸の退行とみなす

## 基準値（2026-10-25、Claude Code 2.1.310、判定役 haiku、c1 の採点 2 件を直す前）

| 構成 | 実行 | 平均点 | 規約にしか現れない 3 件（rate-literal / doc-index / slog） | 費用 | 1 回の所要 |
| --- | --- | --- | --- | --- | --- |
| A（今の 4 体） | 3 ケース × 3 回 | 0.96 | 8/9 PASS | 11.37 USD | 約 140〜180 秒 |
| 検証用: Standards 役を外した版 | 3 ケース × 1 回 | 0.88 | 1/3 PASS（rate-literal と doc-index を落とす） | 2.98 USD | 約 140〜160 秒 |

- A で FAIL になった 2 件（c1 の rate-literal と no-nit）は、最後のメッセージを読むと、指摘が実際には正しく出ていた。判定役（既定の haiku）の取り違えなので、2 件の採点の文面を直した。比べるときは `--judge-model sonnet` を付けることを勧める
- Standards 役を外した版で落ちた 2 件は、最後のメッセージにも本当に指摘が無かった。つまりこの eval は、Standards 軸が抜けたことを検出できる

## 制約（実測で分かったこと）

- eval の実行はサンドボックスの中で動き、`git` が動かない（`/Library/Developer/CommandLineTools` の読み取りが拒否される）。そこで scaffold の段階で `.pr/pr.diff` などを作り、プロンプトで `gh`・`git` の代わりに使わせている
- 組み込みの `/security-review` は中で `git diff` を実行するため、セキュリティ役は動かない。A・B のどちらでも同じ条件なので、Standards 軸の比較には影響しない
- シンボリックリンク先の付属物はサンドボックスから読めないため、`sync.sh` でコピーしている
- スキルとエージェント定義は `~/.claude/skills/...` を決め打ちで読むが、実行時の HOME は一時ディレクトリで、そこには無い。プロンプトで、プラグイン配下へ読み替えるよう指示している。読み替えは本体とレビュー役の判断に任されるので、回によって失敗することがある（A・B で同じ条件）
