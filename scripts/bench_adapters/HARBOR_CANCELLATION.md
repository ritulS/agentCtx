# Harbor のタイムアウト処理（2026-09-06）

以前は `asyncio.to_thread(agent.run, ...)` の待機だけがキャンセルされ、同期の
モデル呼び出し・リトライ・エージェントループが残る構造だった。

現在は `CompressionAgent` がタスクごとに独立した子プロセスを起動する。
モデル呼び出し（圧縮用の要約呼び出しも含む）は子プロセスで行い、Harbor の
コンテナ操作は専用ソケット経由で親プロセスに依頼する。

タイムアウトまたはキャンセル時には子プロセスの専用プロセスグループに
SIGKILL を送り、子プロセスの終了を確認してから CancelledError を再送出する。
Harbor の制限時間・AgentTimeoutError の判定は変更していない。正常終了時も
子プロセスを回収するため、ライブラリのバックグラウンドスレッドは残らない。
旧 `tbench.harbor_adapter` も同じ実装を参照する。

保存する追加ログ:

- `worker_process.json`: 子プロセス PID、終了コード、`reaped: true`。
- `worker.log`: 子プロセスの標準出力・標準エラー。
- `worker_checkpoint.json`: 最後に保存できた呼び出し数・トークン統計。

trajectory とチェックポイントは一時ファイルからの置換で保存し、強制終了で
既存の JSON が壊れないようにする。最終 token_log/exit_info は子プロセス終了後に
親が保存する。中断された推論や要約の未保存トークン数は含まれない。
`exit_info.json` の CancelledError は手動キャンセルも含むため、タイムアウトの
判定には Harbor の result.json の exception_info を使う。

検証コマンド（GPU・Docker・外部 API は不要、ローカルソケットが必要）:

```bash
venv-harbor/bin/python -m unittest scripts.bench_adapters.test_harbor_cancellation -v
```

通常提出、推論待機中のタイムアウトによる接続切断、コンテナ操作中のキャンセル、
他タスクへの非干渉、起動直後のキャンセル、異常終了を検証する。

実 vLLM 上の GPU 要求解放は、このテストでは未検証。インストール済み両版の
chat completions ルートにはクライアント切断によるキャンセル処理がある。
子プロセス終了でクライアント接続は閉じるが、GPU 上の処理が解放されるまでの
時間は実機の小規模試行で確認する必要がある。コンテナ内コマンドの後始末は
引き続き Harbor の環境実装が担当する。

実 vLLM の停止確認（対象サーバーを起動し、他の実験が動いていない状態で実行）:

```bash
venv-harbor/bin/python -m scripts.bench_adapters.check_vllm_cancellation glm
venv-harbor/bin/python -m scripts.bench_adapters.check_vllm_cancellation devstral
```

GLM はポート 8003、Devstral は 8002 を使用する。確認ログは
`logs/cancellation_checks/` に保存し、実験結果には追加しない。

変更は新しく起動する実験に適用される。既に動いている旧エージェントのスレッドは
この変更では停止しない。再開前に旧実験プロセスと不要な推論要求を解消し、
少数タスクで期限到達後に worker が消え、vLLM の Running が減ることを確認する。
vLLM の Running は推論要求数なので、実験の並列タスク数と常に一致するとは限らない。
