# Task D analysis: FC succeeds; remains solved under all compression policies

Cell: Qwen3.5-35B-A3B, `main` section, depth 0.5. Compression policies at token budget 15k; FC and oTRC at unlimited budget.

Failure cause in parentheses after ✗: 
- **S** = step limit (125 steps)
- **T** = time limit (1500 s wall-clock timeout)
- **W** = submitted a wrong answer (includes submissions with an empty patch).

## django__django-11066

> RenameContentType._rename() doesn't save the content type on the correct database

| Policy | Run 1 | Run 2 | Run 3 | Mean steps | Resolved |
|---|---|---|---|---|---|
| FC | 7 ✓ | 10 ✓ | 7 ✓ | 8 | 3/3 |
| oTRC | 13 ✓ | 9 ✓ | 7 ✓ | 9.7 | 3/3 |
| oTRC-TR | 10 ✓ | 6 ✓ | 11 ✓ | 9 | 3/3 |
| oTRC-SU-partial | 9 ✓ | 51 ✓ | 10 ✓ | 23.3 | 3/3 |
| oTRC-SS-partial | 11 ✓ | 13 ✓ | 7 ✓ | 10.3 | 3/3 |
| TR | 9 ✓ | 9 ✓ | 9 ✓ | 9 | 3/3 |
| TRC | 14 ✓ | 8 ✓ | 7 ✓ | 9.7 | 3/3 |
| SU (su-full) | 13 ✓ | 12 ✓ | 15 ✓ | 13.3 | 3/3 |
| SU-partial | 7 ✓ | 7 ✓ | 7 ✓ | 7 | 3/3 |
| SS | 7 ✓ | 7 ✓ | 12 ✓ | 8.7 | 3/3 |
| SS-partial | 7 ✓ | 11 ✓ | 7 ✓ | 8.3 | 3/3 |
| TRC-SU | 8 ✓ | 7 ✓ | 7 ✓ | 7.3 | 3/3 |
| TRC-SS | 8 ✓ | 7 ✓ | 7 ✓ | 7.3 | 3/3 |

## django__django-12143

> Possible data loss in admin changeform view when using regex special characters in formset prefix

| Policy | Run 1 | Run 2 | Run 3 | Mean steps | Resolved |
|---|---|---|---|---|---|
| FC | 19 ✓ | 24 ✓ | 25 ✓ | 22.7 | 3/3 |
| oTRC | 21 ✓ | 30 ✓ | 16 ✓ | 22.3 | 3/3 |
| oTRC-TR | 20 ✓ | 14 ✓ | 89 ✓ | 41 | 3/3 |
| oTRC-SU-partial | 16 ✓ | 18 ✓ | 24 ✓ | 19.3 | 3/3 |
| oTRC-SS-partial | 20 ✓ | 45 ✓ | 28 ✓ | 31 | 3/3 |
| TR | 35 ✓ | 26 ✓ | 43 ✓ | 34.7 | 3/3 |
| TRC | 51 ✓ | 45 ✓ | 54 ✓ | 50 | 3/3 |
| SU (su-full) | 18 ✓ | 17 ✓ | 55 ✓ | 30 | 3/3 |
| SU-partial | 21 ✓ | 23 ✓ | 29 ✓ | 24.3 | 3/3 |
| SS | 40 ✓ | 21 ✓ | 17 ✓ | 26 | 3/3 |
| SS-partial | 33 ✓ | 25 ✓ | 24 ✓ | 27.3 | 3/3 |
| TRC-SU | 26 ✓ | 29 ✓ | 34 ✓ | 29.7 | 3/3 |
| TRC-SS | 25 ✓ | 48 ✓ | 21 ✓ | 31.3 | 3/3 |

## django__django-12276

> FileInput shouldn't display required attribute when initial data exists.

