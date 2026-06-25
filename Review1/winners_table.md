# Per-task efficiency winner — by budget

Among primitives that resolved each task, which uses the fewest tokens?

FC and OTRC always at ∞. Cost = mean total tokens across resolving runs only.


## Budget = 10k

| task | # prims resolved | winner (tokens) | runner-up (tokens) | margin | verdict |
|---|---:|---|---|---:|---|
| `django__django-11066` | 13 | OTRC+TR (22k) | TRC+SU (25k) | 2k | **OTRC+TR** |
| `django__django-11087` | 0 | — | — | — | no primitive resolved |
| `django__django-11095` | 11 | OTRC+SU-partial (139k) | OTRC+SS-partial (142k) | 3k | **OTRC+SU-partial** |
| `django__django-11292` | 12 | OTRC+SU-partial (94k) | OTRC+SS-partial (128k) | 33k | **OTRC+SU-partial** |
| `django__django-11299` | 6 | TR (217k) | SS-partial (248k) | 31k | **TR** |
| `django__django-11433` | 0 | — | — | — | no primitive resolved |
| `django__django-11477` | 0 | — | — | — | no primitive resolved |
| `django__django-11734` | 0 | — | — | — | no primitive resolved |
| `django__django-12143` | 13 | OTRC+TR (68k) | FC (111k) | 43k | **OTRC+TR** |
| `django__django-12273` | 0 | — | — | — | no primitive resolved |
| `django__django-12276` | 12 | OTRC (119k) | SS-partial (189k) | 70k | **OTRC** |
| `django__django-12304` | 11 | SU-full (116k) | OTRC (117k) | 1k | **SU-full** |
| `django__django-12325` | 1 | TRC (355k) | — | — | **TRC** |
| `django__django-12663` | 0 | — | — | — | no primitive resolved |
| `django__django-13012` | 7 | TR (223k) | OTRC+TR (236k) | 13k | **TR** |
| `django__django-13809` | 12 | TRC+SS (108k) | SU-full (150k) | 42k | **TRC+SS** |
| `django__django-13810` | 6 | TRC+SS (188k) | SU-partial (220k) | 32k | **TRC+SS** |
| `django__django-13964` | 3 | OTRC+SS-partial (346k) | TRC+SS (623k) | 277k | **OTRC+SS-partial** |
| `django__django-14351` | 0 | — | — | — | no primitive resolved |
| `django__django-14580` | 11 | SS (248k) | OTRC+SU-partial (273k) | 25k | **SS** |
| `django__django-14725` | 0 | — | — | — | no primitive resolved |
| `django__django-14915` | 13 | OTRC+TR (81k) | SU-full (90k) | 9k | **OTRC+TR** |
| `django__django-14999` | 3 | TRC+SS (164k) | TRC+SU (383k) | 219k | **TRC+SS** |
| `django__django-15098` | 0 | — | — | — | no primitive resolved |
| `django__django-15278` | 5 | TRC (211k) | SU-full (256k) | 45k | **TRC** |
| `django__django-15368` | 12 | OTRC+SS-partial (125k) | OTRC+SU-partial (165k) | 40k | **OTRC+SS-partial** |
| `django__django-15525` | 2 | SU-full (173k) | SS-partial (347k) | 174k | **SU-full** |
| `django__django-15629` | 0 | — | — | — | no primitive resolved |
| `django__django-15741` | 13 | OTRC+TR (239k) | OTRC+SU-partial (260k) | 20k | **OTRC+TR** |
| `django__django-15930` | 4 | OTRC (574k) | TRC+SS (629k) | 56k | **OTRC** |
| `django__django-15957` | 0 | — | — | — | no primitive resolved |
| `django__django-16667` | 0 | — | — | — | no primitive resolved |
| `django__django-17084` | 3 | TRC+SS (426k) | OTRC (758k) | 332k | **TRC+SS** |
| `django__django-17087` | 12 | SS (118k) | FC (145k) | 27k | **SS** |
| `scikit-learn__scikit-learn-10297` | 10 | OTRC+SU-partial (236k) | SS-partial (247k) | 12k | **OTRC+SU-partial** |
| `scikit-learn__scikit-learn-10844` | 13 | SS (157k) | SS-partial (160k) | 3k | **SS** |
| `scikit-learn__scikit-learn-10908` | 4 | OTRC+SU-partial (311k) | OTRC+TR (383k) | 72k | **OTRC+SU-partial** |
| `scikit-learn__scikit-learn-11310` | 3 | OTRC+SU-partial (322k) | TRC+SS (496k) | 174k | **OTRC+SU-partial** |
| `scikit-learn__scikit-learn-11578` | 6 | SS (254k) | SU-full (507k) | 253k | **SS** |
| `scikit-learn__scikit-learn-12585` | 13 | OTRC+SU-partial (181k) | TRC+SS (198k) | 18k | **OTRC+SU-partial** |
| `scikit-learn__scikit-learn-12682` | 6 | SU-full (177k) | TRC+SU (380k) | 203k | **SU-full** |
| `scikit-learn__scikit-learn-12973` | 4 | OTRC+SU-partial (265k) | OTRC+SS-partial (436k) | 171k | **OTRC+SU-partial** |
| `scikit-learn__scikit-learn-13124` | 0 | — | — | — | no primitive resolved |
| `scikit-learn__scikit-learn-13135` | 10 | SS-partial (202k) | SU-partial (216k) | 14k | **SS-partial** |
| `scikit-learn__scikit-learn-13142` | 9 | TR (263k) | SU-partial (274k) | 10k | **TR** |
| `scikit-learn__scikit-learn-13328` | 7 | TRC+SS (325k) | OTRC+SS-partial (344k) | 18k | **TRC+SS** |
| `scikit-learn__scikit-learn-13439` | 13 | SS (198k) | OTRC (202k) | 4k | **SS** |
| `scikit-learn__scikit-learn-13496` | 11 | OTRC+TR (209k) | TRC+SU (226k) | 17k | **OTRC+TR** |
| `scikit-learn__scikit-learn-13779` | 9 | TRC (196k) | SU-partial (245k) | 49k | **TRC** |
| `scikit-learn__scikit-learn-14053` | 7 | SU-partial (241k) | OTRC+TR (340k) | 99k | **SU-partial** |
| `scikit-learn__scikit-learn-14087` | 0 | — | — | — | no primitive resolved |
| `scikit-learn__scikit-learn-14141` | 13 | OTRC+SU-partial (55k) | OTRC (78k) | 23k | **OTRC+SU-partial** |
| `scikit-learn__scikit-learn-14496` | 11 | SS (114k) | OTRC+SS-partial (124k) | 9k | **SS** |
| `scikit-learn__scikit-learn-14629` | 1 | FC (777k) | — | — | **FC** |
| `scikit-learn__scikit-learn-14710` | 0 | — | — | — | no primitive resolved |
| `scikit-learn__scikit-learn-14894` | 11 | OTRC+SS-partial (116k) | SS-partial (144k) | 28k | **OTRC+SS-partial** |
| `scikit-learn__scikit-learn-14983` | 2 | TRC+SU (806k) | FC (827k) | 21k | **TRC+SU** |
| `scikit-learn__scikit-learn-15100` | 12 | SS-partial (114k) | TRC+SS (118k) | 4k | **SS-partial** |
| `scikit-learn__scikit-learn-25102` | 3 | TRC+SU (476k) | OTRC (714k) | 238k | **TRC+SU** |
| `scikit-learn__scikit-learn-25232` | 1 | FC (1574k) | — | — | **FC** |
| `scikit-learn__scikit-learn-25747` | 0 | — | — | — | no primitive resolved |
| `scikit-learn__scikit-learn-25931` | 4 | SU-partial (378k) | TRC+SS (468k) | 90k | **SU-partial** |
| `scikit-learn__scikit-learn-25973` | 6 | SS-partial (301k) | TRC+SS (457k) | 156k | **SS-partial** |
| `scikit-learn__scikit-learn-26194` | 2 | OTRC+TR (262k) | FC (675k) | 413k | **OTRC+TR** |
| `scikit-learn__scikit-learn-26323` | 8 | OTRC+SU-partial (273k) | SS (296k) | 22k | **OTRC+SU-partial** |
| `scikit-learn__scikit-learn-9288` | 4 | OTRC+SS-partial (471k) | TRC+SS (662k) | 191k | **OTRC+SS-partial** |
| `sympy__sympy-11618` | 13 | OTRC+TR (148k) | TRC (177k) | 29k | **OTRC+TR** |
| `sympy__sympy-12419` | 4 | SS-partial (368k) | SU-full (534k) | 166k | **SS-partial** |
| `sympy__sympy-12489` | 0 | — | — | — | no primitive resolved |
| `sympy__sympy-13031` | 2 | OTRC+TR (328k) | TR (742k) | 414k | **OTRC+TR** |
| `sympy__sympy-13091` | 0 | — | — | — | no primitive resolved |
| `sympy__sympy-13372` | 12 | OTRC+SS-partial (143k) | SS-partial (154k) | 11k | **OTRC+SS-partial** |
| `sympy__sympy-13647` | 13 | SS (204k) | OTRC+SU-partial (204k) | 0k | **SS** |
| `sympy__sympy-13757` | 7 | OTRC+TR (322k) | TRC+SU (436k) | 114k | **OTRC+TR** |
| `sympy__sympy-13798` | 0 | — | — | — | no primitive resolved |
| `sympy__sympy-13878` | 1 | SS-partial (701k) | — | — | **SS-partial** |
| `sympy__sympy-14248` | 0 | — | — | — | no primitive resolved |
| `sympy__sympy-14531` | 9 | OTRC+TR (279k) | TR (401k) | 122k | **OTRC+TR** |
| `sympy__sympy-14711` | 10 | SS (216k) | SS-partial (243k) | 27k | **SS** |
| `sympy__sympy-15017` | 10 | OTRC+SU-partial (135k) | SU-partial (160k) | 24k | **OTRC+SU-partial** |
| `sympy__sympy-15345` | 8 | OTRC+SS-partial (313k) | SS-partial (341k) | 28k | **OTRC+SS-partial** |
| `sympy__sympy-15349` | 13 | SU-partial (82k) | SS-partial (90k) | 8k | **SU-partial** |
| `sympy__sympy-15875` | 1 | OTRC (949k) | — | — | **OTRC** |
| `sympy__sympy-16450` | 12 | OTRC+SS-partial (207k) | SS (220k) | 13k | **OTRC+SS-partial** |
| `sympy__sympy-17139` | 5 | OTRC (123k) | TR (190k) | 67k | **OTRC** |
| `sympy__sympy-17318` | 2 | TR (342k) | FC (922k) | 581k | **TR** |
| `sympy__sympy-17630` | 0 | — | — | — | no primitive resolved |
| `sympy__sympy-18189` | 13 | OTRC+SS-partial (111k) | SS-partial (117k) | 6k | **OTRC+SS-partial** |
| `sympy__sympy-18199` | 0 | — | — | — | no primitive resolved |
| `sympy__sympy-18211` | 12 | TRC (220k) | SU-partial (259k) | 39k | **TRC** |
| `sympy__sympy-19040` | 0 | — | — | — | no primitive resolved |
| `sympy__sympy-19637` | 12 | SS-partial (100k) | OTRC+SU-partial (122k) | 21k | **SS-partial** |
| `sympy__sympy-19954` | 13 | TR (123k) | OTRC+SU-partial (132k) | 9k | **TR** |
| `sympy__sympy-20438` | 0 | — | — | — | no primitive resolved |
| `sympy__sympy-20916` | 1 | FC (616k) | — | — | **FC** |
| `sympy__sympy-22456` | 10 | OTRC (218k) | SU-full (220k) | 2k | **OTRC** |
| `sympy__sympy-24066` | 13 | OTRC+SS-partial (102k) | OTRC+SU-partial (124k) | 22k | **OTRC+SS-partial** |
| `sympy__sympy-24213` | 13 | TR (105k) | SS-partial (113k) | 8k | **TR** |
| `sympy__sympy-24443` | 11 | SS (111k) | SS-partial (138k) | 27k | **SS** |
| `sympy__sympy-24661` | 12 | TRC (172k) | OTRC+SU-partial (195k) | 23k | **TRC** |

