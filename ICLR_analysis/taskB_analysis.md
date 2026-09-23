# Task B analysis: FC fails; only a few compression policies succeed

Cell: Qwen3.5-35B-A3B, `main` section, depth 0.5. Compression policies at token budget 15k; FC and oTRC at unlimited budget.

Failure cause in parentheses after ✗: 
- **S** = step limit (125 steps)
- **T** = time limit (1500 s wall-clock timeout)
- **W** = submitted a wrong answer (includes submissions with an empty patch).

## django__django-13810

> MiddlewareNotUsed leaves undesired side effects when loading middleware in ASGI context

| Policy | Run 1 | Run 2 | Run 3 | Mean steps | Resolved |
|---|---|---|---|---|---|
| FC | 52 ✗ (T) | 49 ✗ (T) | 46 ✗ (T) | 49 | 0/3 |
| oTRC | 54 ✗ (W) | 59 ✓ | 95 ✗ (W) | 69.3 | 1/3 |
| oTRC-TR | 79 ✓ | 125 ✗ (S) | 44 ✗ (T) | 82.7 | 1/3 |
| oTRC-SU-partial | 125 ✗ (S) | 66 ✓ | 83 ✓ | 91.3 | 2/3 |
| oTRC-SS-partial | 24 ✓ | 50 ✗ (T) | 38 ✗ (T) | 37.3 | 1/3 |
| TR | 105 ✗ (T) | 104 ✗ (T) | 32 ✗ (T) | 80.3 | 0/3 |
| TRC | 84 ✗ (W) | 81 ✗ (T) | 24 ✓ | 63 | 1/3 |
| SU (su-full) | 71 ✗ (T) | 35 ✓ | 95 ✗ (W) | 67 | 1/3 |
| SU-partial | 48 ✓ | 64 ✓ | 73 ✓ | 61.7 | 3/3 |
| SS | 114 ✗ (W) | 86 ✗ (T) | 43 ✗ (T) | 81 | 0/3 |
| SS-partial | 64 ✓ | 87 ✗ (T) | 63 ✗ (T) | 71.3 | 1/3 |
| TRC-SU | 68 ✓ | 59 ✗ (T) | 53 ✗ (T) | 60 | 1/3 |
| TRC-SS | 57 ✗ (T) | 37 ✓ | 125 ✗ (S) | 73 | 1/3 |

## django__django-17084

> Cannot use aggregate over window functions since 4.2

| Policy | Run 1 | Run 2 | Run 3 | Mean steps | Resolved |
|---|---|---|---|---|---|
| FC | 77 ✓ | 87 ✗ (T) | 96 ✗ (T) | 86.7 | 1/3 |
| oTRC | 92 ✓ | 114 ✗ (T) | 114 ✗ (T) | 106.7 | 1/3 |
| oTRC-TR | 103 ✓ | 125 ✗ (S) | 93 ✗ (T) | 107 | 1/3 |
| oTRC-SU-partial | 85 ✗ (T) | 125 ✗ (S) | 125 ✗ (S) | 111.7 | 0/3 |
| oTRC-SS-partial | 70 ✗ (W) | 125 ✗ (S) | 73 ✗ (W) | 89.3 | 0/3 |
| TR | 110 ✗ (T) | 125 ✗ (S) | 117 ✗ (T) | 117.3 | 0/3 |
| TRC | 107 ✓ | 109 ✓ | 121 ✗ (T) | 112.3 | 2/3 |
| SU (su-full) | 122 ✗ (T) | 125 ✗ (S) | 125 ✗ (S) | 124 | 0/3 |
| SU-partial | 57 ✓ | 47 ✓ | 122 ✗ (T) | 75.3 | 2/3 |
| SS | 66 ✓ | 107 ✗ (T) | 120 ✗ (T) | 97.7 | 1/3 |
| SS-partial | 106 ✗ (W) | 80 ✗ (T) | 89 ✗ (T) | 91.7 | 0/3 |
| TRC-SU | 107 ✗ (T) | 89 ✓ | 125 ✗ (S) | 107 | 1/3 |
| TRC-SS | 50 ✗ (T) | 125 ✗ (S) | 125 ✗ (S) | 100 | 0/3 |

## scikit-learn__scikit-learn-11310

> Retrieving time to refit the estimator in BaseSearchCV