| Policy | Run 1 | Run 2 | Run 3 | Mean steps | Resolved |
|---|---|---|---|---|---|
| FC | 57 ✓ | 46 ✓ | 42 ✓ | 48.3 | 3/3 |
| oTRC | 29 ✓ | 24 ✓ | 55 ✓ | 36 | 3/3 |
| oTRC-TR | 68 ✓ | 68 ✓ | 30 ✓ | 55.3 | 3/3 |
| oTRC-SU-partial | 57 ✓ | 57 ✓ | 60 ✓ | 58 | 3/3 |
| oTRC-SS-partial | 32 ✓ | 62 ✓ | 60 ✓ | 51.3 | 3/3 |
| TR | 84 ✓ | 51 ✓ | 40 ✗ (W) | 58.3 | 2/3 |
| TRC | 58 ✓ | 43 ✓ | 25 ✓ | 42 | 3/3 |
| SU (su-full) | 41 ✓ | 33 ✓ | 105 ✗ (T) | 59.7 | 2/3 |
| SU-partial | 60 ✓ | 39 ✓ | 43 ✓ | 47.3 | 3/3 |
| SS | 39 ✓ | 43 ✓ | 49 ✓ | 43.7 | 3/3 |
| SS-partial | 72 ✓ | 51 ✓ | 125 ✗ (S) | 82.7 | 2/3 |
| TRC-SU | 42 ✓ | 38 ✓ | 32 ✓ | 37.3 | 3/3 |
| TRC-SS | 38 ✓ | 48 ✓ | 46 ✓ | 44 | 3/3 |

## django__django-14915

> ModelChoiceIteratorValue is not hashable.

| Policy | Run 1 | Run 2 | Run 3 | Mean steps | Resolved |
|---|---|---|---|---|---|
| FC | 19 ✓ | 35 ✗ (W) | 48 ✓ | 34 | 2/3 |
| oTRC | 41 ✓ | 41 ✓ | 34 ✓ | 38.7 | 3/3 |
| oTRC-TR | 35 ✓ | 20 ✓ | 19 ✓ | 24.7 | 3/3 |
| oTRC-SU-partial | 19 ✓ | 23 ✓ | 65 ✓ | 35.7 | 3/3 |
| oTRC-SS-partial | 23 ✓ | 20 ✓ | 22 ✓ | 21.7 | 3/3 |
| TR | 35 ✓ | 33 ✓ | 34 ✓ | 34 | 3/3 |
| TRC | 30 ✓ | 35 ✓ | 34 ✓ | 33 | 3/3 |
| SU (su-full) | 28 ✓ | 48 ✓ | 77 ✗ (W) | 51 | 2/3 |
| SU-partial | 19 ✓ | 35 ✓ | 24 ✓ | 26 | 3/3 |
| SS | 36 ✓ | 35 ✓ | 40 ✓ | 37 | 3/3 |
| SS-partial | 45 ✓ | 19 ✓ | 19 ✓ | 27.7 | 3/3 |
| TRC-SU | 43 ✓ | 35 ✓ | 17 ✓ | 31.7 | 3/3 |
| TRC-SS | 18 ✓ | 41 ✓ | 31 ✓ | 30 | 3/3 |

## django__django-15741

> django.utils.formats.get_format should allow lazy parameter

| Policy | Run 1 | Run 2 | Run 3 | Mean steps | Resolved |
|---|---|---|---|---|---|
| FC | 66 ✓ | 66 ✓ | 52 ✓ | 61.3 | 3/3 |
| oTRC | 50 ✓ | 71 ✓ | 82 ✓ | 67.7 | 3/3 |
| oTRC-TR | 40 ✓ | 56 ✓ | 73 ✓ | 56.3 | 3/3 |
| oTRC-SU-partial | 26 ✓ | 86 ✓ | 44 ✓ | 52 | 3/3 |
| oTRC-SS-partial | 111 ✓ | 65 ✓ | 47 ✓ | 74.3 | 3/3 |
| TR | 47 ✓ | 60 ✗ (W) | 116 ✓ | 74.3 | 2/3 |
| TRC | 48 ✓ | 58 ✓ | 56 ✓ | 54 | 3/3 |
| SU (su-full) | 104 ✗ (T) | 70 ✓ | 56 ✓ | 76.7 | 2/3 |
| SU-partial | 44 ✓ | 37 ✓ | 49 ✓ | 43.3 | 3/3 |
| SS | 38 ✓ | 125 ✗ (S) | 38 ✓ | 67 | 2/3 |
| SS-partial | 82 ✓ | 36 ✓ | 45 ✓ | 54.3 | 3/3 |
| TRC-SU | 70 ✓ | 49 ✓ | 69 ✓ | 62.7 | 3/3 |
| TRC-SS | 125 ✗ (S) | 56 ✓ | 43 ✓ | 74.7 | 2/3 |

