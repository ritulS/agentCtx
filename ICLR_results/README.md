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
    │   ├── qwen35b/
    │   ├── devstral24b/
    │   └── glm47flash/
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
- `b10k`: 10K
- `b15k`: 15K
- `b20k`: 20K
- `bA`: GLM lower ablation budget
- `bP`: GLM primary budget
- `bB`: GLM upper ablation budget
- `binf`: unlimited

### Example
```
swebench/ablation/devstral24b/
├── d03__b10k__tr/
├── d03__b10k__su-full/
├── d03__b10k__su-partial/
├── d03__b10k__ss/
├── d03__b10k__ss-partial/
├── ...
├── d05__b20k__su-full/
├── ...
├── d07__b20k__ss-partial/
├── di__b10k__trc/
├── di__b10k__trc-su/
├── ...
└── di__b20k__otrc-ss-partial/
```