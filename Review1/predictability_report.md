# Predictability sprint Phase 1

Can a controller pick the right primitive from observables alone?


## Budget 10k: TR vs TRC+SS

- Tasks where TR > TRC+SS: **13**
- Tasks where TRC+SS > TR: **21**
- Ties dropped: 66

### Univariate feature tests
| feature | mean(TR-wins) | mean(other-wins) | p (Mann-Whitney) |
| --- | ---: | ---: | ---: |
| n_urls | 0.08 | 0.90 | 0.082 |
| is_sympy | 0.46 | 0.24 | 0.190 |
| is_sklearn | 0.23 | 0.43 | 0.257 |
| len_lines | 35.46 | 34.90 | 0.329 |
| len_words | 183.38 | 174.48 | 0.339 |
| n_code_blocks | 1.77 | 1.10 | 0.346 |
| n_inline_code | 2.54 | 3.29 | 0.409 |
| len_chars | 1438.85 | 1533.10 | 0.547 |
| n_py_paths | 2.77 | 0.52 | 0.847 |
| n_tests | 0.08 | 0.52 | 0.857 |
| n_traceback | 0.23 | 0.14 | 0.885 |
| is_django | 0.31 | 0.33 | 0.896 |
| is_astropy | 0.00 | 0.00 | 1.000 |

### Leave-one-out logistic regression

- LOO accuracy: **64.7%**  (n=34)
- Majority-class baseline: 61.8%
- **Verdict:** NOT separable (++2.9pp over baseline)

## Budget 15k: TR vs SU-partial

- Tasks where TR > SU-partial: **18**
- Tasks where SU-partial > TR: **22**
- Ties dropped: 60

### Univariate feature tests
| feature | mean(TR-wins) | mean(other-wins) | p (Mann-Whitney) |
| --- | ---: | ---: | ---: |
| n_urls | 0.44 | 0.86 | 0.087 |
| n_py_paths | 1.33 | 1.64 | 0.087 |
| n_traceback | 0.11 | 0.36 | 0.120 |
| is_sympy | 0.50 | 0.27 | 0.149 |
| is_sklearn | 0.28 | 0.45 | 0.263 |
| n_inline_code | 2.39 | 3.45 | 0.281 |
| len_words | 158.72 | 192.14 | 0.289 |
| len_chars | 1397.94 | 1753.95 | 0.308 |
| n_tests | 0.61 | 0.05 | 0.439 |
| n_code_blocks | 1.39 | 1.95 | 0.576 |
| is_django | 0.22 | 0.27 | 0.731 |
| len_lines | 35.33 | 42.68 | 0.881 |
| is_astropy | 0.00 | 0.00 | 1.000 |

### Leave-one-out logistic regression

- LOO accuracy: **45.0%**  (n=40)
- Majority-class baseline: 55.0%
- **Verdict:** NOT separable (-10.0pp over baseline)

## Budget 20k: TR vs TRC+SS

- Tasks where TR > TRC+SS: **8**
- Tasks where TRC+SS > TR: **20**
- Ties dropped: 72

### Univariate feature tests
| feature | mean(TR-wins) | mean(other-wins) | p (Mann-Whitney) |
| --- | ---: | ---: | ---: |
| **is_sympy** | 0.75 | 0.20 | 0.008** |
| is_django | 0.00 | 0.30 | 0.093 |
| is_sklearn | 0.25 | 0.50 | 0.248 |
| n_py_paths | 2.88 | 1.25 | 0.351 |
| n_urls | 0.88 | 0.80 | 0.379 |
| n_inline_code | 8.00 | 3.45 | 0.430 |
| n_tests | 0.12 | 0.05 | 0.531 |
| n_code_blocks | 1.38 | 1.45 | 0.635 |
| len_lines | 35.00 | 47.00 | 0.741 |
| len_chars | 1464.25 | 1804.25 | 0.746 |
| len_words | 173.75 | 194.20 | 0.939 |
| n_traceback | 0.25 | 0.25 | 1.000 |
| is_astropy | 0.00 | 0.00 | 1.000 |

### Leave-one-out logistic regression

- LOO accuracy: **42.9%**  (n=28)
- Majority-class baseline: 71.4%
- **Verdict:** NOT separable (-28.6pp over baseline)

## Pooled: TR-friendly vs compression-friendly tasks (pan-budget)

A task is 'TR-friendly' if TR's mean rate across budgets > best-compression's.
- TR-friendly (TR ≥ best compressor on average): **35** tasks
- compression-friendly: **65** tasks

### Univariate (pooled)
| feature | mean(TR-friendly) | mean(comp-friendly) | p |
| --- | ---: | ---: | ---: |
| **n_inline_code** | 2.51 | 3.51 | 0.028** |
| **n_code_blocks** | 0.86 | 1.63 | 0.034** |
| is_sklearn | 0.20 | 0.38 | 0.061 |
| is_django | 0.43 | 0.29 | 0.174 |
| len_lines | 40.03 | 40.94 | 0.556 |
| n_tests | 0.29 | 0.37 | 0.607 |
| n_traceback | 0.43 | 0.31 | 0.621 |
| is_sympy | 0.37 | 0.32 | 0.631 |
| len_chars | 1901.94 | 1694.97 | 0.662 |
| n_urls | 1.00 | 0.80 | 0.841 |
| len_words | 213.66 | 189.68 | 0.908 |
| n_py_paths | 2.60 | 1.83 | 0.975 |
| is_astropy | 0.00 | 0.00 | 1.000 |

### Leave-one-out logistic regression (pooled)
- LOO accuracy: **51.0%**  (n=100)
- Majority-class baseline: 65.0%
- **Verdict:** NOT separable (-14.0pp over baseline)