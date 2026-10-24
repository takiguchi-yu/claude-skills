#!/usr/bin/env bash
# 3 ケース共通の土台: 規約文書と既存コードを持つ小さな Go サービスを main に作る。
# ケースの scaffold.sh が source し、その上に PR ブランチを積む。
set -euo pipefail
git init -q -b main .
git config user.email eval@example.invalid
git config user.name eval
mkdir -p docs internal/coupon internal/shop internal/user
cat > go.mod <<'GO'
module example.invalid/shopapi

go 1.22
GO
cat > docs/CODING_RULES.md <<'MD'
# コーディング規約

1. 呼び出し先から受け取ったエラーを返すときは `fmt.Errorf("<何をしていたか>: %w", err)` でラップする。文字列連結や `errors.New` で作り直さない（`errors.Is` で判定できなくなるため）。
2. ログにメールアドレス・電話番号などの個人情報を出さない。利用者はユーザー ID で示す。
3. SQL は必ずプレースホルダ（`?`）で値を渡す。文字列の組み立てで値を埋め込まない。
4. `rows.Next()` のループの後は `rows.Err()` を確認する。
5. 振る舞いを変えたら、その振る舞いのテストを同じ PR に入れる。
6. 業務上の閾値・率・上限は、関数の中に数値で直書きせず、パッケージの `const` に名前を付けて定義する。
7. ログは `log/slog` で出す。標準の `log` パッケージは使わない。
8. パッケージに公開関数を足したら、そのパッケージの `doc.go` にある関数一覧に 1 行追記する。
MD
cat > internal/coupon/coupon.go <<'GO'
package coupon

import (
	"context"
	"fmt"
)

type Store interface {
	OrderTotal(ctx context.Context, orderID int64) (int, error)
}

const (
	FreeShippingThreshold = 5000 // この額以上は送料無料
	ShippingFee           = 500
)

// Shipping は注文額に応じた送料を返す。
func Shipping(total int) int {
	if total >= FreeShippingThreshold {
		return 0
	}
	return ShippingFee
}

func ShippingFor(ctx context.Context, s Store, orderID int64) (int, error) {
	total, err := s.OrderTotal(ctx, orderID)
	if err != nil {
		return 0, fmt.Errorf("load order total: %w", err)
	}
	return Shipping(total), nil
}
GO
cat > internal/coupon/coupon_test.go <<'GO'
package coupon

import "testing"

func TestShipping(t *testing.T) {
	cases := []struct{ total, want int }{{4999, 500}, {5000, 0}}
	for _, c := range cases {
		if got := Shipping(c.total); got != c.want {
			t.Errorf("Shipping(%d) = %d, want %d", c.total, got, c.want)
		}
	}
}
GO
cat > internal/shop/shop.go <<'GO'
package shop

import (
	"context"
	"database/sql"
	"fmt"
)

type Shop struct {
	ID   int64
	Name string
}

func FindByArea(ctx context.Context, db *sql.DB, area string) ([]Shop, error) {
	rows, err := db.QueryContext(ctx, "SELECT id, name FROM shops WHERE area = ?", area)
	if err != nil {
		return nil, fmt.Errorf("query shops by area: %w", err)
	}
	defer rows.Close()
	shops := []Shop{}
	for rows.Next() {
		var s Shop
		if err := rows.Scan(&s.ID, &s.Name); err != nil {
			return nil, fmt.Errorf("scan shop: %w", err)
		}
		shops = append(shops, s)
	}
	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("iterate shops: %w", err)
	}
	return shops, nil
}
GO
cat > internal/shop/doc.go <<'GO'
// Package shop は店舗の検索を提供する。
//
// 公開関数:
//   - FindByArea: エリアで店舗を返す
package shop
GO
cat > internal/user/user.go <<'GO'
package user

import (
	"context"
	"database/sql"
	"fmt"
)

type User struct {
	ID    int64
	Email string
}

// List は offset から limit 件を返す。limit の上限は設けていない。
func List(ctx context.Context, db *sql.DB, offset, limit int) ([]User, error) {
	rows, err := db.QueryContext(ctx, "SELECT id, email FROM users ORDER BY id LIMIT ? OFFSET ?", limit, offset)
	if err != nil {
		return nil, fmt.Errorf("query users: %w", err)
	}
	defer rows.Close()
	users := []User{}
	for rows.Next() {
		var u User
		if err := rows.Scan(&u.ID, &u.Email); err != nil {
			return nil, fmt.Errorf("scan user: %w", err)
		}
		users = append(users, u)
	}
	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("iterate users: %w", err)
	}
	return users, nil
}
GO
git add -A && git commit -q -m "initial"

# PR ブランチを積んだ後にケースの scaffold.sh が呼ぶ。eval の実行はサンドボックスの中で git が動かないため、
# pr-review の手順 2 が作る材料をここで先に作り、head をチェックアウトしておく。
finish_pr() {
	local head="$1"
	mkdir -p .pr
	git diff main..."$head" > .pr/pr.diff
	git diff --name-only main..."$head" > .pr/files.txt
	git log --oneline main.."$head" > .pr/commits.txt
	echo ".pr/" >> .git/info/exclude
	git checkout -q "$head"
}
