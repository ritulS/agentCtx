# Task A analysis: FC fails; many compression policies succeed

Cell: Qwen3.5-35B-A3B, `main` section, depth 0.5. Compression policies at token budget 15k; FC and oTRC at unlimited budget.

Failure cause in parentheses after ✗: 
- **S** = step limit (125 steps)
- **T** = time limit (1500 s wall-clock timeout)
- **W** = submitted a wrong answer (includes submissions with an empty patch).

## django__django-13012

> Constant expressions of an ExpressionWrapper object are incorrectly placed at the GROUP BY clause

| Policy | Run 1 | Run 2 | Run 3 | Mean steps | Resolved |
|---|---|---|---|---|---|
| FC | 82 ✗ (W) | 44 ✗ (W) | 47 ✓ | 57.7 | 1/3 |
| oTRC | 52 ✓ | 119 ✓ | 59 ✓ | 76.7 | 3/3 |
| oTRC-TR | 70 ✓ | 45 ✓ | 54 ✓ | 56.3 | 3/3 |
| oTRC-SU-partial | 54 ✓ | 52 ✓ | 65 ✓ | 57 | 3/3 |
| oTRC-SS-partial | 64 ✓ | 59 ✗ (W) | 56 ✓ | 59.7 | 2/3 |
| TR | 125 ✗ (S) | 125 ✗ (S) | 125 ✗ (S) | 125 | 0/3 |
| TRC | 40 ✗ (W) | 43 ✗ (W) | 73 ✓ | 52 | 1/3 |
| SU (su-full) | 39 ✗ (W) | 111 ✓ | 38 ✓ | 62.7 | 2/3 |
| SU-partial | 54 ✓ | 32 ✓ | 30 ✓ | 38.7 | 3/3 |
| SS | 56 ✓ | 53 ✓ | 50 ✓ | 53 | 3/3 |
| SS-partial | 39 ✓ | 103 ✓ | 69 ✓ | 70.3 | 3/3 |
| TRC-SU | 70 ✓ | 52 ✓ | 79 ✓ | 67 | 3/3 |
| TRC-SS | 47 ✓ | 69 ✓ | 69 ✗ (W) | 61.7 | 2/3 |

## scikit-learn__scikit-learn-13328

> TypeError when supplying a boolean X to HuberRegressor fit

| Policy | Run 1 | Run 2 | Run 3 | Mean steps | Resolved |
|---|---|---|---|---|---|
| FC | 51 ✗ (W) | 58 ✗ (W) | 29 ✓ | 46 | 1/3 |
| oTRC | 56 ✓ | 58 ✓ | 109 ✓ | 74.3 | 3/3 |
| oTRC-TR | 83 ✓ | 54 ✓ | 88 ✓ | 75 | 3/3 |
| oTRC-SU-partial | 44 ✓ | 44 ✓ | 61 ✓ | 49.7 | 3/3 |
| oTRC-SS-partial | 101 ✓ | 64 ✓ | 85 ✓ | 83.3 | 3/3 |
| TR | 125 ✗ (S) | 125 ✗ (S) | 125 ✗ (S) | 125 | 0/3 |
| TRC | 68 ✗ (W) | 80 ✗ (W) | 58 ✓ | 68.7 | 1/3 |
| SU (su-full) | 125 ✗ (S) | 125 ✗ (S) | 47 ✓ | 99 | 1/3 |
| SU-partial | 31 ✓ | 65 ✓ | 73 ✓ | 56.3 | 3/3 |
| SS | 91 ✓ | 93 ✓ | 56 ✓ | 80 | 3/3 |
| SS-partial | 53 ✓ | 75 ✓ | 70 ✓ | 66 | 3/3 |
| TRC-SU | 35 ✓ | 45 ✓ | 57 ✓ | 45.7 | 3/3 |
| TRC-SS | 57 ✓ | 74 ✓ | 44 ✓ | 58.3 | 3/3 |

## scikit-learn__scikit-learn-14496

> [BUG] Optics float min_samples NN instantiation

