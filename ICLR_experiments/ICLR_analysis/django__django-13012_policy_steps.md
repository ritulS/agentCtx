# django__django-13012: qwen35b policy別の実行手順

対象: `ICLR_experiments/swebench/main/qwen35b`。主比較は15K（DTはdepth=0.5）とFC/OTRCの無制限条件。10K・20Kは補足として別表に掲載。

記録上のstepは `experiment_results.json` の `n_calls`（`trajectory.json` の `info.model_stats.api_calls` と全件照合）。探索・検証・書式エラー後の再試行・提出を含むため、タスクの必要最小手数ではない。圧縮後のtrajectoryには過去のメッセージが残らない場合があるので、段階の確認には `agent.log` のstep番号を使用した。

必要な作業の骨格はpolicy間で共通:

1. `ExpressionWrapper`、基底式、`Value` の `get_group_by_cols()` を調べ、定数が除外されなくなる箇所を特定する。
2. 最小のDjango設定・モデルで、ラップした `Value(3)` と直接の `Value(3)` の生成SQLを比較し、余分なGROUP BY項を再現する。
3. `django/db/models/expressions.py` の `ExpressionWrapper.get_group_by_cols(self, alias=None)` を内部式に委譲する。
4. 定数がGROUP BYから消えること、列参照・集約式・ネストなどの振る舞いを確認する。
5. ソース変更のdiffを確認し、パッチを作成・提出する。

複数の評価成功パッチに共通する最小形:

```python
def get_group_by_cols(self, alias=None):
    return self.expression.get_group_by_cols(alias=alias)
```

## 主条件: 各runの実測step数

✓ = evalファイルで成功確認、× = evalファイルで未解決確認、△ = 集計上resolved=Falseだが該当evalファイルがないため未確認、上限 = LimitsExceeded。

| Policy | run 1 | run 2 | run 3 |
|---|---:|---:|---:|
| FC | 82 △ | 44 △ | 47 ✓ |
| OTRC | 52 ✓ | 119 ✓ | 59 ✓ |
| TR | 125 上限 | 125 上限 | 125 上限 |
| SU-full | 39 △ | 111 ✓ | 38 ✓ |
| SU-partial | 54 ✓ | 32 ✓ | 30 ✓ |
| SS | 56 ✓ | 53 ✓ | 50 ✓ |
| SS-partial | 39 ✓ | 103 ✓ | 69 ✓ |
| TRC | 40 △ | 43 △ | 73 ✓ |
| TRC+SU | 70 ✓ | 52 ✓ | 79 ✓ |
| TRC+SS | 47 ✓ | 69 ✓ | 69 × |
| OTRC+TR | 70 ✓ | 45 ✓ | 54 ✓ |
| OTRC+SU-partial | 54 ✓ | 52 ✓ | 65 ✓ |
| OTRC+SS-partial | 64 ✓ | 59 × | 56 ✓ |

## 実際の手順: 代表run

各policyでeval成功が確認できた最少stepのrunを選択（必要最小手数という意味ではない）。TRは成功runがないためrun 1。番号はagent.logのstep。検証欄は自作スクリプトの観測であり、既存テストが全件通ったことを意味しない。

| Policy | run | 修正step | 改善確認step | 提出/終了step |
|---|---:|---|---|---|
| FC | 3 | 39 | 40 | 47 |
| OTRC | 1 | 31 | 36 | 52 |
| TR | 1 | 30 | 31 | 125で上限 |
| SU-full | 3 | 26 | 28 | 38 |
| SU-partial | 3 | 22 | 23 | 30 |
| SS | 3 | 28–31 | 33 | 50 |
| SS-partial | 1 | 20–25 | 27 / SQLは38 | 39 |
| TRC | 3 | 49 | 52 | 73 |
| TRC+SU | 2 | 23（追加修正39） | 24 | 52 |
| TRC+SS | 1 | 25 | 27 | 47 |
| OTRC+TR | 2 | 23 | 25 | 45 |
| OTRC+SU-partial | 2 | 33 | 35 | 52 |
| OTRC+SS-partial | 3 | 33 | 35 | 56 |

