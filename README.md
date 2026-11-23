# claude-skills

自作の Claude Code スキルと、それが使うサブエージェント・スクリプト・フックを、1 つのプラグイン `my` にまとめたもの。配布はしない。自分の PC に入れて使う。

## 構成

ルートの `.claude-plugin/marketplace.json` が、このリポジトリをマーケットプレイス `claude-skills` にする。プラグインは `my` の 1 つだけで、リポジトリのルートがそのプラグインになる。
1 ディレクトリに、1 つのスキルと、そのスキルが前提にするエージェントを置く。`.claude-plugin/plugin.json` が、各ディレクトリの `skills/`・エージェントのファイル・フックを列挙する。

| ディレクトリ | スキル（`/my:<名前>` で呼ぶ） | エージェント（`subagent_type` に渡す名前） |
| --- | --- | --- |
| `complete-task/` | complete-task | `my:ct-researcher` / `my:ct-review-accuracy` / `my:ct-review-ux` / `my:ct-review-risk` / `my:ct-verifier` |
| `pr-comments/` | pr-comments | `my:pr-comment-verifier` |
| `pr-review/` | pr-review（投稿の宛先を照合する PreToolUse フック `hooks/hooks.json` も持つ） | `my:pr-review-functionality` |
| `consistency-check/` | consistency-check | — |
| `oo-design/` | oo-design | — |
| `spec-notation/` | spec-notation | — |
| `rdra/` | rdra（RDRA で要件定義を組み立てる手順。振る舞いの書式は spec-notation に渡す） | — |
| `diagram/` | diagram | — |
| `sumi-shu/` | sumi-shu（デザインシステム。HTML・Artifact の見た目と図の決まり、ページに貼る CSS） | — |
| `deliverable-review/` | —（dotfiles の `REVIEW.md` から呼ぶ） | `my:deliverable-reviewer` |

スキルが同梱物を指すときは、SKILL.md では `${CLAUDE_SKILL_DIR}`（そのスキルのディレクトリ）を使う。`${CLAUDE_PLUGIN_ROOT}` はリポジトリのルートになる。
この 2 つが展開されるのは SKILL.md の本文だけなので、`references/` やエージェント定義には SKILL.md から展開済みのパスを渡す。

### pr-review のフック

プラグイン `my` を有効にすると、pr-review スキルを使っていないセッションでも、Bash の実行前に `pretool_check_mention.py` が走る。

| 項目 | 内容 |
| --- | --- |
| 対象 | `gh pr comment` / `gh pr review` で本文をファイル（`--body-file`・`-F`）で渡すもの、`gh api graphql` の `submitPullRequestReview` / `addPullRequestReview` |
| 止める条件 | 本文の最初のメンションが PR の作者でない（メンションが無いときを含む）、または PR・本文・作者を判定できない。GraphQL で本文を `-f body=` で直接渡したときも止める |
| 対象外 | 自分が作者の PR、`gh pr comment` / `gh pr review` の `--body` の直書き、本文を持たない呼び出し、スレッドへの返信 |
| 止め方 | 環境変数 `PR_REVIEW_MENTION_HOOK=off`（settings.json の `env` に書けば常に止まる） |

コマンドの文字列で判定するので、`echo` の引数などに投稿コマンドの形があっても照合が掛かる。

## 入れる

```sh
git clone https://github.com/takiguchi-yu/claude-skills.git ~/git/private/claude-skills
~/git/private/claude-skills/install.sh
```

`install.sh` は、このリポジトリを `directory` 型のマーケットプレイスとして登録し、`my` を user スコープで入れる（`CLAUDE_CONFIG_DIR` があればそのプロファイルに）。
`marketplace.json` に無くなった `@claude-skills` のプラグインと、`~/.claude/{skills,agents}` に張った、このリポジトリへのリンクは外す。何度実行しても同じ状態になる。
`directory` 型のマーケットプレイスのプラグインは元のディレクトリから読まれるので、ここでの編集は次のセッション起動か `/reload-plugins` で反映される。

[dotfiles](https://github.com/takiguchi-yu/dotfiles-public) の `setup.sh` は、このリポジトリを clone し、マーケットプレイスの登録をローカル設定に書いてから `install.sh` を呼ぶ。

## 足す・消す

- スキルを足す: `<ディレクトリ>/skills/<名前>/SKILL.md` を作る。新しいディレクトリなら、`plugin.json` の `skills` に `./<ディレクトリ>/skills` を足す
- エージェントを足す: `<ディレクトリ>/agents/<名前>.md` を作り、`plugin.json` の `agents` にそのファイルを足す（エージェントはファイルごとに列挙する）
- 消す: ファイルと `plugin.json` の行を消す
- どれも `/reload-plugins` で反映される。`install.sh` は、`plugin.json` に列挙し忘れたスキルのディレクトリとエージェントがあれば止まる

公開リポジトリなので、commit の前に lefthook で gitleaks を実行する（`lefthook install` で有効にする。独自の語は dotfiles のローカル設定 `~/.config/dotfiles/local/gitleaks.toml` を使う）。
