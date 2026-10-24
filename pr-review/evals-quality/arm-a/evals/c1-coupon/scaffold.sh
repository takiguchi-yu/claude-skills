#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/../_shared/base-repo.sh"
git checkout -q -b feat/coupon-discount
cat >> internal/coupon/coupon.go <<'GO'

// Discount はクーポン適用時の割引額を返す。
func Discount(total int) int {
	amt := total / 10
	return amt
}

func DiscountFor(ctx context.Context, s Store, orderID int64) (int, error) {
	total, err := s.OrderTotal(ctx, orderID)
	if err != nil {
		return 0, errors.New("load order total failed: " + err.Error())
	}
	return Discount(total), nil
}
GO
perl -0pi -e 's/\t"fmt"\n/\t"errors"\n\t"fmt"\n/' internal/coupon/coupon.go
git add -A && git commit -q -m "feat: クーポン割引を追加"
finish_pr feat/coupon-discount