## scikit-learn__scikit-learn-10297

> linear_model.RidgeClassifierCV's Parameter store_cv_values issue

| Policy | Run 1 | Run 2 | Run 3 | Mean steps | Resolved |
|---|---|---|---|---|---|
| FC | 38 ✓ | 41 ✓ | 58 ✓ | 45.7 | 3/3 |
| oTRC | 47 ✓ | 80 ✓ | 60 ✓ | 62.3 | 3/3 |
| oTRC-TR | 46 ✓ | 43 ✓ | 44 ✓ | 44.3 | 3/3 |
| oTRC-SU-partial | 65 ✓ | 58 ✓ | 125 ✗ (S) | 82.7 | 2/3 |
| oTRC-SS-partial | 78 ✓ | 39 ✓ | 33 ✓ | 50 | 3/3 |
| TR | 41 ✓ | 40 ✓ | 45 ✓ | 42 | 3/3 |
| TRC | 81 ✓ | 54 ✓ | 79 ✓ | 71.3 | 3/3 |
| SU (su-full) | 125 ✗ (S) | 38 ✓ | 49 ✓ | 70.7 | 2/3 |
| SU-partial | 44 ✓ | 34 ✓ | 28 ✓ | 35.3 | 3/3 |
| SS | 31 ✓ | 46 ✓ | 63 ✓ | 46.7 | 3/3 |
| SS-partial | 50 ✓ | 38 ✓ | 104 ✓ | 64 | 3/3 |
| TRC-SU | 51 ✓ | 38 ✓ | 86 ✓ | 58.3 | 3/3 |
| TRC-SS | 50 ✓ | 55 ✓ | 42 ✓ | 49 | 3/3 |

## scikit-learn__scikit-learn-10844

> fowlkes_mallows_score returns RuntimeWarning when variables get too big

| Policy | Run 1 | Run 2 | Run 3 | Mean steps | Resolved |
|---|---|---|---|---|---|
| FC | 57 ✓ | 27 ✓ | 24 ✓ | 36 | 3/3 |
| oTRC | 31 ✓ | 59 ✓ | 24 ✓ | 38 | 3/3 |
| oTRC-TR | 40 ✓ | 42 ✓ | 35 ✓ | 39 | 3/3 |
| oTRC-SU-partial | 56 ✓ | 125 ✗ (S) | 42 ✓ | 74.3 | 2/3 |
| oTRC-SS-partial | 26 ✓ | 26 ✓ | 40 ✓ | 30.7 | 3/3 |
| TR | 29 ✓ | 35 ✓ | 34 ✓ | 32.7 | 3/3 |
| TRC | 22 ✓ | 20 ✓ | 36 ✓ | 26 | 3/3 |
| SU (su-full) | 77 ✓ | 21 ✓ | 52 ✓ | 50 | 3/3 |
| SU-partial | 27 ✓ | 24 ✓ | 33 ✓ | 28 | 3/3 |
| SS | 19 ✓ | 19 ✓ | 32 ✓ | 23.3 | 3/3 |
| SS-partial | 56 ✓ | 29 ✓ | 51 ✓ | 45.3 | 3/3 |
| TRC-SU | 30 ✓ | 19 ✓ | 25 ✓ | 24.7 | 3/3 |
| TRC-SS | 42 ✓ | 26 ✓ | 44 ✓ | 37.3 | 3/3 |

