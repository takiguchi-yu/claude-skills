# pr-review のレビュー品質 eval

pr-review のレビュー役の構成を変えたとき（例: `/code-review` の Standards 軸を本体に統合する）に、
欠陥を拾う力が落ちていないかを比べるための eval。既存の `skills/pr-review/evals/evals.json` は
位置の検証と投稿の止め方を見るもので、こちらはレビューの中身を見る。

## 構成

| パス | 役割 |
| --- | --- |
| `arm-a/` | 旧構成 A（レビュー役 4 体）を載せたテスト用プラグイン。`arm-a/local.patch` が、今のスキルを A に戻す |
| `arm-b/` | 今の構成 B（Standards 軸を本体が見る、レビュー役 3 体）。2026-10-25 に元のスキルへ入れたので、パッチは持たない |
| `arm-*/sync.sh` | 元のスキル・エージェント（pr-review・pr-review-functionality・code-review と、Standards 軸で使う出典の oo-design・writing-for-agents）を各 arm の `skills` `agents` へコピーし、`local.patch` があれば当てる。実行前に毎回走らせる。コピーを直しても元のスキルは変わらない |
| `arm-a/evals/_shared/base-repo.sh` | 7 ケース共通の fixture（規約文書と既存コードを持つ小さな Go サービス） |
| `arm-a/evals/<case>/` | `scaffold.sh` が PR ブランチを積み、`prompt.md` が PR 情報を渡し、`graders/` が採点する |

| ケース | 拾うべき欠陥 | 拾ったら誤検知 |
| --- | --- | --- |
| `c1-coupon` | 上限 1000 円の未実装（仕様）、`%w` でラップしていない（規約 1）、テスト欠落、**割引率 10 の直書き（規約 6）** | `amt` の命名などの Nit |
| `c2-shop-search` | `fmt.Sprintf` による SQL インジェクション、`rows.Err()` の未確認、**`doc.go` の関数一覧に未追記（規約 8）** | 既存と同型の `[]Shop{}`・`defer rows.Close()` |
| `c3-user-page` | 1 始まりの page で offset が 1 ページずれる、ログにメールアドレス（規約 2）、**`log` パッケージの使用（規約 7）** | PR 以前からある `List` の上限なし |
| `c4-coupon-expiry` | 期限当日の 0 時で期限切れになる、**`time.Now()` の直接呼び出し（規約 9）** | — |
| `c5-shop-handler` | `strconv.Atoi` のエラーを捨てて 400 を返さない、**ハンドラ層が SQL を直接実行（規約 10）** | — |
| `c6-review-average` | 整数の割り算・0 件でのゼロ除算、**JSON タグが camelCase（規約 11）** | — |
| `c7-user-count` | `err` を見る前の `defer rows.Close()`、**`ctx` が第 2 引数（規約 12）** | — |

太字の欠陥は、機能にも issue の完了条件にも現れず、`docs/CODING_RULES.md` を読まないと違反と分からないように仕込んだもの。ただし、検証用の版で実際に落ちたのは次の 3 件だけで、これを**識別項目**と呼ぶ。

検証用の版は、Standards 役を立てないだけでなく、**本体でも規約との照合をしない**ようにスキルに書き足したもの。落ちた回でも、c7 では本体が規約 12 の違反に気づいたうえで載せていなかった。つまり識別項目が見分けているのは、「規約違反を誰かが照合して指摘として出すか」であって、サブエージェントの数そのものではない。

| 識別項目 | ケース | 検証用の版の結果 | 実行回数 | 判定役 |
| --- | --- | --- | --- | --- |
| `rate-literal` | c1 | 落とした | 1 | haiku（c1 の採点の文面を直す前） |
| `doc-index` | c2 | 落とした | 1 | haiku |
| `ctx-rule` | c7 | 落とした | 1 | sonnet |

`slog`（c3）・`clock-rule`（c4）・`json-tag-rule`（c6）は、Standards 役が無くても他の役が拾ったので、識別項目にしない。

c5 の `layer-rule` は、直す前の fixture では検証用の版で落ちた（そのときも機能面の役は規約 10 の違反を報告しており、本体が台帳から外していた。既存の `area.go` が同じ書き方をしていたためと見られる）。fixture を直した後は、検証用の版でも拾った（1 回）。直した fixture の `internal/shop/db.go` のコメント「ハンドラ層はこの型だけを知る」が規約 10 のヒントになり、レビューでも根拠として引かれていた。そのため識別項目から外した。識別項目に戻すなら、このコメントを消して A・B・検証用の版を流し直す。

c4〜c7 は共通の土台を変えずに、各 scaffold が main に規約 9〜12 と既存コードを足してから PR ブランチを積む（c1〜c3 の結果をそのまま使えるようにするため）。

全ケースに `reviewers-spawned`（Agent の呼び出し回数。A は 4 回以上、B は 3 回以上）を入れている。満たさなければ、比べたい構成が動いていない。

