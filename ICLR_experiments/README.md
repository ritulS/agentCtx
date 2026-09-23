# ICLR Experiment Results

## Directory Structure
```text
ICLR_experiments/
├── README.md
|
├── swebench/
│   ├── main/
│   │   ├── qwen35b/
│   │   ├── devstral24b/
│   │   └── glm47flash/
│   ├── ablation/
│   │   ├── qwen35b/
│   │   ├── devstral24b/
│   │   └── glm47flash/
│   ├── summarizer_ablation/
│   └── prefix_cache_ablation/      # vLLM --enable-prefix-caching reruns
│       └── qwen35b-prefixcache/    # ABL-25, 15K + FC/OTRC at inf, canonical depth, all primitives
│
└── terminalbench/
    ├── main/
    │   ├── qwen35b/                  # Complete P-80 results
    │   ├── devstral24b/             # Complete P-80 results
    │   ├── glm47flash/              # Complete P-80 results
    │   └── p80_rootless/            # Rootless-buildable P-80 subset
    │       ├── qwen35b/
    │       │   └── di__binf__fc/
    │       ├── devstral24b/
    │       └── glm47flash/
    ├── ablation/
    │   ├── qwen35b/
    │   ├── devstral24b/
    │   └── glm47flash/
    ├── summarizer_ablation/
    └── prefix_cache_ablation/      # vLLM --no-enable-prefix-caching reruns
        └── qwen35b-noprefixcache/  # ABL-15, 3K + FC/OTRC at inf, canonical depth, all primitives

```

`prefix_cache_ablation/` holds Qwen3.5-35B-A3B reruns with the vLLM prefix-caching
setting flipped relative to each benchmark's production serving: production
SWE-Bench ran with it off, so `swebench/prefix_cache_ablation/qwen35b-prefixcache/`
has it **on** (`scripts/expansions/run_qwen_swe_prefix_cache_ablation.sh`); production
Terminal-Bench ran with it on, so
`terminalbench/prefix_cache_ablation/qwen35b-noprefixcache/` has it **off**
(`scripts/expansions/run_qwen_tb_prefix_cache_ablation.sh`). The baseline of each cell is the
production cell of the same name under `main/qwen35b/`, restricted to the
ablation cohort.

## Naming
```text
{depth}__{budget}__{primitive}
```

**Depth**
- `d03`: 0.3
- `d05`: 0.5
- `d07`: 0.7
- `di`: depth invariant

**Budget**
- `b{N}k`: numeric budget of N thousand tokens (used for Devstral)
- `b15k`: 15K
- `b20k`: 20K
- `b24k`: 24K
- `bA`: GLM lower ablation budget
- `bP`: GLM primary budget
- `bB`: GLM upper ablation budget
- `binf`: unlimited

### Example
```
swebench/ablation/devstral24b/
├── d03__b15k__tr/
├── d03__b15k__su-full/
├── d03__b15k__su-partial/
├── d03__b15k__ss/
├── d03__b15k__ss-partial/
├── ...
├── d05__b20k__su-full/
├── ...
├── d07__b24k__ss-partial/
├── di__b15k__trc/
├── di__b15k__trc-su/
├── ...
└── di__b24k__otrc-ss-partial/
```
