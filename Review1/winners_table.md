# Per-task efficiency winner — by budget

Among primitives that resolved each task, which uses the fewest tokens?

FC and OTRC always at ∞. Cost = mean total tokens across resolving runs only.


## Budget = 10k

| task | # prims resolved | winner (tokens) | runner-up (tokens) | margin | verdict |
|---|---:|---|---|---:|---|
| `django__django-11066` | 13 | OTRC+TR (22k) | TRC+SU (25k) | 2k | **OTRC+TR** |
| `django__django-11292` | 12 | OTRC+SU-partial (94k) | OTRC+SS-partial (128k) | 33k | **OTRC+SU-partial** |
| `django__django-11299` | 6 | TR (217k) | SS-partial (248k) | 31k | **TR** |
| `django__django-12273` | 0 | — | — | — | no primitive resolved |
| `django__django-13012` | 7 | TR (223k) | OTRC+TR (236k) | 13k | **TR** |
| `django__django-13964` | 3 | OTRC+SS-partial (346k) | TRC+SS (623k) | 277k | **OTRC+SS-partial** |
| `django__django-14580` | 11 | SS (248k) | OTRC+SU-partial (273k) | 25k | **SS** |
| `django__django-14915` | 13 | OTRC+TR (81k) | SU-full (90k) | 9k | **OTRC+TR** |
| `django__django-14999` | 3 | TRC+SS (164k) | TRC+SU (383k) | 219k | **TRC+SS** |
| `django__django-17087` | 12 | SS (118k) | FC (145k) | 27k | **SS** |
| `scikit-learn__scikit-learn-10297` | 10 | OTRC+SU-partial (236k) | SS-partial (247k) | 12k | **OTRC+SU-partial** |
| `scikit-learn__scikit-learn-10908` | 4 | OTRC+SU-partial (311k) | OTRC+TR (383k) | 72k | **OTRC+SU-partial** |
| `scikit-learn__scikit-learn-11310` | 3 | OTRC+SU-partial (322k) | TRC+SS (496k) | 174k | **OTRC+SU-partial** |
| `scikit-learn__scikit-learn-11578` | 6 | SS (254k) | SU-full (507k) | 253k | **SS** |
| `scikit-learn__scikit-learn-13328` | 7 | TRC+SS (325k) | OTRC+SS-partial (344k) | 18k | **TRC+SS** |
| `scikit-learn__scikit-learn-13779` | 9 | TRC (196k) | SU-partial (245k) | 49k | **TRC** |
| `scikit-learn__scikit-learn-14496` | 11 | SS (114k) | OTRC+SS-partial (124k) | 9k | **SS** |
| `scikit-learn__scikit-learn-15100` | 12 | SS-partial (114k) | TRC+SS (118k) | 4k | **SS-partial** |
| `scikit-learn__scikit-learn-25747` | 0 | — | — | — | no primitive resolved |
| `scikit-learn__scikit-learn-26323` | 8 | OTRC+SU-partial (273k) | SS (296k) | 22k | **OTRC+SU-partial** |
| `sympy__sympy-11618` | 13 | OTRC+TR (148k) | TRC (177k) | 29k | **OTRC+TR** |
| `sympy__sympy-13031` | 2 | OTRC+TR (328k) | TR (742k) | 414k | **OTRC+TR** |
| `sympy__sympy-13091` | 0 | — | — | — | no primitive resolved |
| `sympy__sympy-13757` | 7 | OTRC+TR (322k) | TRC+SU (436k) | 114k | **OTRC+TR** |
| `sympy__sympy-15017` | 10 | OTRC+SU-partial (135k) | SU-partial (160k) | 24k | **OTRC+SU-partial** |
| `sympy__sympy-15345` | 8 | OTRC+SS-partial (313k) | SS-partial (341k) | 28k | **OTRC+SS-partial** |
| `sympy__sympy-17630` | 0 | — | — | — | no primitive resolved |
| `sympy__sympy-19637` | 12 | SS-partial (100k) | OTRC+SU-partial (122k) | 21k | **SS-partial** |
| `sympy__sympy-24066` | 13 | OTRC+SS-partial (102k) | OTRC+SU-partial (124k) | 22k | **OTRC+SS-partial** |
| `sympy__sympy-24443` | 11 | SS (111k) | SS-partial (138k) | 27k | **SS** |

**Summary @ 10k:** 26/30 unambiguous winner · 0/30 no clear winner · 4/30 unresolved.

**Winner distribution @ 10k:**
- OTRC+SU-partial: 6
- OTRC+TR: 5
- SS: 5
- OTRC+SS-partial: 3
- TR: 2
- TRC+SS: 2
- SS-partial: 2
- TRC: 1

## Budget = 15k