## scikit-learn__scikit-learn-12585

> clone fails for parameters that are estimator types

| Policy | Run 1 | Run 2 | Run 3 | Mean steps | Resolved |
|---|---|---|---|---|---|
| FC | 31 ✓ | 46 ✓ | 40 ✓ | 39 | 3/3 |
| oTRC | 47 ✓ | 63 ✓ | 45 ✓ | 51.7 | 3/3 |
| oTRC-TR | 48 ✓ | 57 ✓ | 43 ✓ | 49.3 | 3/3 |
| oTRC-SU-partial | 30 ✓ | 36 ✓ | 34 ✓ | 33.3 | 3/3 |
| oTRC-SS-partial | 97 ✓ | 19 ✓ | 46 ✓ | 54 | 3/3 |
| TR | 37 ✓ | 39 ✓ | 31 ✓ | 35.7 | 3/3 |
| TRC | 51 ✓ | 44 ✓ | 30 ✓ | 41.7 | 3/3 |
| SU (su-full) | 99 ✓ | 44 ✓ | 59 ✓ | 67.3 | 3/3 |
| SU-partial | 32 ✓ | 23 ✓ | 47 ✗ (W) | 34 | 2/3 |
| SS | 41 ✓ | 32 ✓ | 37 ✓ | 36.7 | 3/3 |
| SS-partial | 26 ✓ | 35 ✓ | 21 ✓ | 27.3 | 3/3 |
| TRC-SU | 88 ✓ | 50 ✓ | 27 ✓ | 55 | 3/3 |
| TRC-SS | 41 ✓ | 32 ✓ | 20 ✓ | 31 | 3/3 |

## scikit-learn__scikit-learn-13135

> KBinsDiscretizer: kmeans fails due to unsorted bin_edges

| Policy | Run 1 | Run 2 | Run 3 | Mean steps | Resolved |
|---|---|---|---|---|---|
| FC | 42 ✓ | 44 ✓ | 36 ✓ | 40.7 | 3/3 |
| oTRC | 70 ✓ | 76 ✓ | 106 ✓ | 84 | 3/3 |
| oTRC-TR | 73 ✓ | 76 ✓ | 48 ✓ | 65.7 | 3/3 |
| oTRC-SU-partial | 40 ✓ | 102 ✓ | 58 ✓ | 66.7 | 3/3 |
| oTRC-SS-partial | 124 ✓ | 108 ✗ (T) | 64 ✓ | 98.7 | 2/3 |
| TR | 64 ✓ | 36 ✓ | 116 ✓ | 72 | 3/3 |
| TRC | 43 ✓ | 57 ✓ | 42 ✓ | 47.3 | 3/3 |
| SU (su-full) | 45 ✓ | 35 ✓ | 125 ✗ (S) | 68.3 | 2/3 |
| SU-partial | 41 ✓ | 29 ✓ | 68 ✓ | 46 | 3/3 |
| SS | 49 ✓ | 116 ✓ | 54 ✓ | 73 | 3/3 |
| SS-partial | 61 ✓ | 45 ✓ | 56 ✓ | 54 | 3/3 |
| TRC-SU | 73 ✓ | 80 ✓ | 51 ✓ | 68 | 3/3 |
| TRC-SS | 46 ✓ | 64 ✓ | 52 ✓ | 54 | 3/3 |

## scikit-learn__scikit-learn-13142

> GaussianMixture predict and fit_predict disagree when n_init>1

