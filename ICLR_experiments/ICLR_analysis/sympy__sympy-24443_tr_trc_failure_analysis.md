# sympy__sympy-24443: TR / TRC の失敗記録の検証

対象は `ICLR_experiments/swebench/main/qwen35b/d05__b15k__tr` と `di__b15k__trc` の各3 run。

結論: 両policyのrun 1/2はresolved=Falseだが、対応する評価レポートが欠落しており、4件をそのまま「圧縮で解けなかった例」とは扱えない。全6 runがパッチを提出済み。TR run 2には独立に再現できる符号バグがある。一方、成功ラベルのTRC run 3も不正な写像を受け入れるバグを持つ。

## タスク

`homomorphism(D3, D3, D3.generators, D3.generators)` が誤ってValueErrorになる問題。群の関係式を像へ変換する `_check_homomorphism._image()` が、逆元の生成元を元の生成元へ対応付けられない。

## 保存記録と実際の進行

| Policy/run | step数 | 圧縮記録step | 保存resolved | ログ上の経過 |
|---|---:|---|---|---|
| TR r1 | 28 | 26 | False・評価欠落 | 17修正 → 18でD3成功 → 19/24追加例成功 → 28提出 |
| TR r2 | 41 | 26 | False・評価欠落 | 17で符号反転を追加 → 19で重複while修正 → 21でD3成功 → 37追加確認 → 41提出 |
| TR r3 | 37 | 22,29 | True・評価サマリーあり | 29修正 → 31で複数の正例成功 → 37提出 |
| TRC r1 | 41 | 22 | False・評価欠落 | 23修正 → 24でD3成功 → 36で既存テスト3関数を直接実行し成功 → 41提出 |
| TRC r2 | 32 | 19 | False・評価欠落 | 22修正 → 23でD3成功 → 26追加例成功 → 29既存テスト1関数実行 → 30写像の性質確認 → 32提出 |
| TRC r3 | 24 | 17 | True・評価サマリーあり | 16修正 → 17でD3成功 → 18追加正例成功 → 24提出 |

step数は保存されたn_calls。TRCは全3 runで `trc_truncation_fallback_events=1`。tool-result clearだけでは目標まで圧縮できずtruncateへフォールバックした記録があるため、純粋なtool-output削除だけの条件とは解釈しない。

## TR run 2: 符号を二重に処理するバグ

`power = r_arr[j][1]` はすでに符号付き指数を持つ。逆元に対応する正方向の生成元を見つけた後で `power = -power` まで行うと、例えば本来 `image(g)**(-1)` とする項を `image(g)**(+1)` に変えてしまう。

この行はstep 17で導入、19の構文修正でも残り、最初の圧縮記録step 26より前に存在する。圧縮によって初めて壊れたという経過ではない。

D3の当該逆元は位数2の反射なので、逆元と元の要素が等しく、この符号バグが元の再現例では露呈しない。今回の追加診断では `AbelianGroup(3,3)`（C3×C3）の恒等写像がValueErrorで拒否された。正しい実装、TR r1/r3、TRC r1/r2はこの例を受け入れる。

TR r2のstep 24は「不正写像」のつもりで正しい写像（回転を単位元へ、反射を反射へ写すもの）を使い、ERRORとAll tests passedを同時に表示していた。その後step 33で生成元を交換する別の不正写像を拒否することは確認したが、位数3の逆元を含むケースは検証していなかった。

これは提出パッチの不具合を示す診断であり、欠落している当時の評価で落ちたテストやFalseの直接原因を確定するものではない。

## TR r1 / TRC r1・r2: 失敗理由は保存情報から確定できない

3件の提出パッチは完全に同一。逆元 `r[i]**-1` を使って生成元を探し、元の符号付きpowerを保持している。評価成功サマリーのあるTR r3は、この部分を `.inverse()` と書いた同等の修正。

3件ともログ内で元の再現例を通過し、今回の局所診断でもD3の恒等写像・C3×C3の恒等写像・不正D3写像の拒否を確認した。これらの範囲では修正失敗を再現できない。

既存の `ICLR_experiments/issue/qwen_main_20260910/evaluation_classification.csv` も、4件すべてを `legacy_evaluation_reports_missing` と分類している。run 1/2は2026年3〜4月、run 3は8月の記録。古いFalseラベルだけからpolicyによる修正能力の差を主張できない。元ラベルは変更していない。

## TRC r3: 成功ラベルでもチェックを実質的に無効化

`r_arr[j][0]` はSymbol、一方 `gens` はFreeGroupElementの列。このパッチはSymbolをそのままgens内で検索し、見つからない場合もSymbolをsにする。Permutationをキーとするimagesにも一致しないため、wに像を掛けずidentityのまま関係式を通過させる。

今回の診断では、D3の回転生成元（位数3）と反射生成元（位数2）の像を交換する不正な写像も受け入れた。正しいチェックはこれを拒否する。元の正例が通るだけでは、チェック機能を保っていることを保証しない。

キャッシュされたSWE-benchの追加テストは、D3の恒等写像を作成して `T.is_isomorphism()` を確認する正例。TRC r3の保存評価は成功サマリーのみで個別テストログはなく、完全な評価再実行は今回行っていない。

## 局所診断の結果と限界

SWE-benchキャッシュのbase_commitは `809c53c077485ca48a206cee78340389cb83b7f1`。そのgold diffから変更前のチェック関数を復元し、保存された各提出パッチを当該関数へ適用した。実行環境はローカルのSymPy 1.12で、モジュールのチェック関数をプロセス内で差し替えて検証。インストール済みファイルや元の実験データは変更していない。元のコンテナ全体でのSWE-bench再評価ではない。

| 実装 | D3恒等写像・is_isomorphism | C3×C3恒等写像 | 不正D3写像を拒否 |
|---|---|---|---|
| 元のチェック関数 | ValueError | ValueError | はい |
| gold相当のSymPy 1.12実装 | 成功 | 成功 | はい |
| TR r1 | 成功 | 成功 | はい |
| TR r2 | 成功 | **ValueError** | はい |
| TR r3 | 成功 | 成功 | はい |
| TRC r1 | 成功 | 成功 | はい |
| TRC r2 | 成功 | 成功 | はい |
| TRC r3 | 成功 | 成功 | **いいえ** |

局所診断の入力関数・結果は [diagnostics.json](sympy__sympy-24443_tr_trc_diagnostics.json)。

## 主要ログ

- [d05__b15k__tr/run_1 step 17](../swebench/main/qwen35b/d05__b15k__tr/sympy__sympy-24443/truncation/run_1/agent.log#L1493)
- [d05__b15k__tr/run_2 step 17](../swebench/main/qwen35b/d05__b15k__tr/sympy__sympy-24443/truncation/run_2/agent.log#L1185)
- [d05__b15k__tr/run_3 step 29](../swebench/main/qwen35b/d05__b15k__tr/sympy__sympy-24443/truncation/run_3/agent.log#L2252)
- [di__b15k__trc/run_1 step 36](../swebench/main/qwen35b/di__b15k__trc/sympy__sympy-24443/tool-result-clear/run_1/agent.log#L2299)
- [di__b15k__trc/run_2 step 30](../swebench/main/qwen35b/di__b15k__trc/sympy__sympy-24443/tool-result-clear/run_2/agent.log#L2310)
- [di__b15k__trc/run_3 step 16](../swebench/main/qwen35b/di__b15k__trc/sympy__sympy-24443/tool-result-clear/run_3/agent.log#L1630)