### FC: run 3

1–13 調査、14–34 再現環境の準備・再現、35–38 再確認、39 修正、40 SQL確認、42–43 境界ケース確認、45–47 パッチ作成・提出。

圧縮イベント記録step: `[]`。オンラインtool-result clear: 0回。

根拠: [agent.log](../swebench/main/qwen35b/di__binf__fc/django__django-13012/full-context/run_3/agent.log) / [trajectory.json](../swebench/main/qwen35b/di__binf__fc/django__django-13012/full-context/run_3/trajectory.json)。

### OTRC: run 1

2–19 調査、20–26 再現、27–30 再確認、31 修正、34–38 書式調整と再確認、39–50 追加検証、52 提出。

圧縮イベント記録step: `[]`。オンラインtool-result clear: 47回。

根拠: [agent.log](../swebench/main/qwen35b/di__binf__otrc/django__django-13012/online-trc/run_1/agent.log) / [trajectory.json](../swebench/main/qwen35b/di__binf__otrc/django__django-13012/online-trc/run_1/trajectory.json)。

### TR: run 1

1–18 調査、20–27 再現、30 修正、31 SQL改善確認、33–35 境界ケース確認。その後テスト起動・ソース再調査・再現スクリプトの書き直しを続け、125で上限。提出なし。

圧縮イベント記録step: `[30, 39, 56, 71, 83, 99, 116]`。オンラインtool-result clear: 0回。

根拠: [agent.log](../swebench/main/qwen35b/d05__b15k__tr/django__django-13012/truncation/run_1/agent.log) / [trajectory.json](../swebench/main/qwen35b/d05__b15k__tr/django__django-13012/truncation/run_1/trajectory.json)。

### SU-full: run 3

1–17 調査、18–24 再現、26 修正、28 SQL確認、29–33 追加検証、35 提出失敗（patch.txtなし）、36 パッチ作成、37 テスト試行、38 提出。

圧縮イベント記録step: `[29]`。オンラインtool-result clear: 0回。

根拠: [agent.log](../swebench/main/qwen35b/d05__b15k__su-full/django__django-13012/summarization/run_3/agent.log) / [trajectory.json](../swebench/main/qwen35b/d05__b15k__su-full/django__django-13012/summarization/run_3/trajectory.json)。

### SU-partial: run 3

1–15 調査、16–20 再現、22 修正、23 SQL確認、25–27 境界ケース検証、28 diff確認、29 提出失敗（patch.txtなし）、30 パッチ作成・提出。

圧縮イベント記録step: `[28]`。オンラインtool-result clear: 0回。

根拠: [agent.log](../swebench/main/qwen35b/d05__b15k__su-partial/django__django-13012/summarization-partial/run_3/agent.log) / [trajectory.json](../swebench/main/qwen35b/d05__b15k__su-partial/django__django-13012/summarization-partial/run_3/trajectory.json)。

### SS: run 3

1–16 調査、17–26 再現、28 修正挿入、31 書式修正、33 SQL改善確認、34–43 追加テスト・テスト環境調整、44–47 diffと再現の再確認、48 提出失敗、49 パッチ作成、50 提出。

圧縮イベント記録step: `[34]`。オンラインtool-result clear: 0回。

根拠: [agent.log](../swebench/main/qwen35b/d05__b15k__ss/django__django-13012/structured-summarize/run_3/agent.log) / [trajectory.json](../swebench/main/qwen35b/d05__b15k__ss/django__django-13012/structured-summarize/run_3/trajectory.json)。

### SS-partial: run 1

