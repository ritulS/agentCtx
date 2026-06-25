# Depth-axis paired analysis (RQ5 / RQ5b)

## §1 Primitive × depth resolve rates @ 15k

Each cell = mean over 200 (task, run) records (100 tasks × 2 runs).

| primitive          | depth=0.3 | depth=0.5 | depth=0.7 |
|--------------------|----------:|----------:|----------:|
| TR                 | 39.5% (n=100) | 38.5% (n=100) | 45.0% (n=100) |
| SU-full            | 40.5% (n=100) | 29.0% (n=100) | 36.0% (n=100) |
| SU-partial         | 45.5% (n=100) | 43.5% (n=100) | 40.5% (n=100) |
| SS                 | 39.5% (n=100) | 36.0% (n=100) | 37.0% (n=100) |
| SS-partial         | 40.0% (n=100) | 38.0% (n=100) | 41.5% (n=100) |
| OTRC+TR            | 44.0% (n=100) | 44.5% (n=100) | 40.0% (n=100) |
| OTRC+SU-partial    | 39.5% (n=100) | 39.5% (n=100) | 36.5% (n=100) |
| OTRC+SS-partial    | 41.5% (n=100) | 42.0% (n=100) | 38.5% (n=100) |

## §2 RQ5 — SU-partial vs SU-full at each depth (paired @ 15k)

Within-depth McNemar + paired bootstrap CI. Positive Δ = SU-partial > SU-full.

| comparison                                       |   n | rateA | rateB |   Δpp |       95% CI | b/c    |  p     |
|--------------------------------------------------|----:|------:|------:|------:|-------------:|:-------|:-------|
| SU-partial vs SU-full @ depth=0.3 @ 15k          | 100 |  45.5% |  40.5% |  +5.0 | [ -2.0, +11.5] |  11/9   | 0.824  |
| SU-partial vs SU-full @ depth=0.5 @ 15k          | 100 |  43.5% |  29.0% | +14.5 | [ +6.5, +22.0] |  21/5   | 0.002* |
| SU-partial vs SU-full @ depth=0.7 @ 15k          | 100 |  40.5% |  36.0% |  +4.5 | [ -2.5, +11.5] |  13/9   | 0.523  |

**Depth-lever read:** the SU-partial − SU-full gap by depth at 15k = +5.0pp (depth=0.3), +14.5pp (depth=0.5), +4.5pp (depth=0.7).

### §2b SU-partial vs SU-full at tail depths @ 10k

| comparison                                       |   n | rateA | rateB |   Δpp |       95% CI | b/c    |  p     |
|--------------------------------------------------|----:|------:|------:|------:|-------------:|:-------|:-------|
| SU-partial vs SU-full @ depth=0.3 @ 10k (P100)   | 100 |  33.0% |  31.5% |  +1.5 | [ -5.5,  +8.5] |  10/9   | 1.000  |
| SU-partial vs SU-full @ depth=0.7 @ 10k (ABL-30) |  30 |  45.0% |  38.3% |  +6.7 | [ -5.0, +20.0] |   5/0   | 0.062  |

## §3 RQ5b — Stacking lift (OTRC + partial-summary) across depths @ 15k

OTRC+SS-partial vs SS-partial isolates the OTRC online-clearing contribution
on top of partial-summary. Positive Δ = OTRC adds lift over bare SS-partial.

| comparison                                       |   n | rateA | rateB |   Δpp |       95% CI | b/c    |  p     |
|--------------------------------------------------|----:|------:|------:|------:|-------------:|:-------|:-------|
| OTRC+SS-partial vs SS-partial @ depth=0.3 @ 15k  | 100 |  41.5% |  40.0% |  +1.5 | [ -5.0,  +8.0] |   8/9   | 1.000  |
| OTRC+SS-partial vs SS-partial @ depth=0.5 @ 15k  | 100 |  42.0% |  38.0% |  +4.0 | [ -3.5, +11.5] |  12/8   | 0.503  |
| OTRC+SS-partial vs SS-partial @ depth=0.7 @ 15k  | 100 |  38.5% |  41.5% |  -3.0 | [-10.5,  +4.0] |   5/8   | 0.581  |

**Stacking-lift read:** OTRC+SS-partial − SS-partial gap by depth = +1.5pp (depth=0.3), +4.0pp (depth=0.5), -3.0pp (depth=0.7).

### §3b Inner-primitive lever (OTRC+SS-partial vs OTRC+TR) by depth @ 15k

Positive Δ = stacking SS-partial inside OTRC beats stacking bare TR.

| comparison                                       |   n | rateA | rateB |   Δpp |       95% CI | b/c    |  p     |
|--------------------------------------------------|----:|------:|------:|------:|-------------:|:-------|:-------|
| OTRC+SS-partial vs OTRC+TR @ depth=0.3 @ 15k     | 100 |  41.5% |  44.0% |  -2.5 | [ -9.5,  +4.5] |   7/9   | 0.804  |
| OTRC+SS-partial vs OTRC+TR @ depth=0.5 @ 15k     | 100 |  42.0% |  44.5% |  -2.5 | [ -8.5,  +3.5] |   6/10  | 0.454  |
| OTRC+SS-partial vs OTRC+TR @ depth=0.7 @ 15k     | 100 |  38.5% |  40.0% |  -1.5 | [ -8.0,  +5.5] |   9/13  | 0.523  |

## §4 Within-primitive depth comparisons @ 15k (Δ = tight − loose)

Asks: holding primitive fixed, does cranking depth down (more aggressive
compression) help or hurt? Positive Δ = depth=0.3 beats depth=0.7.

| primitive            |   n | rate@0.3 | rate@0.7 |   Δpp |       95% CI | b/c    |  p     |
|----------------------|----:|---------:|---------:|------:|-------------:|:-------|:-------|
| TR                   | 100 |    39.5% |    45.0% |  -5.5 | [-11.5,  +0.5] |   4/9   | 0.267  |
| SU-full              | 100 |    40.5% |    36.0% |  +4.5 | [ -2.5, +11.5] |  14/9   | 0.405  |
| SU-partial           | 100 |    45.5% |    40.5% |  +5.0 | [ -1.5, +11.5] |  10/7   | 0.629  |
| SS                   | 100 |    39.5% |    37.0% |  +2.5 | [ -4.5,  +9.0] |  11/10  | 1.000  |
| SS-partial           | 100 |    40.0% |    41.5% |  -1.5 | [ -8.0,  +4.5] |   7/6   | 1.000  |
| OTRC+TR              | 100 |    44.0% |    40.0% |  +4.0 | [ -3.5, +11.5] |  10/9   | 1.000  |
| OTRC+SU-partial      | 100 |    39.5% |    36.5% |  +3.0 | [ -4.0, +10.0] |  10/10  | 1.000  |
| OTRC+SS-partial      | 100 |    41.5% |    38.5% |  +3.0 | [ -4.0, +10.0] |   9/6   | 0.607  |

