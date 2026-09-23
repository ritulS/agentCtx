# Task C analysis: FC succeeds; many compression policies fail

Cell: Qwen3.5-35B-A3B, `main` section, depth 0.5. Compression policies at token budget 15k; FC and oTRC at unlimited budget.

Failure cause in parentheses after ✗: 
- **S** = step limit (125 steps)
- **T** = time limit (1500 s wall-clock timeout)
- **W** = submitted a wrong answer (includes submissions with an empty patch).

## scikit-learn__scikit-learn-26194

> Thresholds can exceed 1 in `roc_curve` while providing probability estimate

| Policy | Run 1 | Run 2 | Run 3 | Mean steps | Resolved |
|---|---|---|---|---|---|
| FC | 44 ✗ (W) | 53 ✓ | 53 ✓ | 50 | 2/3 |
| oTRC | 95 ✗ (W) | 78 ✗ (W) | 71 ✗ (W) | 81.3 | 0/3 |
| oTRC-TR | 55 ✗ (W) | 76 ✗ (W) | 47 ✗ (W) | 59.3 | 0/3 |
| oTRC-SU-partial | 100 ✗ (W) | 37 ✗ (W) | 125 ✗ (S) | 87.3 | 0/3 |
| oTRC-SS-partial | 49 ✓ | 80 ✗ (W) | 66 ✗ (W) | 65 | 1/3 |
| TR | 34 ✗ (W) | 52 ✗ (W) | 68 ✗ (W) | 51.3 | 0/3 |
| TRC | 54 ✗ (W) | 51 ✗ (W) | 78 ✗ (W) | 61 | 0/3 |
| SU (su-full) | 21 ✗ (W) | 103 ✓ | 45 ✗ (W) | 56.3 | 1/3 |
| SU-partial | 55 ✗ (W) | 48 ✗ (W) | 57 ✗ (W) | 53.3 | 0/3 |
| SS | 78 ✗ (W) | 56 ✗ (W) | 40 ✗ (W) | 58 | 0/3 |
| SS-partial | 68 ✗ (W) | 27 ✗ (W) | 28 ✗ (W) | 41 | 0/3 |
| TRC-SU | 64 ✗ (W) | 55 ✗ (W) | 42 ✗ (W) | 53.7 | 0/3 |
| TRC-SS | 32 ✗ (W) | 42 ✗ (W) | 43 ✓ | 39 | 1/3 |

## sympy__sympy-17318

> sqrtdenest raises IndexError

| Policy | Run 1 | Run 2 | Run 3 | Mean steps | Resolved |
|---|---|---|---|---|---|
| FC | 59 ✓ | 38 ✗ (W) | 73 ✓ | 56.7 | 2/3 |
| oTRC | 27 ✗ (W) | 44 ✗ (W) | 83 ✗ (W) | 51.3 | 0/3 |
| oTRC-TR | 125 ✗ (S) | 71 ✗ (W) | 88 ✗ (T) | 94.7 | 0/3 |
| oTRC-SU-partial | 40 ✗ (W) | 41 ✗ (W) | 67 ✗ (W) | 49.3 | 0/3 |
| oTRC-SS-partial | 57 ✗ (W) | 58 ✗ (W) | 59 ✗ (W) | 58 | 0/3 |
| TR | 68 ✗ (W) | 100 ✗ (T) | 33 ✗ (W) | 67 | 0/3 |
| TRC | 46 ✗ (W) | 56 ✗ (W) | 31 ✗ (W) | 44.3 | 0/3 |
| SU (su-full) | 116 ✗ (W) | 34 ✗ (W) | 99 ✗ (W) | 83 | 0/3 |
| SU-partial | 24 ✗ (W) | 65 ✗ (W) | 48 ✗ (W) | 45.7 | 0/3 |
| SS | 71 ✗ (W) | 49 ✗ (W) | 78 ✗ (W) | 66 | 0/3 |
| SS-partial | 34 ✗ (W) | 125 ✗ (S) | 47 ✗ (W) | 68.7 | 0/3 |
| TRC-SU | 38 ✗ (W) | 82 ✗ (W) | 70 ✗ (W) | 63.3 | 0/3 |
| TRC-SS | 87 ✗ (W) | 125 ✗ (S) | 48 ✗ (W) | 86.7 | 0/3 |

