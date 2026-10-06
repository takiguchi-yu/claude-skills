# claude-skills

自作の Claude Code スキルと、それが使うサブエージェント。配布はしない。自分の PC に入れて使う。

## 構成

1 ディレクトリに、1 つのスキルと、そのスキルが前提にするエージェントを入れる。
中身は Claude Code のプラグインと同じ並び（`skills/<名前>/` と `agents/`）にしてあるので、プラグインに移るときはマニフェストを足すだけで済む。

| ディレクトリ | スキル | エージェント |
| --- | --- | --- |
| `complete-task/` | complete-task | ct-researcher / ct-review-accuracy / ct-review-ux / ct-review-risk / ct-verifier |
| `pr-comments/` | pr-comments | pr-comment-verifier |
| `pr-review/` | pr-review | pr-review-functionality |
| `consistency-check/` | consistency-check | — |
| `oo-design/` | oo-design | — |
| `spec-notation/` | spec-notation | — |

## 入れる

```sh
git clone https://github.com/takiguchi-yu/claude-skills.git ~/git/private/claude-skills
~/git/private/claude-skills/install.sh
```

`install.sh` は、スキルを `~/.claude/skills/<名前>`、エージェントを `~/.claude/agents/<名前>.md` にリンクする（`CLAUDE_CONFIG_DIR` があればそちら）。
リンクなので、ここで編集すればすぐに反映される。何度実行しても同じ状態になる。
リンク先に実体か別のリンクがあれば、`~/.local/state/claude-skills/backup/<日時>/` に退避する。

[dotfiles](https://github.com/takiguchi-yu/dotfiles-public) の `setup.sh` は、このリポジトリを clone して `install.sh` を呼ぶ。

## 足す・消す

- 足す: `<ディレクトリ>/skills/<名前>/SKILL.md` を作り（使うエージェントがあれば `<ディレクトリ>/agents/` に置く）、`./install.sh`
- 消す・名前を変える: ファイルを動かしてから `./install.sh`。リンク先が無くなったリンクは外れる

公開リポジトリなので、commit の前に lefthook で gitleaks を実行する（`lefthook install` で有効にする。独自の語は dotfiles のローカル設定 `~/.config/dotfiles/local/gitleaks.toml` を使う）。
