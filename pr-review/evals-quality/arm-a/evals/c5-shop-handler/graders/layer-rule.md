---
type: llm
weight: 1
---
最後のメッセージの指摘（インライン・総評のどちらでもよい）に、ハンドラ `Shop` が SQL を直接実行しており（`db.QueryRowContext`）、`internal/shop` などリポジトリ層の関数を経由すべきだ（docs/CODING_RULES.md の規約 10、または層の責務の崩れ）という指摘があれば PASS。無ければ FAIL。
