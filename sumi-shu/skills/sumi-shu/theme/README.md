# 第三者スキルに寄せる

sumi-shu スキル（`../SKILL.md`）の一部。寄せる先の値は、スキルのフォルダの `tokens.css`（色・余白・書体）と `SKILL.md` の決まりに従う。下の CSS のパスは、スキルのフォルダからのもの。

archify・html-plan の出力は、`theme/` の CSS で幅・色・書体を寄せ、レイアウトはスキルのままにする。html-plan は角丸の変数（`--r`・`--r-sm`）も 0 にし、カードと注記の角を落とさない。変数を使わない角丸（ピルの 99px、シートの 16px、ボタンやコードの 5〜6px など）とカードの枠線は、スキルのレイアウトの一部としてそのまま残る。CSS は中身を `<style>` で貼り、ファイルの先頭の `@import` の行はその `<style>` の先頭に置く。

| 出力 | 足す CSS | 足す場所と時機 |
| --- | --- | --- |
| `archify` の explainer | `theme/archify-explainer.css`（幅・色・書体） | 最後の `finalize` が通った後の HTML。`finalize` を回し直したら、もう一度足す |
| `archify` の図のページ | `theme/archify-diagram.css`（色・書体。色で表されていた種類の区別は線で残す: Cloud は太い枠、External は破線、Message Bus は点線。図の幅は、読む幅の下限を 1440px にして、小さくしない） | テンプレートの `<style>` より後ろ。幅は触らない（JS が図を 1 画面に収める幅を計算している） |
| `html-plan` | `theme/html-plan.css`（幅・色・書体・角丸の変数） | pack 前の `plan.html` の `<link rel="stylesheet" href="htmlplan.css">` より後ろ |

- 状態を表す色（archify の `--good` `--caution` `--bad`、html-plan の `--green` `--amber` `--red` など）は、図表の意味を壊さないよう上書きしない。`sub` の朱は「悪い」の赤（archify の `--bad`、html-plan の `--red`）と色相が近いので、寄せた出力では色だけで両者を見分けさせず、ラベルの文字で区別する
- archify の図を SVG・画像で書き出したものは対象外。書き出しの処理が独自の書体を埋め込むため、上書きが届かない
- CSS を足した explainer は、archify の provenance（成果物の SHA-256 との照合）の検査から外れる。報告には「検査後に幅と配色の CSS を足した」と書く
- スキルの更新で効かなくなったら、`archify/explainer/reader.css`、`archify/assets/template.html`、`html-plan/runtime/htmlplan.css` の変数名を読み直して `theme/` の CSS を直す
- 寄せた後の確かめ: 地・文字・強調色・書体が、sumi-shu の `tokens.css` の値と同じ（幅は、第三者スキルでは全幅と `p` の 45em のままにする。sumi-shu 本体の「1280px の外枠と 720px の文章の列」とは別）