| Policy | Run 1 | Run 2 | Run 3 | Mean steps | Resolved |
|---|---|---|---|---|---|
| FC | 57 ✓ | 34 ✓ | 47 ✓ | 46 | 3/3 |
| oTRC | 88 ✓ | 88 ✓ | 58 ✓ | 78 | 3/3 |
| oTRC-TR | 50 ✓ | 70 ✓ | 56 ✗ (W) | 58.7 | 2/3 |
| oTRC-SU-partial | 56 ✓ | 33 ✓ | 64 ✓ | 51 | 3/3 |
| oTRC-SS-partial | 55 ✓ | 40 ✓ | 54 ✓ | 49.7 | 3/3 |
| TR | 44 ✓ | 45 ✓ | 43 ✓ | 44 | 3/3 |
| TRC | 41 ✓ | 45 ✓ | 45 ✓ | 43.7 | 3/3 |
| SU (su-full) | 57 ✓ | 111 ✗ (T) | 55 ✓ | 74.3 | 2/3 |
| SU-partial | 44 ✓ | 62 ✓ | 54 ✓ | 53.3 | 3/3 |
| SS | 64 ✓ | 57 ✓ | 77 ✗ (W) | 66 | 2/3 |
| SS-partial | 60 ✗ (W) | 35 ✓ | 31 ✓ | 42 | 2/3 |
| TRC-SU | 32 ✗ (W) | 46 ✓ | 66 ✓ | 48 | 2/3 |
| TRC-SS | 125 ✗ (S) | 43 ✓ | 45 ✓ | 71 | 2/3 |

## scikit-learn__scikit-learn-13439

> Pipeline should implement __len__

| Policy | Run 1 | Run 2 | Run 3 | Mean steps | Resolved |
|---|---|---|---|---|---|
| FC | 53 ✓ | 45 ✓ | 38 ✓ | 45.3 | 3/3 |
| oTRC | 48 ✓ | 35 ✓ | 66 ✓ | 49.7 | 3/3 |
| oTRC-TR | 125 ✗ (S) | 37 ✓ | 57 ✓ | 73 | 2/3 |
| oTRC-SU-partial | 84 ✓ | 55 ✓ | 32 ✓ | 57 | 3/3 |
| oTRC-SS-partial | 46 ✓ | 31 ✓ | 50 ✓ | 42.3 | 3/3 |
| TR | 34 ✓ | 51 ✓ | 27 ✓ | 37.3 | 3/3 |
| TRC | 70 ✓ | 57 ✓ | 33 ✓ | 53.3 | 3/3 |
| SU (su-full) | 23 ✓ | 45 ✗ (W) | 63 ✓ | 43.7 | 2/3 |
| SU-partial | 28 ✓ | 36 ✓ | 27 ✓ | 30.3 | 3/3 |
| SS | 51 ✓ | 41 ✗ (W) | 39 ✓ | 43.7 | 2/3 |
| SS-partial | 35 ✓ | 35 ✓ | 40 ✓ | 36.7 | 3/3 |
| TRC-SU | 56 ✓ | 27 ✓ | 77 ✓ | 53.3 | 3/3 |
| TRC-SS | 44 ✓ | 112 ✗ (W) | 27 ✓ | 61 | 2/3 |

## scikit-learn__scikit-learn-14141

> Add joblib in show_versions

| Policy | Run 1 | Run 2 | Run 3 | Mean steps | Resolved |
|---|---|---|---|---|---|
| FC | 20 ✓ | 16 ✓ | 23 ✓ | 19.7 | 3/3 |
| oTRC | 18 ✓ | 20 ✓ | 20 ✓ | 19.3 | 3/3 |
| oTRC-TR | 29 ✓ | 18 ✓ | 22 ✓ | 23 | 3/3 |
| oTRC-SU-partial | 28 ✓ | 24 ✓ | 22 ✓ | 24.7 | 3/3 |
| oTRC-SS-partial | 20 ✓ | 16 ✓ | 23 ✓ | 19.7 | 3/3 |
| TR | 14 ✓ | 16 ✓ | 20 ✓ | 16.7 | 3/3 |
| TRC | 19 ✓ | 21 ✓ | 22 ✓ | 20.7 | 3/3 |
| SU (su-full) | 27 ✓ | 21 ✓ | 22 ✓ | 23.3 | 3/3 |
| SU-partial | 23 ✓ | 15 ✓ | 16 ✓ | 18 | 3/3 |
| SS | 22 ✓ | 15 ✓ | 22 ✓ | 19.7 | 3/3 |
| SS-partial | 20 ✓ | 22 ✓ | 17 ✓ | 19.7 | 3/3 |
| TRC-SU | 24 ✓ | 24 ✓ | 17 ✓ | 21.7 | 3/3 |
| TRC-SS | 19 ✓ | 20 ✓ | 22 ✓ | 20.3 | 3/3 |

