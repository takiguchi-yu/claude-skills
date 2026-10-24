---
type: llm
weight: 1
---
最後のメッセージの採用した指摘に、`SearchByName` が `fmt.Sprintf` で検索語を SQL に埋め込んでおり SQL インジェクションの恐れがある（プレースホルダを使うべき）という指摘が含まれていれば PASS。触れていなければ FAIL。
