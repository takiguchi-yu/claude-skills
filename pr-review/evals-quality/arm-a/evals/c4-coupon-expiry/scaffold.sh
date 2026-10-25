#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/../_shared/base-repo.sh"
cat >> docs/CODING_RULES.md <<'MD'
9. 現在時刻は `time.Now()` を直接呼ばず、`internal/clock` の `Clock` を引数で受け取って `Now()` を呼ぶ（テストで時刻を固定するため）。
MD
mkdir -p internal/clock
cat > internal/clock/clock.go <<'GO'
package clock

import "time"

type Clock interface{ Now() time.Time }

type System struct{}

func (System) Now() time.Time { return time.Now() }
GO
git add -A && git commit -q -m "chore: clock を足す"
git checkout -q -b feat/coupon-expiry
cat > internal/coupon/expiry.go <<'GO'
package coupon

import (
	"errors"
	"time"
)

var ErrExpired = errors.New("coupon expired")

type Coupon struct {
	Code      string
	ExpiresOn time.Time // 有効期限の日付（その日の 0 時で持つ）
}

// CheckExpiry はクーポンが期限切れなら ErrExpired を返す。
func CheckExpiry(c Coupon) error {
	if time.Now().After(c.ExpiresOn) {
		return ErrExpired
	}
	return nil
}
GO
git add -A && git commit -q -m "feat: クーポンの有効期限を判定する"
finish_pr feat/coupon-expiry
