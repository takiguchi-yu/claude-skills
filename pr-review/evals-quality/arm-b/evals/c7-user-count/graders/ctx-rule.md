---
type: llm
weight: 1
---
最後のメッセージの指摘（インライン・総評のどちらでもよい）に、`CountWithEmail` が `context.Context` を第 2 引数で受け取っており、第 1 引数にすべきだ（docs/CODING_RULES.md の規約 12、または Go の慣習）という指摘があれば PASS。無ければ FAIL。
