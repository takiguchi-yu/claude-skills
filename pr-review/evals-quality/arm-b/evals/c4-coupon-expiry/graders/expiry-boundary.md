---
type: llm
weight: 1
---
最後のメッセージの指摘に、`ExpiresOn` がその日の 0 時なので `time.Now().After(c.ExpiresOn)` だと期限当日の 0 時を過ぎた時点で期限切れになり、issue の「期限の日の終わりまで使える」を満たさない、という指摘があれば PASS。無ければ FAIL。