| task | # prims resolved | winner (tokens) | runner-up (tokens) | margin | verdict |
|---|---:|---|---|---:|---|
| `django__django-11066` | 13 | SS (24k) | SU-partial (25k) | 1k | **SS** |
| `django__django-11292` | 13 | OTRC+SS-partial (207k) | FC (215k) | 8k | **OTRC+SS-partial** |
| `django__django-11299` | 10 | SU-full (529k) | SS (537k) | 8k | **SU-full** |
| `django__django-12273` | 0 | — | — | — | no primitive resolved |
| `django__django-13012` | 8 | OTRC+SU-partial (295k) | SS-partial (317k) | 22k | **OTRC+SU-partial** |
| `django__django-13964` | 5 | OTRC+SU-partial (300k) | TRC+SU (385k) | 85k | **OTRC+SU-partial** |
| `django__django-14580` | 8 | OTRC+SU-partial (320k) | SS (409k) | 89k | **OTRC+SU-partial** |
| `django__django-14915` | 13 | OTRC+SS-partial (73k) | OTRC+SU-partial (74k) | 1k | **OTRC+SS-partial** |
| `django__django-14999` | 4 | SU-partial (276k) | TRC+SU (412k) | 136k | **SU-partial** |
| `django__django-17087` | 13 | OTRC+SU-partial (132k) | OTRC+TR (143k) | 11k | **OTRC+SU-partial** |
| `scikit-learn__scikit-learn-10297` | 12 | OTRC+TR (242k) | SS (359k) | 117k | **OTRC+TR** |
| `scikit-learn__scikit-learn-10908` | 9 | OTRC+SS-partial (430k) | TR (437k) | 7k | **OTRC+SS-partial** |
| `scikit-learn__scikit-learn-11310` | 7 | OTRC+TR (358k) | SS (416k) | 58k | **OTRC+TR** |
| `scikit-learn__scikit-learn-11578` | 11 | OTRC+SS-partial (403k) | OTRC+TR (417k) | 14k | **OTRC+SS-partial** |
| `scikit-learn__scikit-learn-13328` | 8 | OTRC+SU-partial (280k) | TRC+SU (373k) | 94k | **OTRC+SU-partial** |
| `scikit-learn__scikit-learn-13779` | 12 | OTRC+SS-partial (172k) | SS-partial (247k) | 76k | **OTRC+SS-partial** |
| `scikit-learn__scikit-learn-14496` | 8 | OTRC+TR (143k) | OTRC+SS-partial (170k) | 27k | **OTRC+TR** |
| `scikit-learn__scikit-learn-15100` | 8 | SS-partial (103k) | OTRC+SS-partial (109k) | 6k | **SS-partial** |
| `scikit-learn__scikit-learn-25747` | 2 | SU-partial (516k) | TRC (827k) | 311k | **SU-partial** |
| `scikit-learn__scikit-learn-26323` | 8 | TRC+SS (395k) | SU-partial (431k) | 37k | **TRC+SS** |
| `sympy__sympy-11618` | 13 | OTRC+SS-partial (165k) | OTRC+SU-partial (169k) | 3k | **OTRC+SS-partial** |
| `sympy__sympy-13031` | 1 | TR (900k) | — | — | **TR** |
| `sympy__sympy-13091` | 0 | — | — | — | no primitive resolved |
| `sympy__sympy-13757` | 2 | OTRC (866k) | FC (1442k) | 576k | **OTRC** |
| `sympy__sympy-15017` | 7 | OTRC (177k) | OTRC+TR (184k) | 7k | **OTRC** |
| `sympy__sympy-15345` | 10 | TRC+SU (326k) | SU-partial (550k) | 225k | **TRC+SU** |
| `sympy__sympy-17630` | 0 | — | — | — | no primitive resolved |
| `sympy__sympy-19637` | 8 | OTRC+SU-partial (77k) | OTRC+SS-partial (121k) | 44k | **OTRC+SU-partial** |
| `sympy__sympy-24066` | 12 | OTRC+SS-partial (97k) | OTRC+SU-partial (144k) | 47k | **OTRC+SS-partial** |
| `sympy__sympy-24443` | 8 | OTRC+SS-partial (110k) | OTRC (163k) | 53k | **OTRC+SS-partial** |

**Summary @ 15k:** 27/30 unambiguous winner · 0/30 no clear winner · 3/30 unresolved.

**Winner distribution @ 15k:**
- OTRC+SS-partial: 8
- OTRC+SU-partial: 6
- OTRC+TR: 3
- SU-partial: 2
- OTRC: 2
- SS: 1
- SU-full: 1
- SS-partial: 1
- TRC+SS: 1
- TR: 1
- TRC+SU: 1

## Budget = 20k