1–13 調査、14–18 再現、20 修正挿入、23・25 書式修正、27 get_group_by_colsの戻り値確認、28–32 追加テスト、34–35 再確認、36 提出失敗、37 パッチ作成、38 SQL・境界ケース確認、39 提出。

圧縮イベント記録step: `[29]`。オンラインtool-result clear: 0回。

根拠: [agent.log](../swebench/main/qwen35b/d05__b15k__ss-partial/django__django-13012/structured-summarize-partial/run_1/agent.log) / [trajectory.json](../swebench/main/qwen35b/d05__b15k__ss-partial/django__django-13012/structured-summarize-partial/run_1/trajectory.json)。

### TRC: run 3

1–11 調査、12–27 再現準備、28–48 ソース再調査、49 修正、51 SQLは改善しているが自作判定が誤警告、52 判定スクリプトを直して改善確認、53–70 複合式の追加調査、71 diff、72 提出失敗、73 パッチ作成・提出。

圧縮イベント記録step: `[35, 53, 65]`。オンラインtool-result clear: 0回。

根拠: [agent.log](../swebench/main/qwen35b/di__b15k__trc/django__django-13012/tool-result-clear/run_3/agent.log) / [trajectory.json](../swebench/main/qwen35b/di__b15k__trc/django__django-13012/tool-result-clear/run_3/trajectory.json)。

### TRC+SU: run 2

1–14 調査、15–20 再現、23 修正、24 SQL改善確認、26–38 複合式の検証・調査、39 CombinedExpressionにも修正を追加、40–49 検証、51 パッチ作成、52 提出。

圧縮イベント記録step: `[27, 36, 41, 49]`。オンラインtool-result clear: 0回。

根拠: [agent.log](../swebench/main/qwen35b/di__b15k__trc-su/django__django-13012/trc-su/run_2/agent.log) / [trajectory.json](../swebench/main/qwen35b/di__b15k__trc-su/django__django-13012/trc-su/run_2/trajectory.json)。

### TRC+SS: run 1

1–13 調査、14–22 再現、25 修正、27 SQL改善確認、28 境界ケース検証、29–42 既存テストの起動試行・再確認、43–46 整理と最終検証、47 提出。

圧縮イベント記録step: `[21]`。オンラインtool-result clear: 0回。

根拠: [agent.log](../swebench/main/qwen35b/di__b15k__trc-ss/django__django-13012/trc-ss/run_1/agent.log) / [trajectory.json](../swebench/main/qwen35b/di__b15k__trc-ss/django__django-13012/trc-ss/run_1/trajectory.json)。

### OTRC+TR: run 2

2–16 調査、17–19 再現、23 修正、25 SQL改善確認、26 境界ケース検証、27–43 既存テスト起動・追加確認、44 パッチ作成、45 提出。

圧縮イベント記録step: `[]`。オンラインtool-result clear: 40回。

根拠: [agent.log](../swebench/main/qwen35b/di__b15k__otrc-tr/django__django-13012/otrc-tr/run_2/agent.log) / [trajectory.json](../swebench/main/qwen35b/di__b15k__otrc-tr/django__django-13012/otrc-tr/run_2/trajectory.json)。

### OTRC+SU-partial: run 2

1–17 調査、18–30 再現環境の準備・再現、33 修正、35 SQL改善確認、36–46 追加検証・既存テスト起動試行、48–49 再確認、50 提出失敗、51 パッチ作成、52 提出。

圧縮イベント記録step: `[]`。オンラインtool-result clear: 47回。

根拠: [agent.log](../swebench/main/qwen35b/di__b15k__otrc-su-partial/django__django-13012/otrc-su-partial/run_2/agent.log) / [trajectory.json](../swebench/main/qwen35b/di__b15k__otrc-su-partial/django__django-13012/otrc-su-partial/run_2/trajectory.json)。

### OTRC+SS-partial: run 3

2–22 調査、23–29 再現、33 修正、35 SQL改善確認、36–49 追加検証・既存テスト起動試行、50–55 diff確認・整理・最終検証、56 提出。