## scikit-learn__scikit-learn-9288

> KMeans gives slightly different result for n_jobs=1 vs. n_jobs > 1

| Policy | Run 1 | Run 2 | Run 3 | Mean steps | Resolved |
|---|---|---|---|---|---|
| FC | 62 ✓ | 47 ✓ | 74 ✓ | 61 | 3/3 |
| oTRC | 76 ✓ | 95 ✓ | 123 ✓ | 98 | 3/3 |
| oTRC-TR | 125 ✗ (S) | 121 ✓ | 125 ✗ (S) | 123.7 | 1/3 |
| oTRC-SU-partial | 125 ✗ (S) | 86 ✓ | 85 ✓ | 98.7 | 2/3 |
| oTRC-SS-partial | 114 ✗ (T) | 125 ✗ (S) | 66 ✓ | 101.7 | 1/3 |
| TR | 107 ✗ (T) | 125 ✗ (S) | 125 ✗ (S) | 119 | 0/3 |
| TRC | 122 ✓ | 125 ✗ (S) | 65 ✓ | 104 | 2/3 |
| SU (su-full) | 125 ✗ (S) | 125 ✗ (S) | 125 ✗ (S) | 125 | 0/3 |
| SU-partial | 125 ✗ (S) | 125 ✗ (S) | 125 ✗ (S) | 125 | 0/3 |
| SS | 125 ✗ (S) | 92 ✓ | 125 ✗ (S) | 114 | 1/3 |
| SS-partial | 56 ✓ | 125 ✗ (S) | 125 ✗ (S) | 102 | 1/3 |
| TRC-SU | 56 ✓ | 125 ✗ (S) | 125 ✗ (S) | 102 | 1/3 |
| TRC-SS | 85 ✓ | 125 ✗ (S) | 125 ✗ (S) | 111.7 | 1/3 |

## scikit-learn__scikit-learn-10908

> CountVectorizer's get_feature_names raise not NotFittedError when the vocabulary parameter is provided

| Policy | Run 1 | Run 2 | Run 3 | Mean steps | Resolved |
|---|---|---|---|---|---|
| FC | 109 ✓ | 63 ✓ | 59 ✗ (T) | 77 | 2/3 |
| oTRC | 125 ✗ (S) | 125 ✗ (S) | 125 ✗ (S) | 125 | 0/3 |
| oTRC-TR | 125 ✗ (S) | 70 ✗ (W) | 76 ✓ | 90.3 | 1/3 |
| oTRC-SU-partial | 67 ✓ | 105 ✓ | 47 ✓ | 73 | 3/3 |
| oTRC-SS-partial | 62 ✓ | 67 ✓ | 51 ✗ (T) | 60 | 2/3 |
| TR | 125 ✗ (S) | 44 ✓ | 91 ✗ (T) | 86.7 | 1/3 |
| TRC | 112 ✓ | 52 ✓ | 86 ✓ | 83.3 | 3/3 |
| SU (su-full) | 74 ✓ | 125 ✗ (S) | 43 ✓ | 80.7 | 2/3 |
| SU-partial | 50 ✓ | 36 ✗ (W) | 125 ✗ (S) | 70.3 | 1/3 |
| SS | 70 ✓ | 102 ✗ (T) | 96 ✗ (T) | 89.3 | 1/3 |
| SS-partial | 58 ✓ | 105 ✗ (T) | 83 ✗ (T) | 82 | 1/3 |
| TRC-SU | 84 ✗ (W) | 117 ✗ (T) | 89 ✓ | 96.7 | 1/3 |
| TRC-SS | 116 ✓ | 125 ✗ (S) | 123 ✗ (W) | 121.3 | 1/3 |

## django__django-11299

> CheckConstraint with OR operator generates incorrect SQL on SQLite and Oracle.