| Policy | Run 1 | Run 2 | Run 3 | Mean steps | Resolved |
|---|---|---|---|---|---|
| FC | 84 ✓ | 53 ✗ (W) | 71 ✗ (W) | 69.3 | 1/3 |
| oTRC | 125 ✗ (S) | 86 ✗ (W) | 46 ✓ | 85.7 | 1/3 |
| oTRC-TR | 60 ✓ | 62 ✗ (W) | 85 ✓ | 69 | 2/3 |
| oTRC-SU-partial | 82 ✗ (W) | 125 ✗ (S) | 63 ✓ | 90 | 1/3 |
| oTRC-SS-partial | 81 ✗ (W) | 125 ✗ (S) | 53 ✓ | 86.3 | 1/3 |
| TR | 72 ✓ | 125 ✗ (S) | 67 ✗ (W) | 88 | 1/3 |
| TRC | 52 ✓ | 125 ✗ (S) | 125 ✗ (S) | 100.7 | 1/3 |
| SU (su-full) | 86 ✓ | 125 ✗ (S) | 20 ✗ (W) | 77 | 1/3 |
| SU-partial | 32 ✓ | 106 ✗ (W) | 125 ✗ (S) | 87.7 | 1/3 |
| SS | 56 ✓ | 125 ✗ (S) | 125 ✗ (S) | 102 | 1/3 |
| SS-partial | 95 ✗ (W) | 121 ✓ | 56 ✓ | 90.7 | 2/3 |
| TRC-SU | 59 ✓ | 125 ✗ (S) | 50 ✗ (W) | 78 | 1/3 |
| TRC-SS | 99 ✗ (W) | 99 ✗ (W) | 71 ✗ (W) | 89.7 | 0/3 |

## scikit-learn__scikit-learn-12973

> LassoLarsIC: unintuitive copy_X behaviour

| Policy | Run 1 | Run 2 | Run 3 | Mean steps | Resolved |
|---|---|---|---|---|---|
| FC | 32 ✗ (W) | 42 ✗ (W) | 43 ✗ (W) | 39 | 0/3 |
| oTRC | 72 ✗ (W) | 40 ✗ (W) | 58 ✓ | 56.7 | 1/3 |
| oTRC-TR | 125 ✗ (S) | 74 ✗ (W) | 68 ✓ | 89 | 1/3 |
| oTRC-SU-partial | 58 ✗ (W) | 66 ✗ (W) | 53 ✗ (W) | 59 | 0/3 |
| oTRC-SS-partial | 48 ✓ | 38 ✗ (W) | 57 ✗ (W) | 47.7 | 1/3 |
| TR | 53 ✗ (W) | 56 ✗ (W) | 88 ✗ (W) | 65.7 | 0/3 |
| TRC | 34 ✗ (W) | 45 ✗ (W) | 46 ✗ (W) | 41.7 | 0/3 |
| SU (su-full) | 50 ✗ (W) | 88 ✓ | 31 ✗ (W) | 56.3 | 1/3 |
| SU-partial | 33 ✗ (W) | 37 ✗ (W) | 33 ✗ (W) | 34.3 | 0/3 |
| SS | 48 ✓ | 125 ✗ (S) | 80 ✓ | 84.3 | 2/3 |
| SS-partial | 90 ✓ | 47 ✗ (W) | 62 ✗ (W) | 66.3 | 1/3 |
| TRC-SU | 80 ✓ | 27 ✗ (W) | 59 ✓ | 55.3 | 2/3 |
| TRC-SS | 43 ✗ (W) | 44 ✗ (W) | 55 ✓ | 47.3 | 1/3 |

## sympy__sympy-13757

> Multiplying an expression by a Poly does not evaluate when the expression is on the left side of the multiplication

| Policy | Run 1 | Run 2 | Run 3 | Mean steps | Resolved |
|---|---|---|---|---|---|
| FC | 87 ✓ | 125 ✗ (S) | 99 ✗ (T) | 103.7 | 1/3 |
| oTRC | 111 ✓ | 125 ✗ (S) | 125 ✗ (S) | 120.3 | 1/3 |
| oTRC-TR | 125 ✗ (S) | 125 ✗ (S) | 125 ✗ (S) | 125 | 0/3 |
| oTRC-SU-partial | 125 ✗ (S) | 88 ✓ | 96 ✓ | 103 | 2/3 |
| oTRC-SS-partial | 76 ✗ (T) | 63 ✗ (T) | 59 ✗ (T) | 66 | 0/3 |
| TR | 125 ✗ (S) | 125 ✗ (S) | 110 ✗ (T) | 120 | 0/3 |
| TRC | 125 ✗ (S) | 125 ✗ (S) | 125 ✗ (S) | 125 | 0/3 |
| SU (su-full) | 91 ✓ | 116 ✗ (T) | 114 ✓ | 107 | 2/3 |
| SU-partial | 103 ✓ | 125 ✗ (S) | 125 ✗ (S) | 117.7 | 1/3 |
| SS | 125 ✗ (S) | 60 ✗ (T) | 102 ✗ (T) | 95.7 | 0/3 |
| SS-partial | 125 ✗ (S) | 83 ✓ | 123 ✗ (T) | 110.3 | 1/3 |
| TRC-SU | 107 ✓ | 125 ✗ (S) | 125 ✗ (S) | 119 | 1/3 |
| TRC-SS | 87 ✗ (T) | 125 ✗ (S) | 125 ✗ (S) | 112.3 | 0/3 |

