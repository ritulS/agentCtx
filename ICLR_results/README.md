# ICLR Experiment Results

## Directory Structure
```text
ICLR_results/
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
│   └── summarizer_ablation/
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
    └── summarizer_ablation/

```

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