## scikit-learn__scikit-learn-14894

> ZeroDivisionError in _sparse_fit for SVM with empty support_vectors_

| Policy | Run 1 | Run 2 | Run 3 | Mean steps | Resolved |
|---|---|---|---|---|---|
| FC | 65 ✓ | 47 ✓ | 49 ✓ | 53.7 | 3/3 |
| oTRC | 25 ✓ | 36 ✓ | 56 ✓ | 39 | 3/3 |
| oTRC-TR | 62 ✓ | 49 ✓ | 51 ✓ | 54 | 3/3 |
| oTRC-SU-partial | 43 ✓ | 36 ✓ | 66 ✓ | 48.3 | 3/3 |
| oTRC-SS-partial | 39 ✓ | 30 ✓ | 54 ✓ | 41 | 3/3 |
| TR | 71 ✓ | 59 ✓ | 34 ✓ | 54.7 | 3/3 |
| TRC | 50 ✓ | 33 ✓ | 40 ✓ | 41 | 3/3 |
| SU (su-full) | 38 ✓ | 42 ✓ | 59 ✓ | 46.3 | 3/3 |
| SU-partial | 37 ✓ | 29 ✓ | 50 ✓ | 38.7 | 3/3 |
| SS | 53 ✓ | 31 ✓ | 55 ✗ (W) | 46.3 | 2/3 |
| SS-partial | 40 ✓ | 36 ✓ | 34 ✓ | 36.7 | 3/3 |
| TRC-SU | 121 ✓ | 60 ✓ | 50 ✓ | 77 | 3/3 |
| TRC-SS | 44 ✓ | 53 ✓ | 76 ✓ | 57.7 | 3/3 |

## sympy__sympy-15349

> Incorrect result with Quaterniont.to_rotation_matrix()

| Policy | Run 1 | Run 2 | Run 3 | Mean steps | Resolved |
|---|---|---|---|---|---|
| FC | 25 ✓ | 31 ✓ | 25 ✓ | 27 | 3/3 |
| oTRC | 37 ✓ | 23 ✓ | 125 ✗ (S) | 61.7 | 2/3 |
| oTRC-TR | 27 ✓ | 34 ✓ | 15 ✓ | 25.3 | 3/3 |
| oTRC-SU-partial | 31 ✓ | 40 ✓ | 25 ✓ | 32 | 3/3 |
| oTRC-SS-partial | 36 ✓ | 21 ✓ | 37 ✗ (W) | 31.3 | 2/3 |
| TR | 26 ✓ | 30 ✓ | 43 ✓ | 33 | 3/3 |
| TRC | 24 ✓ | 30 ✓ | 36 ✓ | 30 | 3/3 |
| SU (su-full) | 25 ✓ | 24 ✓ | 29 ✓ | 26 | 3/3 |
| SU-partial | 33 ✗ (W) | 36 ✓ | 12 ✓ | 27 | 2/3 |
| SS | 43 ✓ | 27 ✓ | 35 ✓ | 35 | 3/3 |
| SS-partial | 36 ✓ | 40 ✓ | 32 ✓ | 36 | 3/3 |
| TRC-SU | 28 ✓ | 23 ✓ | 52 ✗ (W) | 34.3 | 2/3 |
| TRC-SS | 26 ✓ | 24 ✓ | 41 ✓ | 30.3 | 3/3 |

## sympy__sympy-16450

> Posify ignores is_finite assmptions

