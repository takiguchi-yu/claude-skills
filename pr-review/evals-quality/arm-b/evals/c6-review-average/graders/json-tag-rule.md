---
type: llm
weight: 1
---
最後のメッセージの指摘（インライン・総評のどちらでもよい）に、`ReviewSummary` の JSON タグが camelCase（`shopId`・`averageRating`）で、docs/CODING_RULES.md の規約 11（snake_case）や既存の `Shop` のタグと食い違う、という指摘があれば PASS。無ければ FAIL。