圧縮イベント記録step: `[]`。オンラインtool-result clear: 51回。

根拠: [agent.log](../swebench/main/qwen35b/di__b15k__otrc-ss-partial/django__django-13012/otrc-ss-partial/run_3/agent.log) / [trajectory.json](../swebench/main/qwen35b/di__b15k__otrc-ss-partial/django__django-13012/otrc-ss-partial/run_3/trajectory.json)。

## 解釈上の注意

- TR run 1はstep 30で修正し、31でSQL改善を確認済みだが、提出に至らず125で終了。修正発見とタスク完了を分けて考える必要がある。圧縮記録は30、39、56、71、83、99、116。圧縮が失敗を引き起こしたという因果までは、このログ比較だけでは確定できない。
- SU-partial run 3は22で修正、23で改善確認、28に圧縮記録、30で提出。早く修正できた理由を圧縮効果と断定できない。
- 15KのOTRC+TR、OTRC+SU-partial、OTRC+SS-partialは全runで閾値圧縮イベント0。オンラインtool-result clearは作動しているが、追加のTR/SU/SS処理の効果比較にはならない。
- FC run 1/2、TRC run 1/2、SU-full run 1は集計上resolved=Falseだが当該evalが存在しない。特にFC run 1/2のパッチはSU-partial run 2の成功パッチと同一なので、単純な修正能力の差と解釈しない。今回は再評価していない。
- TRC+SU run 2は本題の修正後にCombinedExpressionも変更。これは観測された追加作業であり、本題に不可欠な修正ではない。評価成功は、追加変更の一般的な正しさを保証しない。

## 補足: 10K・20Kの保存済みrun

— は該当cellにこのタスクの実行結果レコードがないことを表す。中断/未判定は集計の終了記録で成功を確認できないもの。

| Cell | run 1 | run 2 | run 3 |
|---|---:|---:|---:|
| `d05__b10k__ss` | — | — | — |
| `d05__b10k__ss-partial` | — | — | — |
| `d05__b10k__su-full` | 69 ✓ | — | 61 ✓ |
| `d05__b10k__su-partial` | — | — | — |
| `d05__b10k__tr` | 125 上限 | 36 ✓ | 125 上限 |
| `d05__b20k__ss` | 125 上限 | — | 51 ✓ |
| `d05__b20k__ss-partial` | — | — | 59 ✓ |
| `d05__b20k__su-full` | — | — | 86 中断/未判定 |
| `d05__b20k__su-partial` | 125 上限 | 37 ✓ | — |
| `d05__b20k__tr` | 70 ✓ | 121 中断/未判定 | 125 上限 |
| `di__b10k__otrc-ss-partial` | — | — | — |
| `di__b10k__otrc-su-partial` | — | — | — |
| `di__b10k__otrc-tr` | 46 ✓ | 125 上限 | 49 ✓ |
| `di__b10k__trc` | 125 上限 | 54 ✓ | 45 ✓ |
| `di__b10k__trc-ss` | — | — | — |
| `di__b10k__trc-su` | — | 125 上限 | 59 中断/未判定 |
| `di__b20k__otrc-ss-partial` | 41 ✓ | 40 ✓ | 49 ✓ |
| `di__b20k__otrc-su-partial` | 63 ✓ | 74 ✓ | 80 ✓ |
| `di__b20k__otrc-tr` | 51 ✓ | 61 ✓ | 52 × |
| `di__b20k__trc` | 36 ✓ | 125 上限 | 77 ✓ |
| `di__b20k__trc-ss` | 72 ✓ | 125 上限 | 123 中断/未判定 |
| `di__b20k__trc-su` | 62 ✓ | 77 ✓ | 77 ✓ |

全79 runの数値・評価確認状況・参照パス: [django__django-13012_policy_steps.csv](django__django-13012_policy_steps.csv)。