| Policy | Run 1 | Run 2 | Run 3 | Mean steps | Resolved |
|---|---|---|---|---|---|
| FC | 27 ✓ | 44 ✓ | 35 ✓ | 35.3 | 3/3 |
| oTRC | 65 ✓ | 33 ✓ | 35 ✓ | 44.3 | 3/3 |
| oTRC-TR | 45 ✓ | 37 ✓ | 44 ✓ | 42 | 3/3 |
| oTRC-SU-partial | 55 ✓ | 34 ✓ | 35 ✓ | 41.3 | 3/3 |
| oTRC-SS-partial | 45 ✓ | 44 ✓ | 24 ✗ (W) | 37.7 | 2/3 |
| TR | 44 ✓ | 32 ✓ | 68 ✓ | 48 | 3/3 |
| TRC | 48 ✓ | 33 ✓ | 51 ✓ | 44 | 3/3 |
| SU (su-full) | 51 ✓ | 33 ✓ | 38 ✓ | 40.7 | 3/3 |
| SU-partial | 51 ✓ | 29 ✓ | 32 ✓ | 37.3 | 3/3 |
| SS | 34 ✓ | 35 ✓ | 39 ✓ | 36 | 3/3 |
| SS-partial | 40 ✓ | 39 ✓ | 43 ✓ | 40.7 | 3/3 |
| TRC-SU | 47 ✓ | 48 ✓ | 40 ✓ | 45 | 3/3 |
| TRC-SS | 34 ✓ | 44 ✓ | 37 ✓ | 38.3 | 3/3 |

## sympy__sympy-18189

> diophantine: incomplete results depending on syms order with permute=True

| Policy | Run 1 | Run 2 | Run 3 | Mean steps | Resolved |
|---|---|---|---|---|---|
| FC | 71 ✓ | 38 ✓ | 18 ✓ | 42.3 | 3/3 |
| oTRC | 32 ✓ | 34 ✗ (W) | 26 ✓ | 30.7 | 2/3 |
| oTRC-TR | 65 ✓ | 57 ✓ | 125 ✗ (S) | 82.3 | 2/3 |
| oTRC-SU-partial | 28 ✓ | 36 ✓ | 31 ✓ | 31.7 | 3/3 |
| oTRC-SS-partial | 25 ✓ | 31 ✓ | 21 ✓ | 25.7 | 3/3 |
| TR | 20 ✓ | 37 ✓ | 37 ✓ | 31.3 | 3/3 |
| TRC | 19 ✓ | 66 ✗ (W) | 50 ✓ | 45 | 2/3 |
| SU (su-full) | 38 ✓ | 45 ✓ | 106 ✗ (T) | 63 | 2/3 |
| SU-partial | 21 ✓ | 18 ✓ | 23 ✓ | 20.7 | 3/3 |
| SS | 16 ✓ | 26 ✓ | 67 ✓ | 36.3 | 3/3 |
| SS-partial | 26 ✓ | 73 ✓ | 20 ✓ | 39.7 | 3/3 |
| TRC-SU | 25 ✓ | 31 ✓ | 24 ✓ | 26.7 | 3/3 |
| TRC-SS | 26 ✓ | 31 ✓ | 23 ✓ | 26.7 | 3/3 |

## sympy__sympy-19954

> sylow_subgroup() IndexError

| Policy | Run 1 | Run 2 | Run 3 | Mean steps | Resolved |
|---|---|---|---|---|---|
| FC | 22 ✓ | 29 ✓ | 21 ✓ | 24 | 3/3 |
| oTRC | 39 ✓ | 29 ✓ | 25 ✓ | 31 | 3/3 |
| oTRC-TR | 26 ✓ | 21 ✓ | 36 ✓ | 27.7 | 3/3 |
| oTRC-SU-partial | 27 ✓ | 29 ✓ | 31 ✓ | 29 | 3/3 |
| oTRC-SS-partial | 20 ✓ | 25 ✓ | 27 ✓ | 24 | 3/3 |
| TR | 19 ✓ | 26 ✓ | 30 ✓ | 25 | 3/3 |
| TRC | 28 ✓ | 28 ✓ | 29 ✓ | 28.3 | 3/3 |
| SU (su-full) | 38 ✓ | 31 ✓ | 24 ✓ | 31 | 3/3 |
| SU-partial | 22 ✓ | 37 ✓ | 27 ✓ | 28.7 | 3/3 |
| SS | 35 ✓ | 28 ✓ | 49 ✗ (T) | 37.3 | 2/3 |
| SS-partial | 23 ✓ | 17 ✓ | 34 ✓ | 24.7 | 3/3 |
| TRC-SU | 30 ✓ | 24 ✓ | 23 ✓ | 25.7 | 3/3 |
| TRC-SS | 29 ✓ | 27 ✓ | 39 ✓ | 31.7 | 3/3 |