## django__django-15525

> loaddata fails on non-default database when natural keys uses foreign keys.

| Policy | Run 1 | Run 2 | Run 3 | Mean steps | Resolved |
|---|---|---|---|---|---|
| FC | 29 ✗ (T) | 114 ✗ (T) | 34 ✗ (T) | 59 | 0/3 |
| oTRC | 37 ✗ (T) | 58 ✗ (T) | 47 ✗ (T) | 47.3 | 0/3 |
| oTRC-TR | 111 ✓ | 82 ✗ (T) | 43 ✗ (W) | 78.7 | 1/3 |
| oTRC-SU-partial | 46 ✗ (W) | 63 ✓ | 38 ✗ (T) | 49 | 1/3 |
| oTRC-SS-partial | 51 ✓ | 47 ✗ (T) | 79 ✗ (T) | 59 | 1/3 |
| TR | 125 ✗ (S) | 63 ✗ (T) | 86 ✗ (T) | 91.3 | 0/3 |
| TRC | 38 ✓ | 111 ✗ (T) | 73 ✗ (T) | 74 | 1/3 |
| SU (su-full) | 72 ✗ (W) | 97 ✗ (T) | 124 ✗ (T) | 97.7 | 0/3 |
| SU-partial | 73 ✗ (T) | 53 ✗ (T) | 92 ✗ (T) | 72.7 | 0/3 |
| SS | 34 ✗ (T) | 34 ✗ (T) | 74 ✗ (T) | 47.3 | 0/3 |
| SS-partial | 49 ✓ | 58 ✗ (T) | 62 ✓ | 56.3 | 2/3 |
| TRC-SU | 125 ✗ (S) | 70 ✓ | 81 ✗ (W) | 92 | 1/3 |
| TRC-SS | 109 ✗ (T) | 70 ✗ (W) | 80 ✗ (W) | 86.3 | 0/3 |

## django__django-15930

> Case() crashes with ~Q(pk__in=[]).

| Policy | Run 1 | Run 2 | Run 3 | Mean steps | Resolved |
|---|---|---|---|---|---|
| FC | 101 ✗ (T) | 98 ✗ (T) | 79 ✓ | 92.7 | 1/3 |
| oTRC | 67 ✓ | 109 ✗ (W) | 89 ✗ (T) | 88.3 | 1/3 |
| oTRC-TR | 125 ✗ (S) | 112 ✓ | 125 ✗ (S) | 120.7 | 1/3 |
| oTRC-SU-partial | 93 ✗ (T) | 117 ✗ (T) | 92 ✗ (T) | 100.7 | 0/3 |
| oTRC-SS-partial | 113 ✗ (T) | 73 ✗ (T) | 61 ✗ (T) | 82.3 | 0/3 |
| TR | 113 ✗ (T) | 125 ✗ (S) | 85 ✗ (T) | 107.7 | 0/3 |
| TRC | 117 ✓ | 86 ✓ | 125 ✗ (S) | 109.3 | 2/3 |
| SU (su-full) | 113 ✗ (T) | 125 ✗ (S) | 125 ✗ (S) | 121 | 0/3 |
| SU-partial | 125 ✗ (S) | 125 ✗ (S) | 125 ✗ (S) | 125 | 0/3 |
| SS | 94 ✗ (T) | 59 ✗ (T) | 85 ✗ (T) | 79.3 | 0/3 |
| SS-partial | 125 ✗ (S) | 125 ✗ (S) | 110 ✗ (T) | 120 | 0/3 |
| TRC-SU | 111 ✗ (T) | 84 ✗ (W) | 122 ✗ (W) | 105.7 | 0/3 |
| TRC-SS | 75 ✓ | 115 ✗ (T) | 125 ✗ (S) | 105 | 1/3 |

## scikit-learn__scikit-learn-14983

> RepeatedKFold and RepeatedStratifiedKFold do not show correct __repr__ string

