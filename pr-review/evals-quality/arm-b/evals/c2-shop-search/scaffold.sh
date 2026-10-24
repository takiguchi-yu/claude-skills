#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/../_shared/base-repo.sh"
git checkout -q -b feat/shop-search
cat >> internal/shop/shop.go <<'GO'

// SearchByName は店名の部分一致で店舗を返す。
func SearchByName(ctx context.Context, db *sql.DB, name string) ([]Shop, error) {
	q := fmt.Sprintf("SELECT id, name FROM shops WHERE name LIKE '%%%s%%'", name)
	rows, err := db.QueryContext(ctx, q)
	if err != nil {
		return nil, fmt.Errorf("query shops by name: %w", err)
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
	return shops, nil
}
GO
cat > internal/shop/shop_test.go <<'GO'
package shop

import "testing"

func TestSearchByNameSignature(t *testing.T) {
	_ = SearchByName
}
GO
git add -A && git commit -q -m "feat: 店名の部分一致検索を追加"
finish_pr feat/shop-search