| Policy | Run 1 | Run 2 | Run 3 | Mean steps | Resolved |
|---|---|---|---|---|---|
| FC | 34 ✗ (W) | 15 ✗ (W) | 30 ✓ | 26.3 | 1/3 |
| oTRC | 32 ✓ | 48 ✓ | 73 ✓ | 51 | 3/3 |
| oTRC-TR | 30 ✓ | 31 ✓ | 24 ✓ | 28.3 | 3/3 |
| oTRC-SU-partial | 67 ✓ | 40 ✓ | 29 ✓ | 45.3 | 3/3 |
| oTRC-SS-partial | 26 ✓ | 45 ✓ | 32 ✓ | 34.3 | 3/3 |
| TR | 28 ✗ (W) | 35 ✗ (W) | 35 ✓ | 32.7 | 1/3 |
| TRC | 81 ✗ (W) | 59 ✗ (W) | 26 ✓ | 55.3 | 1/3 |
| SU (su-full) | 41 ✗ (W) | 26 ✗ (W) | 33 ✓ | 33.3 | 1/3 |
| SU-partial | 14 ✓ | 35 ✓ | 27 ✓ | 25.3 | 3/3 |
| SS | 52 ✓ | 28 ✗ (W) | 24 ✓ | 34.7 | 2/3 |
| SS-partial | 37 ✓ | 24 ✓ | 31 ✓ | 30.7 | 3/3 |
| TRC-SU | 33 ✓ | 32 ✓ | 44 ✓ | 36.3 | 3/3 |
| TRC-SS | 37 ✓ | 48 ✓ | 107 ✓ | 64 | 3/3 |

## sympy__sympy-24443

> `_check_homomorphism` is broken on PermutationGroups

| Policy | Run 1 | Run 2 | Run 3 | Mean steps | Resolved |
|---|---|---|---|---|---|
| FC | 63 ✗ (W) | 40 ✗ (W) | 67 ✓ | 56.7 | 1/3 |
| oTRC | 35 ✓ | 29 ✓ | 36 ✓ | 33.3 | 3/3 |
| oTRC-TR | 125 ✗ (S) | 38 ✓ | 29 ✓ | 64 | 2/3 |
| oTRC-SU-partial | 19 ✓ | 55 ✓ | 28 ✓ | 34 | 3/3 |
| oTRC-SS-partial | 23 ✓ | 24 ✓ | 92 ✗ (T) | 46.3 | 2/3 |
| TR | 28 ✗ (W) | 41 ✗ (W) | 37 ✓ | 35.3 | 1/3 |
| TRC | 41 ✗ (W) | 32 ✗ (W) | 24 ✓ | 32.3 | 1/3 |
| SU (su-full) | 77 ✓ | 39 ✓ | 29 ✓ | 48.3 | 3/3 |
| SU-partial | 47 ✗ (T) | 30 ✓ | 29 ✓ | 35.3 | 2/3 |
| SS | 18 ✗ (T) | 30 ✗ (W) | 29 ✓ | 25.7 | 1/3 |
| SS-partial | 30 ✓ | 32 ✓ | 26 ✓ | 29.3 | 3/3 |
| TRC-SU | 35 ✓ | 53 ✓ | 32 ✓ | 40 | 3/3 |
| TRC-SS | 26 ✓ | 25 ✓ | 36 ✓ | 29 | 3/3 |

## scikit-learn__scikit-learn-15100

> strip_accents_unicode fails to strip accents from strings that are already in NFKD form