**Summary @ 10k:** 76/100 unambiguous winner · 0/100 no clear winner · 24/100 unresolved.

**Winner distribution @ 10k:**
- OTRC+TR: 10
- OTRC+SU-partial: 10
- OTRC+SS-partial: 9
- SS: 9
- TR: 6
- SS-partial: 6
- OTRC: 5
- TRC: 5
- TRC+SS: 5
- SU-full: 3
- SU-partial: 3
- FC: 3
- TRC+SU: 2

## Budget = 15k

| task | # prims resolved | winner (tokens) | runner-up (tokens) | margin | verdict |
|---|---:|---|---|---:|---|
| `django__django-11066` | 13 | SS (24k) | SU-partial (25k) | 1k | **SS** |
| `django__django-11087` | 0 | — | — | — | no primitive resolved |
| `django__django-11095` | 11 | OTRC+SU-partial (133k) | OTRC+SS-partial (262k) | 129k | **OTRC+SU-partial** |
| `django__django-11292` | 13 | OTRC+SS-partial (207k) | FC (215k) | 8k | **OTRC+SS-partial** |
| `django__django-11299` | 10 | SU-full (529k) | SS (537k) | 8k | **SU-full** |
| `django__django-11433` | 1 | SU-partial (296k) | — | — | **SU-partial** |
| `django__django-11477` | 0 | — | — | — | no primitive resolved |
| `django__django-11734` | 0 | — | — | — | no primitive resolved |
| `django__django-12143` | 13 | OTRC+SU-partial (57k) | OTRC+TR (61k) | 4k | **OTRC+SU-partial** |
| `django__django-12273` | 0 | — | — | — | no primitive resolved |
| `django__django-12276` | 12 | OTRC (119k) | OTRC+SS-partial (252k) | 133k | **OTRC** |
| `django__django-12304` | 11 | OTRC (117k) | SS (269k) | 153k | **OTRC** |
| `django__django-12325` | 0 | — | — | — | no primitive resolved |
| `django__django-12663` | 1 | OTRC+TR (736k) | — | — | **OTRC+TR** |
| `django__django-13012` | 8 | OTRC+SU-partial (295k) | SS-partial (317k) | 22k | **OTRC+SU-partial** |
| `django__django-13809` | 13 | OTRC+SU-partial (131k) | OTRC+SS-partial (158k) | 27k | **OTRC+SU-partial** |
| `django__django-13810` | 6 | SU-full (227k) | TRC+SS (302k) | 75k | **SU-full** |
| `django__django-13964` | 5 | OTRC+SU-partial (300k) | TRC+SU (385k) | 85k | **OTRC+SU-partial** |
| `django__django-14351` | 0 | — | — | — | no primitive resolved |
| `django__django-14580` | 8 | OTRC+SU-partial (320k) | SS (409k) | 89k | **OTRC+SU-partial** |
| `django__django-14725` | 0 | — | — | — | no primitive resolved |
| `django__django-14915` | 13 | OTRC+SS-partial (73k) | OTRC+SU-partial (74k) | 1k | **OTRC+SS-partial** |
| `django__django-14999` | 4 | SU-partial (276k) | TRC+SU (412k) | 136k | **SU-partial** |
| `django__django-15098` | 0 | — | — | — | no primitive resolved |
| `django__django-15278` | 10 | TR (260k) | OTRC+SU-partial (286k) | 26k | **TR** |
| `django__django-15368` | 13 | OTRC+SU-partial (156k) | OTRC+SS-partial (171k) | 15k | **OTRC+SU-partial** |
| `django__django-15525` | 5 | TRC (289k) | TRC+SU (652k) | 363k | **TRC** |
| `django__django-15629` | 0 | — | — | — | no primitive resolved |
| `django__django-15741` | 13 | OTRC+TR (245k) | SS (323k) | 78k | **OTRC+TR** |
| `django__django-15930` | 6 | SS (380k) | OTRC+SS-partial (550k) | 170k | **SS** |
| `django__django-15957` | 0 | — | — | — | no primitive resolved |
| `django__django-16667` | 0 | — | — | — | no primitive resolved |
| `django__django-17084` | 5 | OTRC+TR (745k) | OTRC (758k) | 13k | **OTRC+TR** |
| `django__django-17087` | 13 | OTRC+SU-partial (132k) | OTRC+TR (143k) | 11k | **OTRC+SU-partial** |
| `scikit-learn__scikit-learn-10297` | 12 | OTRC+TR (242k) | SS (359k) | 117k | **OTRC+TR** |
| `scikit-learn__scikit-learn-10844` | 13 | SS (112k) | OTRC+SS-partial (141k) | 29k | **SS** |
| `scikit-learn__scikit-learn-10908` | 9 | OTRC+SS-partial (430k) | TR (437k) | 7k | **OTRC+SS-partial** |
| `scikit-learn__scikit-learn-11310` | 7 | OTRC+TR (358k) | SS (416k) | 58k | **OTRC+TR** |
| `scikit-learn__scikit-learn-11578` | 11 | OTRC+SS-partial (403k) | OTRC+TR (417k) | 14k | **OTRC+SS-partial** |
| `scikit-learn__scikit-learn-12585` | 13 | SS (212k) | SS-partial (231k) | 19k | **SS** |
| `scikit-learn__scikit-learn-12682` | 8 | SU-partial (613k) | TRC (690k) | 77k | **SU-partial** |
| `scikit-learn__scikit-learn-12973` | 3 | SU-partial (333k) | SS (386k) | 53k | **SU-partial** |
| `scikit-learn__scikit-learn-13124` | 0 | — | — | — | no primitive resolved |
| `scikit-learn__scikit-learn-13135` | 13 | SS-partial (393k) | SS (422k) | 29k | **SS-partial** |
| `scikit-learn__scikit-learn-13142` | 13 | OTRC+SS-partial (269k) | OTRC+SU-partial (271k) | 2k | **OTRC+SS-partial** |
| `scikit-learn__scikit-learn-13328` | 8 | OTRC+SU-partial (280k) | TRC+SU (373k) | 94k | **OTRC+SU-partial** |
| `scikit-learn__scikit-learn-13439` | 13 | OTRC+SS-partial (192k) | OTRC (202k) | 9k | **OTRC+SS-partial** |
| `scikit-learn__scikit-learn-13496` | 12 | OTRC+TR (244k) | OTRC+SU-partial (259k) | 16k | **OTRC+TR** |
| `scikit-learn__scikit-learn-13779` | 12 | OTRC+SS-partial (172k) | SS-partial (247k) | 76k | **OTRC+SS-partial** |
| `scikit-learn__scikit-learn-14053` | 7 | TR (447k) | TRC+SU (498k) | 51k | **TR** |
| `scikit-learn__scikit-learn-14087` | 0 | — | — | — | no primitive resolved |
| `scikit-learn__scikit-learn-14141` | 11 | OTRC+SS-partial (60k) | TR (77k) | 17k | **OTRC+SS-partial** |
| `scikit-learn__scikit-learn-14496` | 8 | OTRC+TR (143k) | OTRC+SS-partial (170k) | 27k | **OTRC+TR** |
| `scikit-learn__scikit-learn-14629` | 3 | TR (622k) | FC (777k) | 155k | **TR** |
| `scikit-learn__scikit-learn-14710` | 0 | — | — | — | no primitive resolved |
| `scikit-learn__scikit-learn-14894` | 12 | OTRC (155k) | OTRC+SS-partial (199k) | 44k | **OTRC** |
| `scikit-learn__scikit-learn-14983` | 3 | TRC+SS (435k) | TR (716k) | 281k | **TRC+SS** |
| `scikit-learn__scikit-learn-15100` | 8 | SS-partial (103k) | OTRC+SS-partial (109k) | 6k | **SS-partial** |
| `scikit-learn__scikit-learn-25102` | 3 | OTRC (714k) | OTRC+TR (775k) | 62k | **OTRC** |
| `scikit-learn__scikit-learn-25232` | 2 | OTRC+TR (531k) | FC (1574k) | 1043k | **OTRC+TR** |
| `scikit-learn__scikit-learn-25747` | 2 | SU-partial (516k) | TRC (827k) | 311k | **SU-partial** |
| `scikit-learn__scikit-learn-25931` | 7 | OTRC+SS-partial (334k) | OTRC (509k) | 175k | **OTRC+SS-partial** |
| `scikit-learn__scikit-learn-25973` | 5 | OTRC+SS-partial (458k) | OTRC+TR (528k) | 70k | **OTRC+SS-partial** |
| `scikit-learn__scikit-learn-26194` | 2 | OTRC+SS-partial (320k) | FC (675k) | 355k | **OTRC+SS-partial** |
| `scikit-learn__scikit-learn-26323` | 8 | TRC+SS (395k) | SU-partial (431k) | 37k | **TRC+SS** |
| `scikit-learn__scikit-learn-9288` | 7 | OTRC+SS-partial (729k) | OTRC (864k) | 135k | **OTRC+SS-partial** |
| `sympy__sympy-11618` | 13 | OTRC+SS-partial (165k) | OTRC+SU-partial (169k) | 3k | **OTRC+SS-partial** |
| `sympy__sympy-12419` | 5 | SU-partial (438k) | SS (585k) | 147k | **SU-partial** |
| `sympy__sympy-12489` | 0 | — | — | — | no primitive resolved |
| `sympy__sympy-13031` | 1 | TR (900k) | — | — | **TR** |
| `sympy__sympy-13091` | 0 | — | — | — | no primitive resolved |
| `sympy__sympy-13372` | 13 | OTRC+TR (136k) | OTRC (194k) | 58k | **OTRC+TR** |
| `sympy__sympy-13647` | 13 | OTRC+SU-partial (181k) | OTRC+SS-partial (188k) | 6k | **OTRC+SU-partial** |
| `sympy__sympy-13757` | 2 | OTRC (866k) | FC (1442k) | 576k | **OTRC** |
| `sympy__sympy-13798` | 0 | — | — | — | no primitive resolved |
| `sympy__sympy-13878` | 0 | — | — | — | no primitive resolved |
| `sympy__sympy-14248` | 0 | — | — | — | no primitive resolved |
| `sympy__sympy-14531` | 10 | SU-full (505k) | OTRC (531k) | 27k | **SU-full** |
| `sympy__sympy-14711` | 11 | OTRC+SU-partial (228k) | OTRC+TR (233k) | 4k | **OTRC+SU-partial** |
| `sympy__sympy-15017` | 7 | OTRC (177k) | OTRC+TR (184k) | 7k | **OTRC** |
| `sympy__sympy-15345` | 10 | TRC+SU (326k) | SU-partial (550k) | 225k | **TRC+SU** |
| `sympy__sympy-15349` | 13 | OTRC (123k) | OTRC+TR (149k) | 26k | **OTRC** |
| `sympy__sympy-15875` | 5 | OTRC+SS-partial (192k) | TRC+SU (243k) | 52k | **OTRC+SS-partial** |
| `sympy__sympy-16450` | 13 | OTRC+TR (215k) | OTRC+SS-partial (259k) | 44k | **OTRC+TR** |
| `sympy__sympy-17139` | 7 | OTRC (123k) | TR (203k) | 80k | **OTRC** |
| `sympy__sympy-17318` | 1 | FC (922k) | — | — | **FC** |
| `sympy__sympy-17630` | 0 | — | — | — | no primitive resolved |
| `sympy__sympy-18189` | 13 | TRC (138k) | SS (166k) | 28k | **TRC** |
| `sympy__sympy-18199` | 0 | — | — | — | no primitive resolved |
| `sympy__sympy-18211` | 11 | SS-partial (277k) | TRC+SS (332k) | 55k | **SS-partial** |
| `sympy__sympy-19040` | 0 | — | — | — | no primitive resolved |
| `sympy__sympy-19637` | 8 | OTRC+SU-partial (77k) | OTRC+SS-partial (121k) | 44k | **OTRC+SU-partial** |
| `sympy__sympy-19954` | 13 | OTRC+SS-partial (94k) | OTRC+TR (115k) | 21k | **OTRC+SS-partial** |
| `sympy__sympy-20438` | 0 | — | — | — | no primitive resolved |
| `sympy__sympy-20916` | 1 | FC (616k) | — | — | **FC** |
| `sympy__sympy-22456` | 8 | OTRC (218k) | TR (299k) | 82k | **OTRC** |
| `sympy__sympy-24066` | 12 | OTRC+SS-partial (97k) | OTRC+SU-partial (144k) | 47k | **OTRC+SS-partial** |
| `sympy__sympy-24213` | 13 | OTRC+SS-partial (87k) | TRC+SU (116k) | 29k | **OTRC+SS-partial** |
| `sympy__sympy-24443` | 8 | OTRC+SS-partial (110k) | OTRC (163k) | 53k | **OTRC+SS-partial** |
| `sympy__sympy-24661` | 13 | OTRC+TR (216k) | SU-full (241k) | 25k | **OTRC+TR** |

