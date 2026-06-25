# Paired-analysis follow-up to F8


## Headline paired comparisons

Each row: paired bootstrap CI on the per-task difference (A − B) on the same 100 tasks,
plus McNemar exact test on per-task best-of-2 outcome.

```
comparison                                                 A%    B%    Δpp  paired 95% CI        McN p note      
------------------------------------------------------------------------------------------------------------------------
Best stacked vs best single @ 20k                         53%   52%  +1.5pp  [-4.0, +7.5]pp      0.454  (10 A>B, 6 B>A)
TRC+SU vs OTRC+SU-partial @ 15k (both 65%)                47%   40%  +7.5pp  [+2.0, +13.0]pp     0.035* (12 A>B, 3 B>A)
TR vs SU-full @ 15k (the silent-crash story)              38%   29%  +9.5pp  [+4.5, +15.0]pp     0.013* (12 A>B, 2 B>A)
TRC+SS vs TRC @ 15k                                       45%   46%  -0.5pp  [-8.5, +7.5]pp      1.000  (11 A>B, 10 B>A)
SU-partial vs SU-full @ 15k (does partial help?)          44%   29% +14.5pp  [+7.0, +22.5]pp     0.002* (21 A>B, 5 B>A)
OTRC+TR vs OTRC @ ∞ (does adding budget hurt?)            44%   52%  -7.0pp  [-13.0, -1.0]pp     0.607* (6 A>B, 9 B>A)
FC vs TRC+SS @ 20k (no-compression vs best stacked)       43%   53% -10.0pp  [-17.0, -3.0]pp     0.093* (7 A>B, 16 B>A)
OTRC+SS-partial vs SS-partial @ 20k (does OTRC help SS-partial?)   47%   48%  -1.0pp  [-8.0, +6.0]pp      0.607  (6 A>B, 9 B>A)
```

* = paired 95% CI excludes zero (significant at α=0.05).

## Unpaired vs paired CI half-widths at 15k

```
primitive             res% unpaired CI          ± hw  paired Δ vs FC      ± hw_paired
----------------------------------------------------------------------------------------
TR                     38% [31.5, 45.5]  7.0pp   -4.5 [-10.5,  +1.0]         5.8pp
SU-full                29% [22.5, 35.5]  6.5pp  -14.0 [-21.0,  -7.5]         6.8pp
SU-partial             44% [36.5, 50.5]  7.0pp   +0.5 [ -8.0,  +9.5]         8.8pp
SS                     36% [29.5, 43.0]  6.8pp   -7.0 [-13.5,  +0.0]         6.8pp
SS-partial             38% [31.5, 44.5]  6.5pp   -5.0 [-13.5,  +3.5]         8.5pp
TRC                    46% [38.5, 52.5]  7.0pp   +2.5 [ -3.0,  +8.5]         5.8pp
TRC+SU                 47% [40.0, 54.0]  7.0pp   +4.0 [ -4.0, +12.5]         8.3pp
TRC+SS                 45% [38.0, 52.0]  7.0pp   +2.0 [ -5.5,  +9.5]         7.5pp
OTRC+TR                44% [37.5, 51.5]  7.0pp   +1.5 [ -6.5, +10.0]         8.2pp
OTRC+SU-partial        40% [33.0, 46.0]  6.5pp   -3.5 [-11.5,  +5.0]         8.2pp
OTRC+SS-partial        42% [35.0, 48.5]  6.8pp   -1.0 [ -9.0,  +6.5]         7.8pp
```

## Pairwise significance grid at 15k (McNemar exact p-value)

Δ (row − col), in pp; cells with McNemar p < 0.05 marked with *.

```
                      TR  SU-full  SU-part       SS  SS-part      TRC   TRC+SU   TRC+SS  OTRC+TR  OTRC+SU  OTRC+SS
------------------------------------------------------------------------------------------------------------------
TR                   -      +10*      -5       +3       +1       -7       -8       -6       -6       -1       -3  
SU-full            -10*       -      -15*      -7       -9      -17*     -18*     -16*     -16*     -11      -13* 
SU-partial          +5      +15*       -       +8       +5       -2       -3       -2       -1       +4       +2  
SS                  -3       +7       -8        -       -2      -10*     -11*      -9*      -9       -4       -6  
SS-partial          -1       +9       -5       +2        -       -8       -9*      -7       -6       -2       -4  
TRC                 +7      +17*      +2      +10*      +8        -       -1       +1       +1       +6       +4  
TRC+SU              +8      +18*      +3      +11*      +9*      +1        -       +2       +2       +7*      +5  
TRC+SS              +6      +16*      +2       +9*      +7       -1       -2        -       +1       +5       +3  
OTRC+TR             +6      +16*      +1       +9       +6       -1       -2       -1        -       +5       +3  
OTRC+SU-partial     +1      +11       -4       +4       +2       -6       -7*      -5       -5        -       -2  
OTRC+SS-partial     +3      +13*      -2       +6       +4       -4       -5       -3       -3       +2        -  
```

Of 55 pairwise comparisons at 15k, 12 are significant at α=0.05 by McNemar.