| Policy | Run 1 | Run 2 | Run 3 | Mean steps | Resolved |
|---|---|---|---|---|---|
| FC | 61 ✓ | 36 ✗ (W) | 54 ✗ (W) | 50.3 | 1/3 |
| oTRC | 50 ✗ (W) | 46 ✗ (W) | 95 ✗ (W) | 63.7 | 0/3 |
| oTRC-TR | 54 ✗ (W) | 46 ✗ (W) | 44 ✗ (W) | 48 | 0/3 |
| oTRC-SU-partial | 52 ✗ (W) | 45 ✗ (W) | 41 ✗ (W) | 46 | 0/3 |
| oTRC-SS-partial | 42 ✗ (W) | 71 ✗ (W) | 68 ✗ (W) | 60.3 | 0/3 |
| TR | 40 ✗ (W) | 75 ✓ | 52 ✗ (W) | 55.7 | 1/3 |
| TRC | 41 ✗ (W) | 39 ✗ (W) | 53 ✓ | 44.3 | 1/3 |
| SU (su-full) | 57 ✗ (W) | 57 ✗ (W) | 125 ✗ (S) | 79.7 | 0/3 |
| SU-partial | 37 ✗ (W) | 29 ✗ (W) | 30 ✗ (W) | 32 | 0/3 |
| SS | 93 ✗ (W) | 125 ✗ (S) | 120 ✗ (W) | 112.7 | 0/3 |
| SS-partial | 48 ✗ (W) | 49 ✓ | 47 ✗ (W) | 48 | 1/3 |
| TRC-SU | 76 ✗ (W) | 125 ✗ (S) | 55 ✗ (W) | 85.3 | 0/3 |
| TRC-SS | 48 ✓ | 38 ✗ (W) | 75 ✓ | 53.7 | 2/3 |

## scikit-learn__scikit-learn-25102

> Preserving dtypes for DataFrame output by transformers that do not modify the input values

| Policy | Run 1 | Run 2 | Run 3 | Mean steps | Resolved |
|---|---|---|---|---|---|
| FC | 104 ✗ (T) | 44 ✗ (T) | 56 ✗ (W) | 68 | 0/3 |
| oTRC | 73 ✗ (T) | 86 ✓ | 125 ✗ (S) | 94.7 | 1/3 |
| oTRC-TR | 118 ✓ | 73 ✓ | 47 ✗ (W) | 79.3 | 2/3 |
| oTRC-SU-partial | 65 ✗ (W) | 125 ✗ (S) | 105 ✓ | 98.3 | 1/3 |
| oTRC-SS-partial | 125 ✗ (S) | 74 ✗ (T) | 96 ✗ (T) | 98.3 | 0/3 |
| TR | 106 ✗ (T) | 115 ✓ | 125 ✗ (S) | 115.3 | 1/3 |
| TRC | 116 ✗ (W) | 125 ✗ (S) | 125 ✗ (S) | 122 | 0/3 |
| SU (su-full) | 56 ✗ (W) | 90 ✗ (T) | 103 ✗ (W) | 83 | 0/3 |
| SU-partial | 59 ✗ (W) | 51 ✓ | 80 ✗ (T) | 63.3 | 1/3 |
| SS | 125 ✗ (S) | 125 ✗ (S) | 101 ✓ | 117 | 1/3 |
| SS-partial | 60 ✗ (W) | 108 ✗ (W) | 89 ✓ | 85.7 | 1/3 |
| TRC-SU | 102 ✗ (T) | 93 ✗ (W) | 125 ✗ (S) | 106.7 | 0/3 |
| TRC-SS | 125 ✗ (S) | 109 ✓ | 125 ✗ (S) | 119.7 | 1/3 |

## sympy__sympy-15875

> is_zero is incorrect on complex integer

| Policy | Run 1 | Run 2 | Run 3 | Mean steps | Resolved |
|---|---|---|---|---|---|
| FC | 45 ✗ (T) | 58 ✗ (W) | 66 ✗ (T) | 56.3 | 0/3 |
| oTRC | 60 ✗ (W) | 99 ✓ | 56 ✗ (T) | 71.7 | 1/3 |
| oTRC-TR | 80 ✗ (W) | 85 ✗ (T) | 78 ✗ (T) | 81 | 0/3 |
| oTRC-SU-partial | 60 ✗ (W) | 60 ✗ (T) | 68 ✗ (W) | 62.7 | 0/3 |
| oTRC-SS-partial | 68 ✗ (T) | 42 ✓ | 48 ✗ (T) | 52.7 | 1/3 |
| TR | 53 ✗ (W) | 76 ✓ | 38 ✓ | 55.7 | 2/3 |
| TRC | 122 ✓ | 51 ✗ (W) | 77 ✗ (W) | 83.3 | 1/3 |
| SU (su-full) | 50 ✗ (W) | 91 ✗ (T) | 61 ✗ (W) | 67.3 | 0/3 |
| SU-partial | 68 ✗ (W) | 52 ✗ (W) | 46 ✓ | 55.3 | 1/3 |
| SS | 45 ✗ (W) | 53 ✗ (W) | 59 ✗ (W) | 52.3 | 0/3 |
| SS-partial | 64 ✗ (W) | 75 ✗ (W) | 125 ✗ (S) | 88 | 0/3 |
| TRC-SU | 38 ✓ | 125 ✗ (S) | 51 ✗ (W) | 71.3 | 1/3 |
| TRC-SS | 33 ✗ (W) | 59 ✗ (W) | 67 ✗ (T) | 53 | 0/3 |