| Policy | Run 1 | Run 2 | Run 3 | Mean steps | Resolved |
|---|---|---|---|---|---|
| FC | 22 ✗ (W) | 18 ✗ (W) | 25 ✓ | 21.7 | 1/3 |
| oTRC | 26 ✓ | 30 ✓ | 32 ✓ | 29.3 | 3/3 |
| oTRC-TR | 23 ✓ | 35 ✓ | 28 ✓ | 28.7 | 3/3 |
| oTRC-SU-partial | 41 ✓ | 28 ✓ | 20 ✓ | 29.7 | 3/3 |
| oTRC-SS-partial | 27 ✓ | 25 ✓ | 37 ✓ | 29.7 | 3/3 |
| TR | 20 ✗ (W) | 20 ✗ (W) | 19 ✓ | 19.7 | 1/3 |
| TRC | 24 ✗ (W) | 23 ✗ (W) | 20 ✓ | 22.3 | 1/3 |
| SU (su-full) | 24 ✗ (W) | 25 ✗ (W) | 24 ✓ | 24.3 | 1/3 |
| SU-partial | 28 ✓ | 31 ✓ | 20 ✓ | 26.3 | 3/3 |
| SS | 20 ✗ (W) | 19 ✗ (W) | 20 ✓ | 19.7 | 1/3 |
| SS-partial | 20 ✓ | 16 ✓ | 23 ✓ | 19.7 | 3/3 |
| TRC-SU | 19 ✓ | 24 ✓ | 24 ✓ | 22.3 | 3/3 |
| TRC-SS | 19 ✓ | 23 ✓ | 25 ✓ | 22.3 | 3/3 |

## scikit-learn__scikit-learn-26323

> `ColumnTransformer.set_output` ignores the `remainder` if it's an estimator

| Policy | Run 1 | Run 2 | Run 3 | Mean steps | Resolved |
|---|---|---|---|---|---|
| FC | 94 ✗ (T) | 54 ✗ (W) | 34 ✓ | 60.7 | 1/3 |
| oTRC | 92 ✓ | 90 ✓ | 103 ✓ | 95 | 3/3 |
| oTRC-TR | 53 ✓ | 82 ✓ | 117 ✗ (T) | 84 | 2/3 |
| oTRC-SU-partial | 125 ✗ (S) | 78 ✓ | 61 ✓ | 88 | 2/3 |
| oTRC-SS-partial | 75 ✓ | 69 ✗ (W) | 64 ✓ | 69.3 | 2/3 |
| TR | 120 ✗ (W) | 57 ✗ (W) | 52 ✓ | 76.3 | 1/3 |
| TRC | 53 ✗ (W) | 99 ✗ (W) | 69 ✓ | 73.7 | 1/3 |
| SU (su-full) | 93 ✓ | 83 ✓ | 68 ✓ | 81.3 | 3/3 |
| SU-partial | 96 ✓ | 121 ✗ (T) | 121 ✗ (T) | 112.7 | 1/3 |
| SS | 94 ✗ (T) | 119 ✗ (T) | 61 ✓ | 91.3 | 1/3 |
| SS-partial | 85 ✓ | 41 ✓ | 100 ✓ | 75.3 | 3/3 |
| TRC-SU | 66 ✓ | 61 ✓ | 45 ✓ | 57.3 | 3/3 |
| TRC-SS | 41 ✓ | 65 ✗ (T) | 53 ✓ | 53 | 2/3 |

## sympy__sympy-19637

> kernS: 'kern' referenced before assignment

| Policy | Run 1 | Run 2 | Run 3 | Mean steps | Resolved |
|---|---|---|---|---|---|
| FC | 29 ✗ (W) | 23 ✗ (W) | 31 ✓ | 27.7 | 1/3 |
| oTRC | 40 ✓ | 30 ✓ | 19 ✓ | 29.7 | 3/3 |
| oTRC-TR | 28 ✓ | 41 ✓ | 35 ✓ | 34.7 | 3/3 |
| oTRC-SU-partial | 21 ✓ | 21 ✓ | 18 ✓ | 20 | 3/3 |
| oTRC-SS-partial | 31 ✓ | 32 ✓ | 31 ✓ | 31.3 | 3/3 |
| TR | 27 ✗ (W) | 25 ✗ (W) | 38 ✓ | 30 | 1/3 |
| TRC | 31 ✗ (W) | 27 ✗ (W) | 19 ✓ | 25.7 | 1/3 |
| SU (su-full) | 18 ✗ (W) | 27 ✗ (W) | 18 ✓ | 21 | 1/3 |
| SU-partial | 19 ✓ | 19 ✓ | 35 ✓ | 24.3 | 3/3 |
| SS | 33 ✗ (W) | 26 ✗ (W) | 27 ✓ | 28.7 | 1/3 |
| SS-partial | 23 ✓ | 27 ✓ | 27 ✓ | 25.7 | 3/3 |
| TRC-SU | 31 ✓ | 25 ✓ | 31 ✓ | 29 | 3/3 |
| TRC-SS | 31 ✓ | 16 ✓ | 33 ✓ | 26.7 | 3/3 |