| Policy | Run 1 | Run 2 | Run 3 | Mean steps | Resolved |
|---|---|---|---|---|---|
| FC | 60 ✗ (W) | 70 ✓ | 88 ✓ | 72.7 | 2/3 |
| oTRC | 125 ✗ (S) | 104 ✗ (T) | 106 ✓ | 111.7 | 1/3 |
| oTRC-TR | 96 ✓ | 125 ✗ (S) | 125 ✗ (S) | 115.3 | 1/3 |
| oTRC-SU-partial | 73 ✓ | 83 ✓ | 125 ✗ (S) | 93.7 | 2/3 |
| oTRC-SS-partial | 125 ✗ (S) | 105 ✓ | 125 ✗ (S) | 118.3 | 1/3 |
| TR | 125 ✗ (S) | 57 ✓ | 125 ✗ (S) | 102.3 | 1/3 |
| TRC | 46 ✓ | 85 ✓ | 125 ✗ (S) | 85.3 | 2/3 |
| SU (su-full) | 69 ✓ | 125 ✗ (S) | 125 ✗ (S) | 106.3 | 1/3 |
| SU-partial | 125 ✗ (S) | 57 ✓ | 125 ✗ (S) | 102.3 | 1/3 |
| SS | 125 ✗ (S) | 78 ✓ | 117 ✓ | 106.7 | 2/3 |
| SS-partial | 60 ✓ | 107 ✓ | 125 ✗ (S) | 97.3 | 2/3 |
| TRC-SU | 61 ✓ | 71 ✓ | 73 ✓ | 68.3 | 3/3 |
| TRC-SS | 62 ✓ | 125 ✗ (S) | 74 ✓ | 87 | 2/3 |

## django__django-12304

> Enumeration Types are not usable in templates.

| Policy | Run 1 | Run 2 | Run 3 | Mean steps | Resolved |
|---|---|---|---|---|---|
| FC | 33 ✓ | 47 ✓ | 58 ✓ | 46 | 3/3 |
| oTRC | 95 ✗ (T) | 26 ✓ | 27 ✗ (W) | 49.3 | 1/3 |
| oTRC-TR | 125 ✗ (S) | 125 ✗ (S) | 88 ✓ | 112.7 | 1/3 |
| oTRC-SU-partial | 41 ✓ | 26 ✗ (W) | 27 ✓ | 31.3 | 2/3 |
| oTRC-SS-partial | 60 ✓ | 33 ✗ (W) | 62 ✗ (T) | 51.7 | 1/3 |
| TR | 37 ✓ | 76 ✓ | 29 ✓ | 47.3 | 3/3 |
| TRC | 25 ✗ (W) | 36 ✓ | 21 ✗ (W) | 27.3 | 1/3 |
| SU (su-full) | 56 ✓ | 30 ✓ | 40 ✓ | 42 | 3/3 |
| SU-partial | 39 ✓ | 31 ✗ (W) | 41 ✓ | 37 | 2/3 |
| SS | 26 ✓ | 39 ✓ | 66 ✗ (T) | 43.7 | 2/3 |
| SS-partial | 56 ✓ | 38 ✓ | 61 ✗ (T) | 51.7 | 2/3 |
| TRC-SU | 67 ✗ (W) | 38 ✗ (W) | 54 ✓ | 53 | 1/3 |
| TRC-SS | 37 ✓ | 45 ✗ (W) | 17 ✗ (W) | 33 | 1/3 |

## scikit-learn__scikit-learn-12682

> `SparseCoder` doesn't expose `max_iter` for `Lasso`

| Policy | Run 1 | Run 2 | Run 3 | Mean steps | Resolved |
|---|---|---|---|---|---|
| FC | 57 ✓ | 100 ✓ | 63 ✓ | 73.3 | 3/3 |
| oTRC | 76 ✓ | 110 ✓ | 83 ✓ | 89.7 | 3/3 |
| oTRC-TR | 125 ✗ (S) | 72 ✗ (W) | 67 ✓ | 88 | 1/3 |
| oTRC-SU-partial | 76 ✗ (W) | 125 ✗ (S) | 91 ✓ | 97.3 | 1/3 |
| oTRC-SS-partial | 71 ✗ (W) | 79 ✗ (T) | 56 ✓ | 68.7 | 1/3 |
| TR | 80 ✓ | 106 ✓ | 56 ✓ | 80.7 | 3/3 |
| TRC | 77 ✓ | 41 ✗ (W) | 101 ✗ (W) | 73 | 1/3 |
| SU (su-full) | 47 ✓ | 101 ✓ | 125 ✗ (S) | 91 | 2/3 |
| SU-partial | 43 ✓ | 72 ✓ | 39 ✓ | 51.3 | 3/3 |
| SS | 74 ✓ | 59 ✓ | 112 ✗ (W) | 81.7 | 2/3 |
| SS-partial | 69 ✓ | 84 ✓ | 45 ✓ | 66 | 3/3 |
| TRC-SU | 80 ✓ | 45 ✗ (W) | 63 ✗ (W) | 62.7 | 1/3 |
| TRC-SS | 125 ✗ (S) | 44 ✗ (W) | 49 ✓ | 72.7 | 1/3 |

