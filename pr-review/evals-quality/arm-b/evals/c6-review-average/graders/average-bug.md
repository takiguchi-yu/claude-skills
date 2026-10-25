---
type: llm
weight: 1
---
最後のメッセージの指摘に、次のどちらか（両方でもよい）があれば PASS: (a) `sum / len(ratings)` が整数の割り算で小数が切り捨てられ、小数第 1 位まで出ない。(b) 口コミが 0 件だと `len(ratings)` が 0 でゼロ除算（panic）になり、issue の「0 件なら 0」を満たさない。どちらも無ければ FAIL。