## sympy__sympy-24213

> collect_factor_and_dimension does not detect equivalent dimensions in addition

| Policy | Run 1 | Run 2 | Run 3 | Mean steps | Resolved |
|---|---|---|---|---|---|
| FC | 26 ✓ | 23 ✓ | 26 ✓ | 25 | 3/3 |
| oTRC | 30 ✓ | 30 ✓ | 33 ✓ | 31 | 3/3 |
| oTRC-TR | 28 ✓ | 36 ✓ | 34 ✓ | 32.7 | 3/3 |
| oTRC-SU-partial | 36 ✓ | 40 ✓ | 27 ✓ | 34.3 | 3/3 |
| oTRC-SS-partial | 26 ✓ | 20 ✓ | 25 ✓ | 23.7 | 3/3 |
| TR | 45 ✓ | 21 ✓ | 34 ✓ | 33.3 | 3/3 |
| TRC | 23 ✓ | 22 ✓ | 19 ✓ | 21.3 | 3/3 |
| SU (su-full) | 22 ✓ | 25 ✓ | 18 ✓ | 21.7 | 3/3 |
| SU-partial | 25 ✓ | 18 ✓ | 35 ✓ | 26 | 3/3 |
| SS | 21 ✓ | 18 ✓ | 74 ✗ (T) | 37.7 | 2/3 |
| SS-partial | 33 ✓ | 27 ✓ | 27 ✓ | 29 | 3/3 |
| TRC-SU | 20 ✓ | 17 ✓ | 21 ✓ | 19.3 | 3/3 |
| TRC-SS | 30 ✓ | 28 ✓ | 31 ✓ | 29.7 | 3/3 |

## sympy__sympy-24661

> The evaluate=False parameter to `parse_expr` is ignored for relationals

| Policy | Run 1 | Run 2 | Run 3 | Mean steps | Resolved |
|---|---|---|---|---|---|
| FC | 44 ✓ | 25 ✓ | 48 ✓ | 39 | 3/3 |
| oTRC | 57 ✓ | 77 ✓ | 39 ✓ | 57.7 | 3/3 |
| oTRC-TR | 40 ✓ | 45 ✓ | 113 ✓ | 66 | 3/3 |
| oTRC-SU-partial | 40 ✓ | 58 ✓ | 58 ✓ | 52 | 3/3 |
| oTRC-SS-partial | 60 ✓ | 60 ✓ | 70 ✓ | 63.3 | 3/3 |
| TR | 55 ✓ | 42 ✓ | 72 ✓ | 56.3 | 3/3 |
| TRC | 32 ✓ | 54 ✓ | 39 ✓ | 41.7 | 3/3 |
| SU (su-full) | 43 ✓ | 85 ✓ | 36 ✓ | 54.7 | 3/3 |
| SU-partial | 34 ✓ | 59 ✓ | 33 ✓ | 42 | 3/3 |
| SS | 46 ✓ | 80 ✓ | 42 ✓ | 56 | 3/3 |
| SS-partial | 41 ✓ | 34 ✓ | 95 ✓ | 56.7 | 3/3 |
| TRC-SU | 46 ✓ | 45 ✓ | 42 ✓ | 44.3 | 3/3 |
| TRC-SS | 35 ✓ | 48 ✓ | 51 ✓ | 44.7 | 3/3 |
