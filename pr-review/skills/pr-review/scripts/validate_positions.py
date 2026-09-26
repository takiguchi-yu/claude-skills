#!/usr/bin/env python3
"""PR の diff に対して、インラインコメントの投稿位置が有効かを判定する。

GitHub はコメントを「diff のハンク内に現れる行」にしか付けられない。範囲外の
行を渡すと GraphQL が pull_request_review_thread.line エラーを返し、どのコメントが
悪かったのかは返ってこない。投稿前にここで落とす。

入力:
  --diff      `gh pr diff <番号>` の出力を保存したファイル（`-` で stdin）
  --comments  投稿候補の JSON 配列
  --out       検証結果 JSON の出力先（省略時は stdout に人間向けレポートのみ）

投稿候補 1 件の形:
  {
    "id":         "S1",            # 任意。レポートで指す名前
    "path":       "src/foo.ts",
    "line":       42,              # 複数行コメントでは範囲の「終わり」
    "side":       "RIGHT",         # RIGHT=変更後 / LEFT=変更前。省略時 RIGHT
    "start_line": 40,              # 任意。複数行コメントの開始行
    "start_side": "RIGHT",         # 任意。省略時は side と同じ
    "body":       "..."
  }

出力 JSON:
  {"valid": [...], "invalid": [{..., "reason": "...", "nearest": [..]}]}

終了コード: 全件有効なら 0、1 件でも無効なら 1。
"""

import argparse
import json
import re
import sys

HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


def parse_diff(text):
    """unified diff を {(path, side): set(line)} に畳む。

    コメントできるのは「ハンクに現れた行」なので、追加行・削除行だけでなく
    文脈行も入れる。文脈行は変更後・変更前の両側に現れる。

    ハンクヘッダの行数（`@@ -4,9 +4,13 @@` の 9 と 13）を消化しきるまでを
    ハンク本体とみなす。行の先頭 1 文字だけで判定すると、空白を除去された
    diff の空文脈行（`" "` ではなく `""`）で行番号が静かにずれる。
    ずれたまま投稿すると「有効だが違う行」に付くので、エラーより厄介。
    """
    commentable = {}
    renames = {}
    old_path = new_path = None
    old_no = new_no = 0
    old_left = new_left = 0

    def add(path, side, line):
        if path and path != "/dev/null":
            commentable.setdefault((path, side), set()).add(line)

    lines = text.splitlines()
    i = 0
    while i < len(lines):
        raw = lines[i]
        i += 1
        in_hunk = old_left > 0 or new_left > 0

        if not in_hunk:
            if raw.startswith("diff --git "):
                old_path = new_path = None
                continue
            if raw.startswith("--- "):
                old_path = strip_prefix(raw[4:])
                continue
            if raw.startswith("+++ "):
                new_path = strip_prefix(raw[4:])
                continue
            m = HUNK.match(raw)
            if m:
                old_no = int(m.group(1))
                old_left = int(m.group(2)) if m.group(2) is not None else 1
                new_no = int(m.group(3))
                new_left = int(m.group(4)) if m.group(4) is not None else 1
                if (old_path and new_path and old_path != new_path
                        and "/dev/null" not in (old_path, new_path)):
                    renames[old_path] = new_path
                continue
            continue  # ヘッダ行 (index / mode / Binary files) と余白

        head = raw[0] if raw else " "  # 空行はハンク内では空の文脈行
        if head == "\\":
            continue  # "\ No newline at end of file" は行を消費しない
        if head == "+":
            if new_left:
                add(new_path, "RIGHT", new_no)
                new_no += 1
                new_left -= 1
        elif head == "-":
            if old_left:
                add(old_path, "LEFT", old_no)
                old_no += 1
                old_left -= 1
        elif head == " ":
            if new_left:
                add(new_path, "RIGHT", new_no)
                new_no += 1
                new_left -= 1
            if old_left:
                add(old_path, "LEFT", old_no)
                old_no += 1
                old_left -= 1
        else:
            # ハンクの行数を消化しきる前に想定外の行が来た。ハンクを打ち切り、
            # この行をヘッダとして読み直す（壊れた diff で暴走させない）。
            old_left = new_left = 0
            i -= 1

    return commentable, renames


def strip_prefix(path):
    """diff ヘッダの `a/` `b/` を落とす。タブ以降のタイムスタンプも切る。"""
    path = path.split("\t")[0].strip()
    if path.startswith(("a/", "b/")):
        return path[2:]
    return path