**Summary @ 15k:** 77/100 unambiguous winner · 0/100 no clear winner · 23/100 unresolved.

**Winner distribution @ 15k:**
- OTRC+SS-partial: 18
- OTRC+SU-partial: 12
- OTRC+TR: 11
- OTRC: 9
- SU-partial: 6
- SS: 4
- TR: 4
- SU-full: 3
- SS-partial: 3
- TRC: 2
- TRC+SS: 2
- FC: 2
- TRC+SU: 1

## Budget = 20k

| task | # prims resolved | winner (tokens) | runner-up (tokens) | margin | verdict |
|---|---:|---|---|---:|---|
| `django__django-11066` | 13 | TR (24k) | OTRC+SS-partial (29k) | 4k | **TR** |
| `django__django-11087` | 0 | — | — | — | no primitive resolved |
| `django__django-11095` | 12 | SU-full (147k) | OTRC+SS-partial (169k) | 22k | **SU-full** |
| `django__django-11292` | 13 | OTRC+SS-partial (123k) | OTRC+SU-partial (208k) | 85k | **OTRC+SS-partial** |
| `django__django-11299` | 11 | TR (596k) | TRC+SS (600k) | 4k | **TR** |
| `django__django-11433` | 2 | TRC+SS (761k) | TRC (1261k) | 500k | **TRC+SS** |
| `django__django-11477` | 0 | — | — | — | no primitive resolved |
| `django__django-11734` | 0 | — | — | — | no primitive resolved |
| `django__django-12143` | 13 | SU-partial (63k) | OTRC+SU-partial (65k) | 2k | **SU-partial** |
| `django__django-12273` | 0 | — | — | — | no primitive resolved |
| `django__django-12276` | 13 | OTRC (119k) | OTRC+SS-partial (178k) | 59k | **OTRC** |
| `django__django-12304` | 10 | OTRC (117k) | OTRC+TR (164k) | 48k | **OTRC** |
| `django__django-12325` | 0 | — | — | — | no primitive resolved |
| `django__django-12663` | 0 | — | — | — | no primitive resolved |
| `django__django-13012` | 11 | OTRC+SS-partial (257k) | TRC (361k) | 103k | **OTRC+SS-partial** |
| `django__django-13809` | 13 | OTRC+SU-partial (112k) | SS (132k) | 20k | **OTRC+SU-partial** |
| `django__django-13810` | 8 | OTRC+SS-partial (514k) | SS-partial (523k) | 9k | **OTRC+SS-partial** |
| `django__django-13964` | 9 | OTRC+SU-partial (223k) | OTRC+SS-partial (366k) | 144k | **OTRC+SU-partial** |
| `django__django-14351` | 0 | — | — | — | no primitive resolved |
| `django__django-14580` | 13 | OTRC+TR (181k) | SS (421k) | 239k | **OTRC+TR** |
| `django__django-14725` | 0 | — | — | — | no primitive resolved |
| `django__django-14915` | 13 | FC (98k) | OTRC+SU-partial (118k) | 20k | **FC** |
| `django__django-14999` | 4 | SU-full (737k) | TRC+SU (770k) | 33k | **SU-full** |
| `django__django-15098` | 0 | — | — | — | no primitive resolved |
| `django__django-15278` | 9 | OTRC+SS-partial (254k) | OTRC+SU-partial (355k) | 101k | **OTRC+SS-partial** |
| `django__django-15368` | 13 | OTRC+TR (267k) | OTRC+SS-partial (343k) | 77k | **OTRC+TR** |
| `django__django-15525` | 3 | SU-full (657k) | SU-partial (934k) | 278k | **SU-full** |
| `django__django-15629` | 0 | — | — | — | no primitive resolved |
| `django__django-15741` | 13 | OTRC+SS-partial (298k) | OTRC+TR (328k) | 30k | **OTRC+SS-partial** |
| `django__django-15930` | 6 | SS (522k) | OTRC (574k) | 52k | **SS** |
| `django__django-15957` | 0 | — | — | — | no primitive resolved |
| `django__django-16667` | 0 | — | — | — | no primitive resolved |
| `django__django-17084` | 4 | OTRC+SS-partial (438k) | OTRC (758k) | 320k | **OTRC+SS-partial** |
| `django__django-17087` | 13 | OTRC+SS-partial (119k) | FC (145k) | 26k | **OTRC+SS-partial** |
| `scikit-learn__scikit-learn-10297` | 13 | OTRC+SS-partial (347k) | TRC+SS (421k) | 74k | **OTRC+SS-partial** |
| `scikit-learn__scikit-learn-10844` | 9 | SU-partial (172k) | OTRC+SU-partial (180k) | 8k | **SU-partial** |
| `scikit-learn__scikit-learn-10908` | 10 | OTRC+TR (494k) | OTRC+SU-partial (557k) | 63k | **OTRC+TR** |
| `scikit-learn__scikit-learn-11310` | 8 | OTRC+TR (641k) | SS-partial (735k) | 95k | **OTRC+TR** |
| `scikit-learn__scikit-learn-11578` | 13 | OTRC+TR (273k) | SU-full (396k) | 123k | **OTRC+TR** |
| `scikit-learn__scikit-learn-12585` | 10 | SU-partial (269k) | OTRC+SS-partial (336k) | 66k | **SU-partial** |
| `scikit-learn__scikit-learn-12682` | 9 | OTRC+SS-partial (319k) | OTRC+TR (500k) | 181k | **OTRC+SS-partial** |
| `scikit-learn__scikit-learn-12973` | 0 | — | — | — | no primitive resolved |
| `scikit-learn__scikit-learn-13124` | 0 | — | — | — | no primitive resolved |
| `scikit-learn__scikit-learn-13135` | 12 | OTRC+SS-partial (247k) | SU-partial (391k) | 144k | **OTRC+SS-partial** |
| `scikit-learn__scikit-learn-13142` | 13 | OTRC+SU-partial (258k) | OTRC+TR (372k) | 113k | **OTRC+SU-partial** |
| `scikit-learn__scikit-learn-13328` | 11 | OTRC (433k) | OTRC+SS-partial (474k) | 40k | **OTRC** |
| `scikit-learn__scikit-learn-13439` | 13 | OTRC+SS-partial (179k) | OTRC (202k) | 23k | **OTRC+SS-partial** |
| `scikit-learn__scikit-learn-13496` | 12 | OTRC+SS-partial (310k) | SS-partial (381k) | 72k | **OTRC+SS-partial** |
| `scikit-learn__scikit-learn-13779` | 13 | OTRC+SS-partial (255k) | SS-partial (402k) | 146k | **OTRC+SS-partial** |
| `scikit-learn__scikit-learn-14053` | 13 | OTRC+SS-partial (385k) | SU-partial (481k) | 96k | **OTRC+SS-partial** |
| `scikit-learn__scikit-learn-14087` | 0 | — | — | — | no primitive resolved |
| `scikit-learn__scikit-learn-14141` | 13 | OTRC+SU-partial (42k) | OTRC+TR (61k) | 19k | **OTRC+SU-partial** |
| `scikit-learn__scikit-learn-14496` | 12 | OTRC+TR (124k) | OTRC+SU-partial (127k) | 4k | **OTRC+TR** |
| `scikit-learn__scikit-learn-14629` | 4 | SS-partial (698k) | FC (777k) | 79k | **SS-partial** |
| `scikit-learn__scikit-learn-14710` | 0 | — | — | — | no primitive resolved |
| `scikit-learn__scikit-learn-14894` | 13 | OTRC (155k) | OTRC+TR (247k) | 92k | **OTRC** |
| `scikit-learn__scikit-learn-14983` | 2 | TRC (684k) | FC (827k) | 142k | **TRC** |
| `scikit-learn__scikit-learn-15100` | 12 | TRC+SS (98k) | TRC (105k) | 6k | **TRC+SS** |
| `scikit-learn__scikit-learn-25102` | 4 | OTRC+TR (620k) | OTRC (714k) | 94k | **OTRC+TR** |
| `scikit-learn__scikit-learn-25232` | 6 | SU-full (720k) | SU-partial (895k) | 175k | **SU-full** |
| `scikit-learn__scikit-learn-25747` | 1 | TRC+SS (669k) | — | — | **TRC+SS** |
| `scikit-learn__scikit-learn-25931` | 8 | OTRC (509k) | SS-partial (532k) | 23k | **OTRC** |
| `scikit-learn__scikit-learn-25973` | 7 | OTRC+SS-partial (611k) | OTRC+SU-partial (636k) | 25k | **OTRC+SS-partial** |
| `scikit-learn__scikit-learn-26194` | 2 | SU-partial (447k) | FC (675k) | 229k | **SU-partial** |
| `scikit-learn__scikit-learn-26323` | 11 | OTRC+SU-partial (514k) | OTRC+TR (595k) | 81k | **OTRC+SU-partial** |
| `scikit-learn__scikit-learn-9288` | 10 | SU-full (784k) | OTRC (864k) | 80k | **SU-full** |
| `sympy__sympy-11618` | 13 | OTRC+SU-partial (184k) | OTRC+TR (192k) | 8k | **OTRC+SU-partial** |
| `sympy__sympy-12419` | 5 | SU-full (676k) | SS (783k) | 107k | **SU-full** |
| `sympy__sympy-12489` | 0 | — | — | — | no primitive resolved |
| `sympy__sympy-13031` | 0 | — | — | — | no primitive resolved |
| `sympy__sympy-13091` | 2 | OTRC+SU-partial (1153k) | TR (1189k) | 36k | **OTRC+SU-partial** |
| `sympy__sympy-13372` | 13 | OTRC+SS-partial (191k) | OTRC (194k) | 4k | **OTRC+SS-partial** |
| `sympy__sympy-13647` | 13 | OTRC+SS-partial (173k) | OTRC+SU-partial (218k) | 45k | **OTRC+SS-partial** |
| `sympy__sympy-13757` | 4 | TRC (668k) | OTRC (866k) | 198k | **TRC** |
| `sympy__sympy-13798` | 0 | — | — | — | no primitive resolved |
| `sympy__sympy-13878` | 0 | — | — | — | no primitive resolved |
| `sympy__sympy-14248` | 0 | — | — | — | no primitive resolved |
| `sympy__sympy-14531` | 11 | OTRC+SU-partial (489k) | TR (518k) | 29k | **OTRC+SU-partial** |
| `sympy__sympy-14711` | 10 | SS (272k) | TRC+SS (523k) | 251k | **SS** |
| `sympy__sympy-15017` | 10 | OTRC+SS-partial (135k) | OTRC+TR (168k) | 32k | **OTRC+SS-partial** |
| `sympy__sympy-15345` | 13 | OTRC+SS-partial (374k) | OTRC+TR (533k) | 160k | **OTRC+SS-partial** |
| `sympy__sympy-15349` | 13 | SS-partial (119k) | OTRC (123k) | 5k | **SS-partial** |
| `sympy__sympy-15875` | 3 | TRC+SS (386k) | OTRC (949k) | 562k | **TRC+SS** |
| `sympy__sympy-16450` | 13 | OTRC+SS-partial (224k) | OTRC+TR (234k) | 10k | **OTRC+SS-partial** |
| `sympy__sympy-17139` | 8 | OTRC (123k) | OTRC+TR (141k) | 18k | **OTRC** |
| `sympy__sympy-17318` | 2 | SS-partial (454k) | FC (922k) | 468k | **SS-partial** |
| `sympy__sympy-17630` | 0 | — | — | — | no primitive resolved |
| `sympy__sympy-18189` | 13 | OTRC (173k) | OTRC+SS-partial (182k) | 9k | **OTRC** |
| `sympy__sympy-18199` | 0 | — | — | — | no primitive resolved |
| `sympy__sympy-18211` | 9 | OTRC+TR (168k) | SS (320k) | 152k | **OTRC+TR** |
| `sympy__sympy-19040` | 0 | — | — | — | no primitive resolved |
| `sympy__sympy-19637` | 12 | OTRC+TR (75k) | TRC+SS (104k) | 29k | **OTRC+TR** |
| `sympy__sympy-19954` | 13 | OTRC+SS-partial (85k) | OTRC+TR (123k) | 38k | **OTRC+SS-partial** |
| `sympy__sympy-20438` | 0 | — | — | — | no primitive resolved |
| `sympy__sympy-20916` | 1 | FC (616k) | — | — | **FC** |
| `sympy__sympy-22456` | 6 | OTRC (218k) | OTRC+SS-partial (285k) | 68k | **OTRC** |
| `sympy__sympy-24066` | 11 | OTRC+TR (170k) | OTRC+SU-partial (192k) | 23k | **OTRC+TR** |
| `sympy__sympy-24213` | 13 | SU-full (110k) | OTRC+SU-partial (113k) | 3k | **SU-full** |
| `sympy__sympy-24443` | 12 | OTRC (163k) | OTRC+TR (189k) | 26k | **OTRC** |
| `sympy__sympy-24661` | 13 | FC (357k) | SU-full (406k) | 49k | **FC** |

