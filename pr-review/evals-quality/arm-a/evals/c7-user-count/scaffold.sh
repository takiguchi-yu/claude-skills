#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/../_shared/base-repo.sh"
cat >> docs/CODING_RULES.md <<'MD'
12. `context.Context` を受け取る関数は、それを第 1 引数 `ctx` にする。
MD
git add -A && git commit -q -m "docs: 規約 12"
git checkout -q -b feat/user-count
cat > internal/user/count.go <<'GO'
package user

import (
	"context"
	"database/sql"
	"fmt"
)

// CountWithEmail はメールアドレスが登録済みのユーザー数を返す。
func CountWithEmail(db *sql.DB, ctx context.Context) (int, error) {
	rows, err := db.QueryContext(ctx, "SELECT id FROM users WHERE email <> ''")
	defer rows.Close()
	if err != nil {
		return 0, fmt.Errorf("query users with email: %w", err)
	}
	n := 0
	for rows.Next() {
		n++
	}
	if err := rows.Err(); err != nil {
		return 0, fmt.Errorf("iterate users: %w", err)
	}
	return n, nil
}
GO
git add -A && git commit -q -m "feat: 有効なユーザー数を返す"
finish_pr feat/user-count
