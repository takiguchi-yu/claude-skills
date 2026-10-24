#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/../_shared/base-repo.sh"
git checkout -q -b feat/user-page
cat > internal/user/page.go <<'GO'
package user

import (
	"context"
	"database/sql"
	"fmt"
	"log"
)

// Page は 1 始まりのページ番号 page で、1 ページ size 件のユーザーを返す。
func Page(ctx context.Context, db *sql.DB, page, size int) ([]User, error) {
	if page < 1 || size < 1 {
		return nil, fmt.Errorf("invalid page %d or size %d", page, size)
	}
	users, err := List(ctx, db, page*size, size)
	if err != nil {
		return nil, fmt.Errorf("list users page %d: %w", page, err)
	}
	for _, u := range users {
		log.Printf("listed user %s", u.Email)
	}
	return users, nil
}
GO
cat > internal/user/page_test.go <<'GO'
package user

import "testing"

func TestPageRejectsZero(t *testing.T) {
	if _, err := Page(nil, nil, 0, 10); err == nil {
		t.Fatal("want error for page 0")
	}
}
GO
git add -A && git commit -q -m "feat: ユーザー一覧のページングを追加"
finish_pr feat/user-page