**Summary @ 20k:** 75/100 unambiguous winner · 0/100 no clear winner · 25/100 unresolved.

**Winner distribution @ 20k:**
- OTRC+SS-partial: 21
- OTRC+TR: 10
- OTRC: 9
- OTRC+SU-partial: 8
- SU-full: 7
- TRC+SS: 4
- SU-partial: 4
- FC: 3
- SS-partial: 3
- TR: 2
- SS: 2
- TRC: 2


## Cross-budget comparison

| budget | unambig winner | no clear winner | unresolved |
|---|---:|---:|---:|
| 10k | 76/100 | 0/100 | 24/100 |
| 15k | 77/100 | 0/100 | 23/100 |
| 20k | 75/100 | 0/100 | 25/100 |

### Winner counts side-by-side
| primitive | 10k | 15k | 20k |
|---|---:|---:|---:|
| FC | 3 | 2 | 3 |
| OTRC | 5 | 9 | 9 |
| OTRC+SS-partial | 9 | 18 | 21 |
| OTRC+SU-partial | 10 | 12 | 8 |
| OTRC+TR | 10 | 11 | 10 |
| SS | 9 | 4 | 2 |
| SS-partial | 6 | 3 | 3 |
| SU-full | 3 | 3 | 7 |
| SU-partial | 3 | 6 | 4 |
| TR | 6 | 4 | 2 |
| TRC | 5 | 2 | 2 |
| TRC+SS | 5 | 2 | 4 |
| TRC+SU | 2 | 1 | 0 |
