---
type: llm
weight: 1
---
最後のメッセージの採用した指摘に、`log.Printf` でユーザーのメールアドレスをログに出している（個人情報。docs/CODING_RULES.md の規約 2 に反する、ID で示すべき）という指摘が含まれていれば PASS。触れていなければ FAIL。