def nearest(lines, target, count=3):
    return sorted(lines, key=lambda n: (abs(n - target), n))[:count]


def check(comment, commentable):
    """1 件を検証し、無効なら理由を返す。有効なら None。"""
    path = comment.get("path")
    line = comment.get("line")
    side = comment.get("side", "RIGHT")

    if not path:
        return "path が無い", []
    if side not in ("RIGHT", "LEFT"):
        return f"side は RIGHT か LEFT のみ（受け取った値: {side!r}）", []
    if not isinstance(line, int):
        return f"line が整数でない（受け取った値: {line!r}）", []

    paths_in_diff = {p for p, _ in commentable}
    if path not in paths_in_diff:
        hint = ""
        tail = [p for p in paths_in_diff if p.endswith("/" + path.split("/")[-1])]
        if tail:
            hint = f" diff にある似たパス: {', '.join(sorted(tail)[:3])}"
        return f"このパスは diff に含まれない。{hint}".rstrip(), []

    lines = commentable.get((path, side), set())
    if not lines:
        other = "LEFT" if side == "RIGHT" else "RIGHT"
        if commentable.get((path, other)):
            return f"{path} に {side} 側の行が無い。{other} 側なら行がある", []
        return f"{path} に {side} 側の行が無い", []

    if line not in lines:
        return (
            f"{line} 行目は diff のハンク外（{side} 側）",
            nearest(lines, line),
        )

    start = comment.get("start_line")
    if start is not None:
        start_side = comment.get("start_side", side)
        if start_side not in ("RIGHT", "LEFT"):
            return f"start_side は RIGHT か LEFT のみ（受け取った値: {start_side!r}）", []
        if not isinstance(start, int):
            return f"start_line が整数でない（受け取った値: {start!r}）", []
        if start > line:
            return f"start_line {start} が line {line} より後ろ", []
        start_lines = commentable.get((path, start_side), set())
        if start not in start_lines:
            return (
                f"start_line {start} は diff のハンク外（{start_side} 側）",
                nearest(start_lines, start),
            )

    return None, []


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--diff", required=True, help="gh pr diff の出力ファイル（- で stdin）")
    ap.add_argument("--comments", required=True, help="投稿候補の JSON 配列ファイル")
    ap.add_argument("--out", help="検証結果 JSON の出力先")
    args = ap.parse_args()

    diff_text = sys.stdin.read() if args.diff == "-" else open(args.diff, encoding="utf-8").read()
    with open(args.comments, encoding="utf-8") as f:
        comments = json.load(f)
    if not isinstance(comments, list):
        sys.exit("--comments は JSON 配列でなければならない")

    commentable, renames = parse_diff(diff_text)
    if not commentable:
        sys.exit("diff からコメント可能な行を 1 行も読み取れなかった。diff ファイルの中身を確認すること")

    valid, invalid, warnings = [], [], []
    for i, c in enumerate(comments):
        cid = c.get("id") or f"#{i}"
        reason, near = check(c, commentable)
        if reason is None:
            valid.append(c)
            if c.get("path") in renames:
                warnings.append(
                    f"{cid}: {c['path']} はこの PR でリネームされている（→ {renames[c['path']]}）。"
                    f"GitHub がリネーム後のパスしか受け付けない可能性がある。"
                    f"投稿が 422 で落ちたら path を {renames[c['path']]} に変えて試すこと"
                )
        else:
            invalid.append({**c, "id": cid, "reason": reason, "nearest": near})

    files = sorted({p for p, _ in commentable})
    print(f"diff: {len(files)} ファイル / コメント可能な行 {sum(len(v) for v in commentable.values())}")
    print(f"検証: 全 {len(comments)} 件 → 有効 {len(valid)} 件 / 無効 {len(invalid)} 件")
    for c in invalid:
        print(f"\n  ✗ {c['id']}  {c.get('path')}:{c.get('line')} ({c.get('side', 'RIGHT')})")
        print(f"    理由: {c['reason']}")
        if c["nearest"]:
            print(f"    近い有効行: {', '.join(map(str, c['nearest']))}")

    for w in warnings:
        print(f"\n  ⚠ {w}")

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump({"valid": valid, "invalid": invalid, "warnings": warnings},
                      f, ensure_ascii=False, indent=2)
        print(f"\n検証結果を書き出した: {args.out}")

    if invalid:
        print("\n無効な件は行を直すか、行を特定できないならファイル単位（subjectType: FILE）に落とすこと。")
    sys.exit(1 if invalid else 0)


if __name__ == "__main__":
    main()
