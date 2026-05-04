# Paired-analysis follow-up to F8


## Headline paired comparisons

Each row: paired bootstrap CI on the per-task difference (A − B) on the same 30 tasks,
plus McNemar exact test on per-task best-of-2 outcome.

```
comparison                                                 A%    B%    Δpp  paired 95% CI        McN p note      
------------------------------------------------------------------------------------------------------------------------
Best stacked vs best single @ 20k                         77%   72%  +5.0pp  [-5.0, +16.7]pp     0.250  (3 A>B, 0 B>A)
TRC+SU vs OTRC+SU-partial @ 15k (both 65%)                65%   65%  +0.0pp  [-10.0, +8.3]pp     1.000  (2 A>B, 1 B>A)
TR vs SU-full @ 15k (the silent-crash story)              33%   23% +10.0pp  [+0.0, +21.7]pp     0.375  (4 A>B, 1 B>A)
TRC+SS vs TRC @ 15k                                       58%   52%  +6.7pp  [-13.3, +26.7]pp    0.549  (7 A>B, 4 B>A)
SU-partial vs SU-full @ 15k (does partial help?)          57%   23% +33.3pp  [+15.0, +51.7]pp    0.003* (12 A>B, 1 B>A)
OTRC+TR vs OTRC @ ∞ (does adding budget hurt?)            55%   62%  -6.7pp  [-18.3, +5.0]pp     1.000  (2 A>B, 2 B>A)
FC vs TRC+SS @ 20k (no-compression vs best stacked)       38%   77% -38.3pp  [-51.7, -25.0]pp    0.001* (0 A>B, 11 B>A)
OTRC+SS-partial vs SS-partial @ 20k (does OTRC help SS-partial?)   65%   65%  +0.0pp  [-13.3, +13.3]pp    1.000  (1 A>B, 2 B>A)
```

* = paired 95% CI excludes zero (significant at α=0.05).

## Unpaired vs paired CI half-widths at 15k

```
primitive             res% unpaired CI          ± hw  paired Δ vs FC      ± hw_paired
----------------------------------------------------------------------------------------
TR                     33% [21.7, 45.0] 11.7pp   -5.0 [-18.3,  +6.7]        12.5pp
SU-full                23% [13.3, 35.0] 10.8pp  -15.0 [-26.7,  -3.3]        11.7pp
SU-partial             57% [45.0, 68.3] 11.7pp  +18.3 [ -1.7, +38.3]        20.0pp
SS                     30% [18.3, 41.7] 11.7pp   -8.3 [-20.0,  +3.3]        11.7pp
SS-partial             53% [40.0, 65.0] 12.5pp  +15.0 [ -3.3, +33.3]        18.3pp
TRC                    52% [38.3, 65.0] 13.3pp  +13.3 [ +5.0, +23.3]         9.2pp
TRC+SU                 65% [51.7, 76.7] 12.5pp  +26.7 [ +8.3, +45.0]        18.3pp
TRC+SS                 58% [45.0, 70.0] 12.5pp  +20.0 [ +1.7, +38.3]        18.3pp
OTRC+TR                55% [41.7, 68.3] 13.3pp  +16.7 [ -5.0, +36.7]        20.8pp
OTRC+SU-partial        65% [53.3, 76.7] 11.7pp  +26.7 [ +6.7, +45.0]        19.2pp
OTRC+SS-partial        52% [40.0, 65.0] 12.5pp  +13.3 [ -6.7, +33.3]        20.0pp
```

## Pairwise significance grid at 15k (McNemar exact p-value)

Δ (row − col), in pp; cells with McNemar p < 0.05 marked with *.

```
                      TR  SU-full  SU-part       SS  SS-part      TRC   TRC+SU   TRC+SS  OTRC+TR  OTRC+SU  OTRC+SS
------------------------------------------------------------------------------------------------------------------
TR                   -      +10      -23       +3      -20      -18      -32      -25      -22      -32      -18  
SU-full            -10        -      -33*      -7      -30*     -28*     -42*     -35*     -32*     -42*     -28  
SU-partial         +23      +33*       -      +27*      +3       +5       -8       -2       +2       -8       +5  
SS                  -3       +7      -27*       -      -23      -22      -35*     -28      -25      -35*     -22  
SS-partial         +20      +30*      -3      +23        -       +2      -12       -5       -2      -12       +2  
TRC                +18      +28*      -5      +22       -2        -      -13       -7       -3      -13       +0  
TRC+SU             +32      +42*      +8      +35*     +12      +13        -       +7      +10       +0      +13  
TRC+SS             +25      +35*      +2      +28       +5       +7       -7        -       +3       -7       +7  
OTRC+TR            +22      +32*      -2      +25       +2       +3      -10       -3        -      -10       +3  
OTRC+SU-partial    +32      +42*      +8      +35*     +12      +13       +0       +7      +10        -      +13  
OTRC+SS-partial    +18      +28       -5      +22       -2       +0      -13       -7       -3      -13        -  
```

Of 55 pairwise comparisons at 15k, 10 are significant at α=0.05 by McNemar.