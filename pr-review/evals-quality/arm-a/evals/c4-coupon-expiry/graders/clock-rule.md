---
type: llm
weight: 1
---
最後のメッセージの指摘（インライン・総評のどちらでもよい）に、`CheckExpiry` が `time.Now()` を直接呼んでおり、`internal/clock` の `Clock` を引数で受け取るべきだ（docs/CODING_RULES.md の規約 9、またはテストで時刻を固定できない）という指摘があれば PASS。無ければ FAIL。