タグは c1〜c3 が `quality`、c4〜c7 が `standards-only`。`--tag` で組ごとに流す。1 回約 1.3 USD なので、`quality` の 9 回も `standards-only` の 12 回も上限 25 USD に収まる。両方を一度に流すなら上限を 40 USD にする。

## 実行

測る構成の arm に `cd` する。今の構成（B）は `arm-b`、旧構成（A）は `arm-a`。`--tag` は `quality`（c1〜c3）か `standards-only`（c4〜c7）。

```bash
cd pr-review/evals-quality/arm-b   # 旧構成 A を測るなら arm-a
./sync.sh
claude plugin eval . --tag quality --runs 3 -j 3 --ablation none --scaffold \
  --allow-tools Bash Write Edit --trust-plugin --no-publish --max-cost-usd 25 --threshold 0 --judge-model sonnet \
  --json <出力先>.json
```

- `--ablation none`: 既定の「プラグインなし」の比較を付けない（実行回数が倍になるため）
- `--no-publish`: 既定ではレポートを claude.ai に公開するので止める

別の構成を今のスキル（B）と比べるときは、次の手順で arm を足す。A を作ったときと同じ手順。

1. `arm-b` を `evals/results/` を除いて `arm-<名前>` に複製する
2. `.claude-plugin/plugin.json` の `name` を `pr-review-eval-arm-<名前>` に変える（結果で区別するため）
3. 今のスキルとの違いを `local.patch`（arm から見た相対パスの `patch -p0` 形式。例: `skills/pr-review/SKILL.md` への差分）に置く。`sync.sh` はコピーし直した後でこれを当てるので、上の実行コマンドを `./sync.sh` からそのまま流してよい
4. 構成に合わせて、各ケースの `graders/reviewers-spawned.md` の `min` と、`prompt.md` のレビュー役の一文を直す。結果で Agent の回数を見て、変更が効いていたことを確かめる
5. 比べる arm どうしは、同じ graders・同じ `--judge-model` で流し直す
6. 結果 JSON の `cases[].arms.with[].graders` から、採点項目ごとに PASS の回数（例: A 3/3、B 1/3）を数えて比べる。回ごとの突き合わせはしない（各回は独立で、対応が無い）。識別項目の PASS 回数が下がったら、Standards 軸の退行とみなす

## 基準値（2026-10-25、Claude Code 2.1.310、判定役 haiku、c1 の採点 2 件を直す前）

| 構成 | 実行 | 平均点 | 規約にしか現れない 3 件（rate-literal / doc-index / slog） | 費用 | 1 回の所要 |
| --- | --- | --- | --- | --- | --- |
| A（旧構成、4 体） | 3 ケース × 3 回 | 0.96 | 8/9 PASS | 11.37 USD | 約 140〜180 秒 |
| 検証用: Standards 役を外した版 | 3 ケース × 1 回 | 0.88 | 1/3 PASS（rate-literal と doc-index を落とす） | 2.98 USD | 約 140〜160 秒 |

- A で FAIL になった 2 件（c1 の rate-literal と no-nit）は、最後のメッセージを読むと、指摘が実際には正しく出ていた。判定役（既定の haiku）の取り違えなので、2 件の採点の文面を直した。比べるときは `--judge-model sonnet` を付けることを勧める
- Standards 役を外した版で落ちた 2 件は、最後のメッセージにも本当に指摘が無かった。つまりこの eval は、Standards 軸が抜けたことを検出できる

## A と B の比較（2026-10-25、判定役 sonnet、各 3 ケース × 3 回）

B は、比べた時点では `arm-b/local.patch` で当てていた版（今は元のスキルに入っている）。`/code-review` からは Spec のサブエージェントだけを立て、Standards 軸は本体が規約を 1 条ずつ照合して見る。
A と B の違いは、パッチ、プロンプトのレビュー役の一文（B は「Standards 軸は本体が見る」）、`reviewers-spawned` の `min`（A 4・B 3）の 3 点で、それ以外の graders は同じ。

| 項目 | A | B |
| --- | --- | --- |
| 平均点 | 0.93 | 1.00 |
| 費用（9 回） | 12.99 USD（1 回 1.44） | 11.15 USD（1 回 1.24） |
| 1 回の平均所要 | 155 秒 | 138 秒 |
| `rate-literal`・`doc-index`（Standards 軸の識別項目） | 3/3・3/3 | 3/3・3/3 |
| c3 の `off-by-one`・`pii-log`・`slog` | 各 2/3 | 各 3/3 |
| Agent の起動回数 | 8 回は 4、1 回は 6 | 9 回とも 3 |

