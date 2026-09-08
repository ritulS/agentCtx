# 再開ログ監査 — 2026-09-08

対象はQwen SWE-benchの2026-09-07 20:01:53 CDT再開から、保存済み最終結果2026-09-08 12:55:43 CDTまで。親ログで新規完了した645 runと、更新された645 trajectory、結果indexのtimestampを照合した。過去結果・他モデル・別マシンは今回の集計対象外。実験コードと結果は変更していない。

## 確認結果

- 保存trajectoryでFormatErrorが337/645 run、767イベント。一般的なaction書式違反も含むため、全件がsummaryバグという意味ではない。
- summary markerを含む拒否応答は33 run、42イベント。うち31イベントは、直前のuserメッセージにsummaryと`</think>`がある。具体例では要約は既に格納されており、次のagent応答が再び要約を生成して`Expected exactly 1 action, found 0`になる。
- 保存された構造化summaryメッセージ220個中219個に`</think>`を含む前置きが残り、9個は終了markerを欠く。最終trajectoryに残ったメッセージだけの集計であり、全2085圧縮イベントの品質検査ではない。思考文の混入が再要約を誘発している可能性があるが、因果は未確定。
- 現行memory.pyのquery_summaryはparserを無効にしたコピーで問い合わせ、通常agent側のparserは維持する。ローカルの模擬応答でも、summaryは受理され、同じ本文を通常agentが返すとFormatErrorになることを確認。旧バグの再発とは断定できず、要約をagentに戻す内容と再開指示の改善が必要。
- agentの1500秒timeoutは152/645 run（23.6%）。特にmain OTRC+SS-partialは52/89（58.4%）、ablation d03/10k SSは22/46（47.8%）。152件中151件のexit_statusは空文字、1件はSubmittedだがプロセス終了待ちでtimeoutした記録。timeout行もindexに登録され、run_all_agentsはkeyの存在だけでskipするため、通常の再開では再実行されない。
- 評価の600秒timeoutは8件、すべてscikit-learn__scikit-learn-14710。これはFAILEDではなくERROR（resolved=null）。summaryを使わないTRC、FC、OTRC等にも発生しており、評価側で別途切り分けが必要。TRC r3の評価ログはeval.shをcontainerへコピーする段階で途切れている。
- 再開時のvLLMプロセスpid=2552238以降にERROR・HTTP 400/500記録なし。645 runすべてtrajectory/token_logをJSONとして読め、結果indexの欠落とstep token配列の長さ不一致はなし。

## 解釈上の注意

- trajectoryは圧縮で過去メッセージを失うため、エラー件数は保存された範囲の下限。
- 旧監査のcall-accounting式だけでは今回2 runが陽性になるが、保存タイミングの異なるtrajectory/token_logの差を排除できない。これを旧summary呼び出しバグの確証には使わない。
- agent.logのTraceback文字列にはタスク中のテスト出力が大量に含まれる。8319個の文字列一致を実験基盤の例外件数として扱わない。
- 最終親ログはablation d07/10k SS-partialの90/90で終わり、続く評価や全体完了の行は未確認。この環境で見えるログだけから現在のホストプロセス稼働状態は確定できない。

## 優先する対応

1. summaryの思考前置きを除き、履歴情報であることと元タスクを続行することを明示する修正を検証する。
2. timeoutの集中原因を調査し、1500秒上限による打ち切りを実験上どう扱うか決める。条件間比較に影響するため、単に全件を再実行するだけでは解決しない。
3. scikit-learn-14710の評価環境を調査し、8件を評価し直す。

## 証拠ファイル

- summary_marker_events.csv: 42イベントのtrajectoryパスと0始まりmessage index。
- agent_timeouts.csv: 152件の条件、run key、終了状態、時間。
- audited_runs.csv: 645件の監査対象。
- counts.json: 条件別集計。log_tracebacksは文字列一致数であり障害数ではない。

代表例: `ICLR_results/swebench/ablation/qwen35b/d03__b10k__ss-partial/django__django-11299/structured-summarize-partial/run_3/trajectory.json` のmessages[2]にsummary、messages[3]に再要約応答のFormatError。

コード参照: memory.py:73, memory.py:283, memory.py:300; scripts/run_experiment.py:204, scripts/run_experiment.py:282; scripts/bench_adapters/swe_bench.py:193。
評価timeoutの親ログ行: 915, 982, 1019, 1073, 1118, 1421, 1520, 1557。