## scikit-learn__scikit-learn-25232

> IterativeImputer has no parameter "fill_value"

| Policy | Run 1 | Run 2 | Run 3 | Mean steps | Resolved |
|---|---|---|---|---|---|
| FC | 52 ✓ | 85 ✓ | 64 ✓ | 67 | 3/3 |
| oTRC | 53 ✗ (W) | 125 ✗ (S) | 125 ✗ (S) | 101 | 0/3 |
| oTRC-TR | 119 ✗ (T) | 68 ✓ | 125 ✗ (S) | 104 | 1/3 |
| oTRC-SU-partial | 97 ✗ (W) | 114 ✗ (W) | 125 ✗ (S) | 112 | 0/3 |
| oTRC-SS-partial | 91 ✗ (W) | 96 ✗ (T) | 81 ✗ (W) | 89.3 | 0/3 |
| TR | 97 ✓ | 51 ✗ (W) | 72 ✓ | 73.3 | 2/3 |
| TRC | 123 ✓ | 71 ✓ | 84 ✓ | 92.7 | 3/3 |
| SU (su-full) | 112 ✗ (W) | 125 ✗ (S) | 125 ✗ (S) | 120.7 | 0/3 |
| SU-partial | 65 ✓ | 56 ✗ (W) | 71 ✓ | 64 | 2/3 |
| SS | 59 ✓ | 77 ✗ (W) | 87 ✓ | 74.3 | 2/3 |
| SS-partial | 45 ✗ (W) | 94 ✓ | 82 ✗ (W) | 73.7 | 1/3 |
| TRC-SU | 121 ✓ | 55 ✓ | 62 ✓ | 79.3 | 3/3 |
| TRC-SS | 119 ✓ | 70 ✓ | 49 ✓ | 79.3 | 3/3 |

## sympy__sympy-14711

> vector add 0 error

| Policy | Run 1 | Run 2 | Run 3 | Mean steps | Resolved |
|---|---|---|---|---|---|
| FC | 66 ✗ (T) | 78 ✓ | 86 ✓ | 76.7 | 2/3 |
| oTRC | 114 ✗ (W) | 73 ✗ (W) | 82 ✓ | 89.7 | 1/3 |
| oTRC-TR | 49 ✓ | 125 ✗ (S) | 125 ✗ (S) | 99.7 | 1/3 |
| oTRC-SU-partial | 48 ✓ | 114 ✗ (W) | 93 ✓ | 85 | 2/3 |
| oTRC-SS-partial | 67 ✓ | 112 ✓ | 61 ✓ | 80 | 3/3 |
| TR | 125 ✗ (S) | 93 ✓ | 106 ✓ | 108 | 2/3 |
| TRC | 54 ✓ | 125 ✗ (S) | 102 ✗ (W) | 93.7 | 1/3 |
| SU (su-full) | 125 ✗ (S) | 121 ✗ (W) | 84 ✓ | 110 | 1/3 |
| SU-partial | 94 ✓ | 81 ✓ | 79 ✓ | 84.7 | 3/3 |
| SS | 83 ✓ | 114 ✗ (T) | 69 ✓ | 88.7 | 2/3 |
| SS-partial | 120 ✗ (W) | 45 ✓ | 125 ✗ (S) | 96.7 | 1/3 |
| TRC-SU | 113 ✓ | 125 ✗ (S) | 125 ✗ (S) | 121 | 1/3 |
| TRC-SS | 47 ✓ | 61 ✓ | 125 ✗ (S) | 77.7 | 2/3 |