- A の c3 の FAIL は 1 回の実行にまとめて出たもので、最後のメッセージが「待機用のコマンドが終わった」という 1 文だけだった。採点の対象が最後のメッセージだけであることによる取りこぼしと見ている。その回のトレースは消えていて、前のメッセージのレビュー内容は確かめていない（推測）
- B の起動回数は 3 だが、どの役が立ったかは、最後のメッセージに書かれた回でしか確かめていない（トレースは実行後に消える）
- 初版の B（プロンプトが「Standards 役を立てる」のまま、スキルの既存の 4 体の記述も残したもの）は `rate-literal` を 3 回中 1 回落とした。矛盾を消した今の版で流し直した結果が上の表
- 上の実行の後で、`local.patch` に別の節の 5 か所（条件付きの出典の渡し先、`model: opus` の対象、手順 2・3 の完了条件の「4 体」）を足した。B を元のスキルへ移すときに矛盾が残らないようにするためで、比較の結果は変わらないと見て流し直していない（推測）
- 元のスキルへ入れるときに、次の 6 か所の文面も B に合わせた。どれも eval では流していない（推測で、結果は変わらないと見ている）: SKILL.md 冒頭の役割の説明、Spec への brief の ID 接頭辞、`references/re-review.md`（3 体）、`references/review-standard.md`（誰が基準を読むか）、`references/conditional-sources.md`（添え書きを本体が読む）、`agents/pr-review-functionality.md`（規約違反は本体が見る）
- さらに writing-for-agents で点検し、本体の Standards の手順を独立した節（SKILL.md「Standards 軸を本体で見る」）に移した。中身の変更は、見るタイミング（3 体の報告が返った後）、完了条件（全規約・全 smell を照合し終えたか）、控える項目（要点・区分・根拠・直し方の案）、規約ごとの照合一覧 `standards-check.md` の 4 点。これも eval では流していない

### c4〜c7 を足した結果（各 4 ケース × 3 回、判定役 sonnet）

| 項目 | A | B |
| --- | --- | --- |
| 平均点 | 1.00 | 1.00 |
| 費用（12 回） | 15.89 USD（1 回 1.32） | 14.02 USD（1 回 1.17） |
| 1 回の平均所要 | 146 秒 | 129 秒 |
| Agent の起動回数 | 12 回とも 4 | 12 回とも 3 |

### まとめ（7 ケース × 3 回）

| 項目 | A | B |
| --- | --- | --- |
| 識別項目 3 件（`rate-literal`・`doc-index`・`ctx-rule`）の PASS 回数 | 9/9 | 9/9 |
| 識別項目以外で落とした回数 | 3（c3 の 1 回にまとまったもの） | 0 |
| 1 回の平均費用 | 1.37 USD | 1.20 USD |
| 1 回の平均所要 | 150 秒 | 133 秒 |

7 ケースでは、B は Standards 軸の欠陥を A と同じだけ拾い、費用と時間は 1 割強少ない。

### c5 の fixture を直した後の再計測（2026-10-25、各 3 回、判定役 sonnet）

初版の c5 は、main の既存コード `internal/handler/area.go` が `database/sql` を import していて、規約 10 に自分で反していた。`DB` 型を `internal/shop/db.go` に移して直し、c5 だけを流し直した。上の表の c5 は直す前の値。

| 項目 | A | B（今のスキル。eval の後に足した照合一覧などを含む） |
| --- | --- | --- |
| `layer-rule`（識別項目から外した）・`atoi-error` | 3/3・3/3 | 3/3・3/3 |
| 費用（3 回） | 4.03 USD | 3.62 USD |
| 1 回の平均所要 | 141 秒 | 138 秒 |
| Agent の起動回数 | 3 回とも 4 | 2 回は 3、1 回は 4 |

- B の 3 回中 2 回は、最後のメッセージに `standards-check.md` で規約を 1 条ずつ判定したと書いている。eval の後に足した照合一覧の手順が動くことは、ここで確かめた
- B の 1 回で Agent が 4 回呼ばれた理由は、最後のメッセージに無く、トレースも消えていて確かめられなかった。A でも 6 回の回がある（上の「A と B の比較」の表の「1 回は 6」）ので、レビュー役の中のサブタスクも数えられている可能性がある（推測）
- c5 の規約文書は 1〜8 条と 10 条で、9 条が欠番になっている（c4 だけが 9 条を足すため）。B の 1 回はこれを報告に書いたが、採点には影響していない

## 制約（実測で分かったこと）

- eval の実行はサンドボックスの中で動き、`git` が動かない（`/Library/Developer/CommandLineTools` の読み取りが拒否される）。そこで scaffold の段階で `.pr/pr.diff` などを作り、プロンプトで `gh`・`git` の代わりに使わせている
- 組み込みの `/security-review` は中で `git diff` を実行するため、セキュリティ役は動かない。A・B のどちらでも同じ条件なので、Standards 軸の比較には影響しない
- シンボリックリンク先の付属物はサンドボックスから読めないため、`sync.sh` でコピーしている
- スキルとエージェント定義は `~/.claude/skills/...` を決め打ちで読むが、実行時の HOME は一時ディレクトリで、そこには無い。プロンプトで、プラグイン配下へ読み替えるよう指示している。読み替えは本体とレビュー役の判断に任されるので、回によって失敗することがある（A・B で同じ条件）
