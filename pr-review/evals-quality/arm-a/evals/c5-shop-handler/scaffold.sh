#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/../_shared/base-repo.sh"
cat >> docs/CODING_RULES.md <<'MD'
10. `internal/handler` は `database/sql` を import しない。DB へのアクセスは `internal/shop` などのリポジトリ層の関数を経由する。
MD
mkdir -p internal/handler
cat > internal/shop/db.go <<'GO'
package shop

import "database/sql"

// DB はリポジトリ層の関数が受け取る DB の型。ハンドラ層はこの型だけを知る。
type DB = *sql.DB
GO
cat > internal/handler/area.go <<'GO'
package handler

import (
	"encoding/json"
	"net/http"

	"example.invalid/shopapi/internal/shop"
)

// Area は GET /shops/area?area=<名前> を返す。
func Area(db shop.DB) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		shops, err := shop.FindByArea(r.Context(), db, r.URL.Query().Get("area"))
		if err != nil {
			http.Error(w, "internal error", http.StatusInternalServerError)
			return
		}
		_ = json.NewEncoder(w).Encode(shops)
	}
}
GO
git add -A && git commit -q -m "chore: エリア検索のハンドラ"
git checkout -q -b feat/shop-handler
cat > internal/handler/shop.go <<'GO'
package handler

import (
	"encoding/json"
	"net/http"
	"strconv"

	"example.invalid/shopapi/internal/shop"
)

// Shop は GET /shops?id=<数値> を返す。
func Shop(db shop.DB) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		id, _ := strconv.Atoi(r.URL.Query().Get("id"))
		var s shop.Shop
		err := db.QueryRowContext(r.Context(), "SELECT id, name FROM shops WHERE id = ?", id).Scan(&s.ID, &s.Name)
		if err != nil {
			http.Error(w, "internal error", http.StatusInternalServerError)
			return
		}
		_ = json.NewEncoder(w).Encode(s)
	}
}
GO
git add -A && git commit -q -m "feat: 店舗詳細のハンドラを追加"
finish_pr feat/shop-handler
