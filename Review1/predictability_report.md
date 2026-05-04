# Predictability sprint Phase 1

Can a controller pick the right primitive from observables alone?


## Budget 10k: TR vs TRC+SS

- Tasks where TR > TRC+SS: **5**
- Tasks where TRC+SS > TR: **10**
- Ties dropped: 15

### Univariate feature tests
| feature | mean(TR-wins) | mean(other-wins) | p (Mann-Whitney) |
| --- | ---: | ---: | ---: |
| **is_sklearn** | 0.00 | 0.60 | 0.037** |
| n_inline_code | 0.60 | 3.80 | 0.144 |
| is_sympy | 0.40 | 0.10 | 0.217 |
| n_urls | 0.00 | 1.00 | 0.220 |
| is_django | 0.60 | 0.30 | 0.313 |
| n_tests | 0.00 | 1.10 | 0.352 |
| n_traceback | 0.00 | 0.10 | 0.572 |
| n_code_blocks | 0.80 | 0.90 | 0.694 |
| len_lines | 32.00 | 41.10 | 0.902 |
| len_chars | 1402.20 | 1764.20 | 0.953 |
| len_words | 167.00 | 207.10 | 1.000 |
| n_py_paths | 0.60 | 0.50 | 1.000 |
| is_astropy | 0.00 | 0.00 | 1.000 |

### Leave-one-out logistic regression

- LOO accuracy: **53.3%**  (n=15)
- Majority-class baseline: 66.7%
- **Verdict:** NOT separable (-13.3pp over baseline)

## Budget 15k: TR vs SU-partial

- Tasks where TR > SU-partial: **6**
- Tasks where SU-partial > TR: **13**
- Ties dropped: 11

### Univariate feature tests
| feature | mean(TR-wins) | mean(other-wins) | p (Mann-Whitney) |
| --- | ---: | ---: | ---: |
| is_sklearn | 0.17 | 0.54 | 0.152 |
| n_traceback | 0.00 | 0.31 | 0.154 |
| n_py_paths | 0.67 | 1.92 | 0.203 |
| is_sympy | 0.50 | 0.23 | 0.277 |
| n_code_blocks | 1.00 | 2.00 | 0.321 |
| n_inline_code | 2.83 | 3.38 | 0.344 |
| n_urls | 0.83 | 0.62 | 0.556 |
| n_tests | 1.67 | 0.08 | 0.565 |
| is_django | 0.33 | 0.23 | 0.688 |
| len_chars | 2310.33 | 1925.77 | 0.966 |
| len_words | 261.17 | 197.31 | 1.000 |
| len_lines | 52.83 | 51.31 | 1.000 |
| is_astropy | 0.00 | 0.00 | 1.000 |

### Leave-one-out logistic regression

- LOO accuracy: **63.2%**  (n=19)
- Majority-class baseline: 68.4%
- **Verdict:** NOT separable (-5.3pp over baseline)

## Budget 20k: TR vs TRC+SS

- Tasks where TR > TRC+SS: **2**
- Tasks where TRC+SS > TR: **9**
- Ties dropped: 19

### Univariate feature tests
| feature | mean(TR-wins) | mean(other-wins) | p (Mann-Whitney) |
| --- | ---: | ---: | ---: |
| **n_urls** | 2.00 | 0.11 | 0.016** |
| n_inline_code | 19.50 | 2.89 | 0.117 |
| is_sympy | 1.00 | 0.33 | 0.134 |
| len_lines | 16.50 | 61.78 | 0.145 |
| n_tests | 0.50 | 0.11 | 0.292 |
| n_py_paths | 2.00 | 1.78 | 0.303 |
| is_sklearn | 0.00 | 0.44 | 0.324 |
| n_traceback | 0.00 | 0.22 | 0.598 |
| is_django | 0.00 | 0.22 | 0.598 |
| n_code_blocks | 1.00 | 2.00 | 0.903 |
| len_words | 158.50 | 224.22 | 0.906 |
| len_chars | 1254.00 | 2278.33 | 0.909 |
| is_astropy | 0.00 | 0.00 | 1.000 |

### Leave-one-out logistic regression

- LOO accuracy: **81.8%**  (n=11)
- Majority-class baseline: 81.8%
- **Verdict:** NOT separable (+0.0pp over baseline)

## Pooled: TR-friendly vs compression-friendly tasks (pan-budget)

A task is 'TR-friendly' if TR's mean rate across budgets > best-compression's.
- TR-friendly (TR ≥ best compressor on average): **4** tasks
- compression-friendly: **26** tasks

### Univariate (pooled)
| feature | mean(TR-friendly) | mean(comp-friendly) | p |
| --- | ---: | ---: | ---: |
| is_django | 0.75 | 0.27 | 0.067 |
| n_traceback | 1.00 | 0.15 | 0.087 |
| is_sklearn | 0.00 | 0.38 | 0.145 |
| n_inline_code | 0.75 | 4.12 | 0.214 |
| n_code_blocks | 1.00 | 1.42 | 0.355 |
| n_py_paths | 4.00 | 1.23 | 0.416 |
| n_tests | 0.00 | 0.46 | 0.519 |
| len_chars | 1806.50 | 1788.08 | 0.659 |
| len_words | 186.75 | 194.88 | 0.692 |
| is_sympy | 0.25 | 0.35 | 0.737 |
| len_lines | 33.25 | 44.38 | 0.927 |
| n_urls | 0.75 | 0.62 | 1.000 |
| is_astropy | 0.00 | 0.00 | 1.000 |

### Leave-one-out logistic regression (pooled)
- LOO accuracy: **70.0%**  (n=30)
- Majority-class baseline: 86.7%
- **Verdict:** NOT separable (-16.7pp over baseline)