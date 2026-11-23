# claude-skills

自作の Claude Code スキルと、それが使うサブエージェント・スクリプトを、プラグインとしてまとめたもの。配布はしない。自分の PC に入れて使う。

## 構成

ルートの `.claude-plugin/marketplace.json` が、このリポジトリをマーケットプレイス `claude-skills` にする。
1 ディレクトリが 1 プラグインで、1 つのスキルと、そのスキルが前提にするエージェントを入れる。

| プラグイン | スキル | エージェント（`subagent_type` に渡す名前） |
| --- | --- | --- |
| `complete-task` | complete-task | `complete-task:ct-researcher` / `:ct-review-accuracy` / `:ct-review-ux` / `:ct-review-risk` / `:ct-verifier` |
| `pr-comments` | pr-comments | `pr-comments:pr-comment-verifier` |
| `pr-review` | pr-review | `pr-review:pr-review-functionality` |
| `consistency-check` | consistency-check | — |
| `oo-design` | oo-design | — |
| `spec-notation` | spec-notation | — |
| `rdra` | rdra（RDRA で要件定義を組み立てる手順。振る舞いの書式は spec-notation に渡す） | — |
| `diagram` | diagram | — |
| `sumi-shu` | sumi-shu（デザインシステム。HTML・Artifact の見た目と図の決まり、ページに貼る CSS） | — |
| `deliverable-review` | —（dotfiles の `REVIEW.md` から呼ぶ） | `deliverable-review:deliverable-reviewer` |

スキルは `/<プラグイン>:<スキル>` で呼ぶ。名前が衝突しなければ素の `/<スキル>` でも呼べる。
スキルが同梱物を指すときは、SKILL.md では `${CLAUDE_SKILL_DIR}`（そのスキルのディレクトリ）と `${CLAUDE_PLUGIN_ROOT}`（プラグインのルート）を使う。
この 2 つが展開されるのは SKILL.md の本文だけなので、`references/` やエージェント定義には SKILL.md から展開済みのパスを渡す。

## 入れる

```sh
git clone https://github.com/takiguchi-yu/claude-skills.git ~/git/private/claude-skills
~/git/private/claude-skills/install.sh
```

`install.sh` は、このリポジトリを `directory` 型のマーケットプレイスとして登録し、全プラグインを user スコープで入れる（`CLAUDE_CONFIG_DIR` があればそのプロファイルに）。
何度実行しても同じ状態になる。以前の方式で `~/.claude/{skills,agents}` に張った、このリポジトリへのリンクは外す。
`directory` 型のマーケットプレイスのプラグインは元のディレクトリから読まれるので、ここでの編集は次のセッション起動か `/reload-plugins` で反映される。

[dotfiles](https://github.com/takiguchi-yu/dotfiles-public) の `setup.sh` は、このリポジトリを clone し、マーケットプレイスの登録をローカル設定に書いてから `install.sh` を呼ぶ。

## 足す・消す

- スキルを足す: `<プラグイン>/skills/<名前>/SKILL.md` を作る（エージェントは `<プラグイン>/agents/` に置く）。`/reload-plugins` で反映される
- プラグインを足す: ディレクトリに `.claude-plugin/plugin.json` を作り、`.claude-plugin/marketplace.json` の `plugins` に足して `./install.sh`
- プラグインを消す: `claude plugin uninstall <名前>@claude-skills` を実行してから（個人プロファイルにも入れたなら `CLAUDE_CONFIG_DIR=~/.claude-personal` を付けてもう一度）、ディレクトリと `marketplace.json` の行を消す。dotfiles を使っているなら `setup.sh` を再実行し、ローカル設定の `enabledPlugins` から外す

公開リポジトリなので、commit の前に lefthook で gitleaks を実行する（`lefthook install` で有効にする。独自の語は dotfiles のローカル設定 `~/.config/dotfiles/local/gitleaks.toml` を使う）。