| task | # prims resolved | winner (tokens) | runner-up (tokens) | margin | verdict |
|---|---:|---|---|---:|---|
| `django__django-11066` | 13 | TR (24k) | OTRC+SS-partial (29k) | 4k | **TR** |
| `django__django-11292` | 13 | OTRC+SS-partial (123k) | OTRC+SU-partial (208k) | 85k | **OTRC+SS-partial** |
| `django__django-11299` | 11 | TR (596k) | TRC+SS (600k) | 4k | **TR** |
| `django__django-12273` | 0 | — | — | — | no primitive resolved |
| `django__django-13012` | 11 | OTRC+SS-partial (257k) | TRC (361k) | 103k | **OTRC+SS-partial** |
| `django__django-13964` | 9 | OTRC+SU-partial (223k) | OTRC+SS-partial (366k) | 144k | **OTRC+SU-partial** |
| `django__django-14580` | 13 | OTRC+TR (181k) | SS (421k) | 239k | **OTRC+TR** |
| `django__django-14915` | 13 | FC (98k) | OTRC+SU-partial (118k) | 20k | **FC** |
| `django__django-14999` | 4 | SU-full (737k) | TRC+SU (770k) | 33k | **SU-full** |
| `django__django-17087` | 13 | OTRC+SS-partial (119k) | FC (145k) | 26k | **OTRC+SS-partial** |
| `scikit-learn__scikit-learn-10297` | 13 | OTRC+SS-partial (347k) | TRC+SS (421k) | 74k | **OTRC+SS-partial** |
| `scikit-learn__scikit-learn-10908` | 10 | OTRC+TR (494k) | OTRC+SU-partial (557k) | 63k | **OTRC+TR** |
| `scikit-learn__scikit-learn-11310` | 8 | OTRC+TR (641k) | SS-partial (735k) | 95k | **OTRC+TR** |
| `scikit-learn__scikit-learn-11578` | 13 | OTRC+TR (273k) | SU-full (396k) | 123k | **OTRC+TR** |
| `scikit-learn__scikit-learn-13328` | 11 | OTRC (433k) | OTRC+SS-partial (474k) | 40k | **OTRC** |
| `scikit-learn__scikit-learn-13779` | 13 | OTRC+SS-partial (255k) | SS-partial (402k) | 146k | **OTRC+SS-partial** |
| `scikit-learn__scikit-learn-14496` | 12 | OTRC+TR (124k) | OTRC+SU-partial (127k) | 4k | **OTRC+TR** |
| `scikit-learn__scikit-learn-15100` | 12 | TRC+SS (98k) | TRC (105k) | 6k | **TRC+SS** |
| `scikit-learn__scikit-learn-25747` | 1 | TRC+SS (669k) | — | — | **TRC+SS** |
| `scikit-learn__scikit-learn-26323` | 11 | OTRC+SU-partial (514k) | OTRC+TR (595k) | 81k | **OTRC+SU-partial** |
| `sympy__sympy-11618` | 13 | OTRC+SU-partial (184k) | OTRC+TR (192k) | 8k | **OTRC+SU-partial** |
| `sympy__sympy-13031` | 0 | — | — | — | no primitive resolved |
| `sympy__sympy-13091` | 2 | OTRC+SU-partial (1153k) | TR (1189k) | 36k | **OTRC+SU-partial** |
| `sympy__sympy-13757` | 4 | TRC (668k) | OTRC (866k) | 198k | **TRC** |
| `sympy__sympy-15017` | 10 | OTRC+SS-partial (135k) | OTRC+TR (168k) | 32k | **OTRC+SS-partial** |
| `sympy__sympy-15345` | 13 | OTRC+SS-partial (374k) | OTRC+TR (533k) | 160k | **OTRC+SS-partial** |
| `sympy__sympy-17630` | 0 | — | — | — | no primitive resolved |
| `sympy__sympy-19637` | 12 | OTRC+TR (75k) | TRC+SS (104k) | 29k | **OTRC+TR** |
| `sympy__sympy-24066` | 11 | OTRC+TR (170k) | OTRC+SU-partial (192k) | 23k | **OTRC+TR** |
| `sympy__sympy-24443` | 12 | OTRC (163k) | OTRC+TR (189k) | 26k | **OTRC** |

**Summary @ 20k:** 27/30 unambiguous winner · 0/30 no clear winner · 3/30 unresolved.

**Winner distribution @ 20k:**
- OTRC+SS-partial: 7
- OTRC+TR: 7
- OTRC+SU-partial: 4
- TR: 2
- OTRC: 2
- TRC+SS: 2
- FC: 1
- SU-full: 1
- TRC: 1


## Cross-budget comparison

| budget | unambig winner | no clear winner | unresolved |
|---|---:|---:|---:|
| 10k | 26/30 | 0/30 | 4/30 |
| 15k | 27/30 | 0/30 | 3/30 |
| 20k | 27/30 | 0/30 | 3/30 |

### Winner counts side-by-side
| primitive | 10k | 15k | 20k |
|---|---:|---:|---:|
| FC | 0 | 0 | 1 |
| OTRC | 0 | 2 | 2 |
| OTRC+SS-partial | 3 | 8 | 7 |
| OTRC+SU-partial | 6 | 6 | 4 |
| OTRC+TR | 5 | 3 | 7 |
| SS | 5 | 1 | 0 |
| SS-partial | 2 | 1 | 0 |
| SU-full | 0 | 1 | 1 |
| SU-partial | 0 | 2 | 0 |
| TR | 2 | 1 | 2 |
| TRC | 1 | 0 | 1 |
| TRC+SS | 2 | 1 | 2 |
| TRC+SU | 0 | 1 | 0 |