## scikit-learn__scikit-learn-14053

> IndexError: list index out of range in export_text when the tree only has one feature

| Policy | Run 1 | Run 2 | Run 3 | Mean steps | Resolved |
|---|---|---|---|---|---|
| FC | 44 ✗ (T) | 57 ✓ | 52 ✗ (T) | 51 | 1/3 |
| oTRC | 86 ✓ | 64 ✓ | 114 ✓ | 88 | 3/3 |
| oTRC-TR | 62 ✗ (W) | 125 ✗ (S) | 104 ✓ | 97 | 1/3 |
| oTRC-SU-partial | 64 ✗ (T) | 125 ✗ (S) | 67 ✓ | 85.3 | 1/3 |
| oTRC-SS-partial | 105 ✓ | 63 ✓ | 40 ✓ | 69.3 | 3/3 |
| TR | 54 ✓ | 76 ✗ (W) | 41 ✓ | 57 | 2/3 |
| TRC | 41 ✓ | 99 ✓ | 72 ✗ (W) | 70.7 | 2/3 |
| SU (su-full) | 112 ✗ (T) | 110 ✗ (T) | 52 ✓ | 91.3 | 1/3 |
| SU-partial | 59 ✓ | 59 ✓ | 54 ✓ | 57.3 | 3/3 |
| SS | 117 ✗ (T) | 79 ✓ | 125 ✗ (S) | 107 | 1/3 |
| SS-partial | 57 ✓ | 125 ✗ (S) | 66 ✓ | 82.7 | 2/3 |
| TRC-SU | 66 ✗ (W) | 61 ✓ | 50 ✓ | 59 | 2/3 |
| TRC-SS | 57 ✓ | 46 ✗ (W) | 81 ✗ (W) | 61.3 | 1/3 |

## sympy__sympy-15017

> `len` of rank-0 arrays returns 0

| Policy | Run 1 | Run 2 | Run 3 | Mean steps | Resolved |
|---|---|---|---|---|---|
| FC | 37 ✗ (W) | 25 ✗ (W) | 49 ✓ | 37 | 1/3 |
| oTRC | 38 ✓ | 125 ✗ (S) | 44 ✓ | 69 | 2/3 |
| oTRC-TR | 41 ✓ | 32 ✓ | 57 ✓ | 43.3 | 3/3 |
| oTRC-SU-partial | 44 ✓ | 51 ✓ | 47 ✓ | 47.3 | 3/3 |
| oTRC-SS-partial | 57 ✓ | 37 ✓ | 33 ✓ | 42.3 | 3/3 |
| TR | 38 ✗ (W) | 68 ✗ (W) | 44 ✓ | 50 | 1/3 |
| TRC | 27 ✗ (W) | 35 ✗ (W) | 66 ✓ | 42.7 | 1/3 |
| SU (su-full) | 70 ✗ (W) | 31 ✗ (W) | 93 ✗ (W) | 64.7 | 0/3 |
| SU-partial | 31 ✗ (W) | 40 ✓ | 35 ✓ | 35.3 | 2/3 |
| SS | 28 ✗ (W) | 80 ✗ (W) | 81 ✓ | 63 | 1/3 |
| SS-partial | 51 ✓ | 24 ✗ (W) | 36 ✓ | 37 | 2/3 |
| TRC-SU | 72 ✓ | 35 ✓ | 36 ✓ | 47.7 | 3/3 |
| TRC-SS | 28 ✗ (W) | 22 ✗ (W) | 43 ✓ | 31 | 1/3 |
