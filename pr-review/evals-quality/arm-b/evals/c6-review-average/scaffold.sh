#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/../_shared/base-repo.sh"
cat >> docs/CODING_RULES.md <<'MD'
11. JSON で返す構造体のフィールドには、`json:"snake_case"` のタグを付ける。
MD
perl -0pi -e 's/\tID   int64\n\tName string\n/\tID   int64  `json:"id"`\n\tName string `json:"name"`\n/' internal/shop/shop.go
git add -A && git commit -q -m "chore: Shop に JSON タグ"
git checkout -q -b feat/review-average
cat > internal/shop/review.go <<'GO'
package shop

import "math"

type ReviewSummary struct {
	ShopID  int64   `json:"shopId"`
	Average float64 `json:"averageRating"`
}

// Summarize は評価（1〜5）の一覧から平均を小数第 1 位まで求める。
func Summarize(shopID int64, ratings []int) ReviewSummary {
	sum := 0
	for _, r := range ratings {
		sum += r
	}
	avg := float64(sum / len(ratings))
	return ReviewSummary{ShopID: shopID, Average: math.Round(avg*10) / 10}
}
GO
git add -A && git commit -q -m "feat: 口コミ平均を返す"
finish_pr feat/review-average
