# task-level analysis (SWE-bench Verified, Qwen)
- Success: resolved in at least 2 out of 3 runs

## Task A: FC fails; many compression policies succeed

| Task | N | Successful policies | Unsuccessful policies | Task description |
|---|---|---|---|---|
| [django__django-13012](taskA_analysis.md#django__django-13012) | 10/12 | SU, SU-p, SS, SS-p, TRC+SU, TRC+SS, oTRC, oTRC+TR, oTRC+SU-p, oTRC+SS-p | TR, TRC | Constant expressions of an ExpressionWrapper object are incorrectly placed at the GROUP BY clause |
| [scikit-learn__scikit-learn-13328](taskA_analysis.md#scikit-learn__scikit-learn-13328) | 9/12 | SU-p, SS, SS-p, TRC+SU, TRC+SS, oTRC, oTRC+TR, oTRC+SU-p, oTRC+SS-p | TR, TRC, SU | TypeError when supplying a boolean X to HuberRegressor fit |
| [scikit-learn__scikit-learn-14496](taskA_analysis.md#scikit-learn__scikit-learn-14496) | 9/12 | SU-p, SS, SS-p, TRC+SU, TRC+SS, oTRC, oTRC+TR, oTRC+SU-p, oTRC+SS-p | TR, TRC, SU | [BUG] Optics float min_samples NN instantiation |
| [sympy__sympy-24443](taskA_analysis.md#sympy__sympy-24443) | 9/12 | SU, SU-p, SS-p, TRC+SU, TRC+SS, oTRC, oTRC+TR, oTRC+SU-p, oTRC+SS-p | TR, TRC, SS | `_check_homomorphism` is broken on PermutationGroups |
| [scikit-learn__scikit-learn-15100](taskA_analysis.md#scikit-learn__scikit-learn-15100) | 8/12 | SU-p, SS-p, TRC+SU, TRC+SS, oTRC, oTRC+TR, oTRC+SU-p, oTRC+SS-p | TR, TRC, SU, SS | strip_accents_unicode fails to strip accents from strings that are already in NFKD form |
| [scikit-learn__scikit-learn-26323](taskA_analysis.md#scikit-learn__scikit-learn-26323) | 8/12 | SU, SS-p, TRC+SU, TRC+SS, oTRC, oTRC+TR, oTRC+SU-p, oTRC+SS-p | TR, TRC, SU-p, SS | `ColumnTransformer.set_output` ignores the `remainder` if it's an estimator |
| [sympy__sympy-19637](taskA_analysis.md#sympy__sympy-19637) | 8/12 | SU-p, SS-p, TRC+SU, TRC+SS, oTRC, oTRC+TR, oTRC+SU-p, oTRC+SS-p | TR, TRC, SU, SS | kernS: 'kern' referenced before assignment |
| [scikit-learn__scikit-learn-14053](taskA_analysis.md#scikit-learn__scikit-learn-14053) | 7/12 | TR, TRC, SU-p, SS-p, TRC+SU, oTRC, oTRC+SS-p | SU, SS, TRC+SS, oTRC+TR, oTRC+SU-p | IndexError: list index out of range in export_text when the tree only has one feature |
| [sympy__sympy-15017](taskA_analysis.md#sympy__sympy-15017) | 7/12 | SU-p, SS-p, TRC+SU, oTRC, oTRC+TR, oTRC+SU-p, oTRC+SS-p | TR, TRC, SU, SS, TRC+SS | `len` of rank-0 arrays returns 0 |

## Task C: FC succeeds; many compression policies fail

| Task | N | Successful policies | Unsuccessful policies | Task description |
|---|---|---|---|---|
| [scikit-learn__scikit-learn-26194](taskC_analysis.md#scikit-learn__scikit-learn-26194) | 12/12 | — | TR, TRC, SU, SU-p, SS, SS-p, TRC+SU, TRC+SS, oTRC, oTRC+TR, oTRC+SU-p, oTRC+SS-p | Thresholds can exceed 1 in `roc_curve` while providing probability estimate |
| [sympy__sympy-17318](taskC_analysis.md#sympy__sympy-17318) | 12/12 | — | TR, TRC, SU, SU-p, SS, SS-p, TRC+SU, TRC+SS, oTRC, oTRC+TR, oTRC+SU-p, oTRC+SS-p | sqrtdenest raises IndexError |
| [scikit-learn__scikit-learn-9288](taskC_analysis.md#scikit-learn__scikit-learn-9288) | 9/12 | TRC, oTRC, oTRC+SU-p | TR, SU, SU-p, SS, SS-p, TRC+SU, TRC+SS, oTRC+TR, oTRC+SS-p | KMeans gives slightly different result for n_jobs=1 vs. n_jobs > 1 |
| [scikit-learn__scikit-learn-10908](taskC_analysis.md#scikit-learn__scikit-learn-10908) | 8/12 | TRC, SU, oTRC+SU-p, oTRC+SS-p | TR, SU-p, SS, SS-p, TRC+SU, TRC+SS, oTRC, oTRC+TR | CountVectorizer's get_feature_names raise not NotFittedError when the vocabulary parameter is provided |
| [django__django-11299](taskC_analysis.md#django__django-11299) | 6/12 | TRC, SS, SS-p, TRC+SU, TRC+SS, oTRC+SU-p | TR, SU, SU-p, oTRC, oTRC+TR, oTRC+SS-p | CheckConstraint with OR operator generates incorrect SQL on SQLite and Oracle. |
| [django__django-12304](taskC_analysis.md#django__django-12304) | 6/12 | TR, SU, SU-p, SS, SS-p, oTRC+SU-p | TRC, TRC+SU, TRC+SS, oTRC, oTRC+TR, oTRC+SS-p | Enumeration Types are not usable in templates. |
| [scikit-learn__scikit-learn-12682](taskC_analysis.md#scikit-learn__scikit-learn-12682) | 6/12 | TR, SU, SU-p, SS, SS-p, oTRC | TRC, TRC+SU, TRC+SS, oTRC+TR, oTRC+SU-p, oTRC+SS-p | `SparseCoder` doesn't expose `max_iter` for `Lasso` |
| [scikit-learn__scikit-learn-25232](taskC_analysis.md#scikit-learn__scikit-learn-25232) | 6/12 | TR, TRC, SU-p, SS, TRC+SU, TRC+SS | SU, SS-p, oTRC, oTRC+TR, oTRC+SU-p, oTRC+SS-p | IterativeImputer has no parameter "fill_value" |
| [sympy__sympy-14711](taskC_analysis.md#sympy__sympy-14711) | 6/12 | TR, SU-p, SS, TRC+SS, oTRC+SU-p, oTRC+SS-p | TRC, SU, SS-p, TRC+SU, oTRC, oTRC+TR | vector add 0 error |

## Task B: FC fails; only a few compression policies succeed

| Task | N | Successful policies | Unsuccessful policies | Task description |
|---|---|---|---|---|
| [django__django-13810](taskB_analysis.md#django__django-13810) | 2/12 | SU-p, oTRC+SU-p | TR, TRC, SU, SS, SS-p, TRC+SU, TRC+SS, oTRC, oTRC+TR, oTRC+SS-p | MiddlewareNotUsed leaves undesired side effects when loading middleware in ASGI context |
| [django__django-17084](taskB_analysis.md#django__django-17084) | 2/12 | TRC, SU-p | TR, SU, SS, SS-p, TRC+SU, TRC+SS, oTRC, oTRC+TR, oTRC+SU-p, oTRC+SS-p | Cannot use aggregate over window functions since 4.2 |
| [scikit-learn__scikit-learn-11310](taskB_analysis.md#scikit-learn__scikit-learn-11310) | 2/12 | SS-p, oTRC+TR | TR, TRC, SU, SU-p, SS, TRC+SU, TRC+SS, oTRC, oTRC+SU-p, oTRC+SS-p | Retrieving time to refit the estimator in BaseSearchCV |
| [scikit-learn__scikit-learn-12973](taskB_analysis.md#scikit-learn__scikit-learn-12973) | 2/12 | SS, TRC+SU | TR, TRC, SU, SU-p, SS-p, TRC+SS, oTRC, oTRC+TR, oTRC+SU-p, oTRC+SS-p | LassoLarsIC: unintuitive copy_X behaviour |
| [sympy__sympy-13757](taskB_analysis.md#sympy__sympy-13757) | 2/12 | SU, oTRC+SU-p | TR, TRC, SU-p, SS, SS-p, TRC+SU, TRC+SS, oTRC, oTRC+TR, oTRC+SS-p | Multiplying an expression by a Poly does not evaluate when the expression is on the left side of the multiplication |
| [django__django-15525](taskB_analysis.md#django__django-15525) | 1/12 | SS-p | TR, TRC, SU, SU-p, SS, TRC+SU, TRC+SS, oTRC, oTRC+TR, oTRC+SU-p, oTRC+SS-p | loaddata fails on non-default database when natural keys uses foreign keys. |
| [django__django-15930](taskB_analysis.md#django__django-15930) | 1/12 | TRC | TR, SU, SU-p, SS, SS-p, TRC+SU, TRC+SS, oTRC, oTRC+TR, oTRC+SU-p, oTRC+SS-p | Case() crashes with ~Q(pk__in=[]). |
| [scikit-learn__scikit-learn-14983](taskB_analysis.md#scikit-learn__scikit-learn-14983) | 1/12 | TRC+SS | TR, TRC, SU, SU-p, SS, SS-p, TRC+SU, oTRC, oTRC+TR, oTRC+SU-p, oTRC+SS-p | RepeatedKFold and RepeatedStratifiedKFold do not show correct __repr__ string |
| [scikit-learn__scikit-learn-25102](taskB_analysis.md#scikit-learn__scikit-learn-25102) | 1/12 | oTRC+TR | TR, TRC, SU, SU-p, SS, SS-p, TRC+SU, TRC+SS, oTRC, oTRC+SU-p, oTRC+SS-p | Preserving dtypes for DataFrame output by transformers that do not modify the input values |
| [sympy__sympy-15875](taskB_analysis.md#sympy__sympy-15875) | 1/12 | TR | TRC, SU, SU-p, SS, SS-p, TRC+SU, TRC+SS, oTRC, oTRC+TR, oTRC+SU-p, oTRC+SS-p | is_zero is incorrect on complex integer |

## Task D: FC succeeds; remains solved under all compression policies

| Task | N | Successful policies | Unsuccessful policies | Task description |
|---|---|---|---|---|
| [django__django-11066](taskD_analysis.md#django__django-11066) | 0/12 | TR, TRC, SU, SU-p, SS, SS-p, TRC+SU, TRC+SS, oTRC, oTRC+TR, oTRC+SU-p, oTRC+SS-p | — | RenameContentType._rename() doesn't save the content type on the correct database |
| [django__django-12143](taskD_analysis.md#django__django-12143) | 0/12 | TR, TRC, SU, SU-p, SS, SS-p, TRC+SU, TRC+SS, oTRC, oTRC+TR, oTRC+SU-p, oTRC+SS-p | — | Possible data loss in admin changeform view when using regex special characters in formset prefix |
| [django__django-12276](taskD_analysis.md#django__django-12276) | 0/12 | TR, TRC, SU, SU-p, SS, SS-p, TRC+SU, TRC+SS, oTRC, oTRC+TR, oTRC+SU-p, oTRC+SS-p | — | FileInput shouldn't display required attribute when initial data exists. |
| [django__django-14915](taskD_analysis.md#django__django-14915) | 0/12 | TR, TRC, SU, SU-p, SS, SS-p, TRC+SU, TRC+SS, oTRC, oTRC+TR, oTRC+SU-p, oTRC+SS-p | — | ModelChoiceIteratorValue is not hashable. |
| [django__django-15741](taskD_analysis.md#django__django-15741) | 0/12 | TR, TRC, SU, SU-p, SS, SS-p, TRC+SU, TRC+SS, oTRC, oTRC+TR, oTRC+SU-p, oTRC+SS-p | — | django.utils.formats.get_format should allow lazy parameter |
| [scikit-learn__scikit-learn-10297](taskD_analysis.md#scikit-learn__scikit-learn-10297) | 0/12 | TR, TRC, SU, SU-p, SS, SS-p, TRC+SU, TRC+SS, oTRC, oTRC+TR, oTRC+SU-p, oTRC+SS-p | — | linear_model.RidgeClassifierCV's Parameter store_cv_values issue |
| [scikit-learn__scikit-learn-10844](taskD_analysis.md#scikit-learn__scikit-learn-10844) | 0/12 | TR, TRC, SU, SU-p, SS, SS-p, TRC+SU, TRC+SS, oTRC, oTRC+TR, oTRC+SU-p, oTRC+SS-p | — | fowlkes_mallows_score returns RuntimeWarning when variables get too big |
| [scikit-learn__scikit-learn-12585](taskD_analysis.md#scikit-learn__scikit-learn-12585) | 0/12 | TR, TRC, SU, SU-p, SS, SS-p, TRC+SU, TRC+SS, oTRC, oTRC+TR, oTRC+SU-p, oTRC+SS-p | — | clone fails for parameters that are estimator types |
| [scikit-learn__scikit-learn-13135](taskD_analysis.md#scikit-learn__scikit-learn-13135) | 0/12 | TR, TRC, SU, SU-p, SS, SS-p, TRC+SU, TRC+SS, oTRC, oTRC+TR, oTRC+SU-p, oTRC+SS-p | — | KBinsDiscretizer: kmeans fails due to unsorted bin_edges |
| [scikit-learn__scikit-learn-13142](taskD_analysis.md#scikit-learn__scikit-learn-13142) | 0/12 | TR, TRC, SU, SU-p, SS, SS-p, TRC+SU, TRC+SS, oTRC, oTRC+TR, oTRC+SU-p, oTRC+SS-p | — | GaussianMixture predict and fit_predict disagree when n_init>1 |
| [scikit-learn__scikit-learn-13439](taskD_analysis.md#scikit-learn__scikit-learn-13439) | 0/12 | TR, TRC, SU, SU-p, SS, SS-p, TRC+SU, TRC+SS, oTRC, oTRC+TR, oTRC+SU-p, oTRC+SS-p | — | Pipeline should implement __len__ |
| [scikit-learn__scikit-learn-14141](taskD_analysis.md#scikit-learn__scikit-learn-14141) | 0/12 | TR, TRC, SU, SU-p, SS, SS-p, TRC+SU, TRC+SS, oTRC, oTRC+TR, oTRC+SU-p, oTRC+SS-p | — | Add joblib in show_versions |
| [scikit-learn__scikit-learn-14894](taskD_analysis.md#scikit-learn__scikit-learn-14894) | 0/12 | TR, TRC, SU, SU-p, SS, SS-p, TRC+SU, TRC+SS, oTRC, oTRC+TR, oTRC+SU-p, oTRC+SS-p | — | ZeroDivisionError in _sparse_fit for SVM with empty support_vectors_ |
| [sympy__sympy-15349](taskD_analysis.md#sympy__sympy-15349) | 0/12 | TR, TRC, SU, SU-p, SS, SS-p, TRC+SU, TRC+SS, oTRC, oTRC+TR, oTRC+SU-p, oTRC+SS-p | — | Incorrect result with Quaterniont.to_rotation_matrix() |
| [sympy__sympy-16450](taskD_analysis.md#sympy__sympy-16450) | 0/12 | TR, TRC, SU, SU-p, SS, SS-p, TRC+SU, TRC+SS, oTRC, oTRC+TR, oTRC+SU-p, oTRC+SS-p | — | Posify ignores is_finite assmptions |
| [sympy__sympy-18189](taskD_analysis.md#sympy__sympy-18189) | 0/12 | TR, TRC, SU, SU-p, SS, SS-p, TRC+SU, TRC+SS, oTRC, oTRC+TR, oTRC+SU-p, oTRC+SS-p | — | diophantine: incomplete results depending on syms order with permute=True |
| [sympy__sympy-19954](taskD_analysis.md#sympy__sympy-19954) | 0/12 | TR, TRC, SU, SU-p, SS, SS-p, TRC+SU, TRC+SS, oTRC, oTRC+TR, oTRC+SU-p, oTRC+SS-p | — | sylow_subgroup() IndexError |
| [sympy__sympy-24213](taskD_analysis.md#sympy__sympy-24213) | 0/12 | TR, TRC, SU, SU-p, SS, SS-p, TRC+SU, TRC+SS, oTRC, oTRC+TR, oTRC+SU-p, oTRC+SS-p | — | collect_factor_and_dimension does not detect equivalent dimensions in addition |
| [sympy__sympy-24661](taskD_analysis.md#sympy__sympy-24661) | 0/12 | TR, TRC, SU, SU-p, SS, SS-p, TRC+SU, TRC+SS, oTRC, oTRC+TR, oTRC+SU-p, oTRC+SS-p | — | The evaluate=False parameter to `parse_expr` is ignored for relationals |
