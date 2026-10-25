# 条件付きの標準の出典 — 落とし方と添え書き

`pr-review` の手順 2 で、PR が「条件付きの標準の出典」の表のどれかの行に当たったときに読む。

添え書きは、出典ごとの当て方の注意で、本体が Standards 軸を見るときに、その出典と一緒に読む。

外部の規則は**コミットを固定して** `$PRDIR` に落とす。元のスキル（`web-design-guidelines` など）は毎回最新を取り直すので、
そのまま使うと回ごとに基準が変わる。版を上げるときは URL の SHA を書き換える。
`curl` が失敗したら、その行の出典は読まず、手順 9 で「未実施」と失敗の理由を報告する。

## エージェントが読む文書 — writing-for-agents

出典は `~/.claude/skills/writing-for-agents/SKILL.md`。添え書きは無い。
リポジトリに書き方の規約が無くても、重複・禁止形・古びる値の写しといった書き方の基準が当たるため足す。

## 設計に手を入れている — oo-design

出典は `~/.claude/skills/oo-design/SKILL.md`。`oo-design` は書く側の指針で、そのまま当てると「パターンにできる」という Nit が出るので、
次を添える。

```markdown
review-standard.md の B「この PR で入れた設計が層・責務を崩す」を判定する物差しとして使う。
oo-design の「採らない判断の基準」に当たるもの（YAGNI・浅くなる・既存の設計と食い違う）は返さない。
```

## 画面のファイル — Web Interface Guidelines

Vercel の [Web Interface Guidelines](https://github.com/vercel-labs/web-interface-guidelines)（MIT）。UI コードのレビュー用に書かれた規則で、コードから判定できる。

```bash
curl -sf -o "$PRDIR/web-interface-guidelines.md" \
  https://raw.githubusercontent.com/vercel-labs/web-interface-guidelines/4ecfb9fb8d1d3b7009674869b3aaee2f904042e1/command.md
```

```markdown
web-interface-guidelines.md は、review-standard.md の区分を判定する物差しとして使う。冒頭の対象ファイルの指示
（$ARGUMENTS）と末尾の Output Format は使わず、対象は pr.diff、出力は本体の Standards の指摘（ID は std-）にする。
- 操作できなくなる・データを失う → A。Accessibility・Focus States・Anti-patterns で操作を塞ぐもの
  （ラベルの無い入力、click だけの div、outline を消したままのフォーカス、拡大の禁止など）、Hydration Safety、確認も取り消しも無い破壊的操作
- 使いにくくなる・本番の条件で困る → B。上以外の Accessibility・Focus States・Forms・Animation の prefers-reduced-motion、
  Content Handling（空・長い内容で崩れる）、何が起きてどう直すかを言わないエラー文言、
  Performance・Images のうち変更したコードが本番のデータ量で遅くなる・ずれる場面を示せるもの
- リポジトリのデザインシステム・規約はこのガイドラインより優先する
- 見た目への影響がコードから決まらないものは C にして、スクリーンショットかデモを求める。UI の変更は
  コードを読むだけでは利用者への影響が分かりにくい（https://google.github.io/eng-practices/review/reviewer/looking-for.html の Functionality）
Typography・Content & Copy の表記（`…`、引用符、Title Case など）、Hover・Touch・Dark Mode・Safe Areas の仕上げ、
URL への状態の同期の勧めは好み（Nit）として返さない。
```

## React / Next.js — React Best Practices

Vercel の [React Best Practices](https://github.com/vercel-labs/agent-skills/tree/main/skills/react-best-practices)（MIT）のうち、
影響度 CRITICAL・HIGH の 3 章（Eliminating Waterfalls・Bundle Size Optimization・Server-Side Performance）だけを使う。
4 章以降（再レンダリング・JavaScript の細かい最適化など）は好みの Nit が大半なので、落とす時点で切り捨てる。

```bash
curl -sf -o "$PRDIR/react-best-practices-all.md" \
  https://raw.githubusercontent.com/vercel-labs/agent-skills/dc8367e6f91c022d83361f03c3313fa05e848ee5/skills/react-best-practices/AGENTS.md \
  && awk '/^## 1\./{p=1} /^## 4\./{p=0} p' "$PRDIR/react-best-practices-all.md" > "$PRDIR/react-best-practices.md"
```

```markdown
react-best-practices.md は、review-standard.md の区分を判定する物差しとして使う。
- 3.1 Authenticate Server Actions Like API Routes に当たるもの → A
- それ以外の規則 → 変更したコードで、本番のデータ量・通信で遅くなる・バンドルが膨らむ場面を path:line で示せるときだけ B
```
