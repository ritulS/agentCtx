"""Calibrate TIGHT/MEDIUM/LOOSE compression budgets for a model.

Methodology (Option B, per ALBUS_PLAN §1.3b):
  Match Qwen3.5-35B-A3B's reference trigger rates within ±5pp:
    TIGHT  → 97% of FC runs would have triggered compression
    MEDIUM → 88% trigger rate
    LOOSE  → 76% trigger rate
  Mathematically: budget = peak step_prompt_tokens at percentile (1 - rate),
  rounded to nearest 1000.

Reads:
  results/ablations/<MODEL_TAG>-inf/experiment_results.json

Writes:
  logs/<MODEL_TAG>_calibrated_budgets.sh    shell-sourceable budgets

Exit code:
  0 if all three targets land within ±5pp tolerance
  1 if any target is out of tolerance (manual review required)

Usage:
  venv/bin/python3 Review1/calibrate_budgets.py --model-tag qwen25-7b
"""

import argparse
import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent

REFERENCE_TARGETS = [
    ("TIGHT",  0.97),
    ("MEDIUM", 0.88),
    ("LOOSE",  0.76),
]
CANDIDATE_BUDGETS = [4000, 6000, 8000, 10000, 12000, 15000, 20000, 25000, 30000]
TOLERANCE_PP = 5  # ±5 percentage points


def percentile(sorted_vals: list[int], p: float) -> int:
    """Linear interpolation percentile (numpy default style). p in [0, 1]."""
    if not sorted_vals:
        raise ValueError("empty distribution")
    k = (len(sorted_vals) - 1) * p
    lo, hi = int(k), min(int(k) + 1, len(sorted_vals) - 1)
    return int(round(sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (k - lo)))


def trigger_rate(peaks: list[int], budget: int) -> float:
    return sum(1 for p in peaks if p > budget) / len(peaks)


def round_to_1k(x: int) -> int:
    return int(round(x / 1000.0)) * 1000


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-tag", required=True,
                        help="Model tag (e.g. qwen25-7b). Reads results/ablations/<TAG>-inf/.")
    parser.add_argument("--ablation-suffix", default="inf",
                        help="Suffix for the FC ablation dir (default: inf).")
    args = parser.parse_args()

    tag = args.model_tag
    src = ROOT / "results" / "ablations" / f"{tag}-{args.ablation_suffix}" / "experiment_results.json"
    if not src.exists():
        print(f"ERROR: {src} not found")
        return 1

    runs = json.loads(src.read_text())
    fc_runs = [r for r in runs if r.get("condition") == "full-context"]
    if not fc_runs:
        print(f"ERROR: no full-context runs in {src}")
        return 1

    peaks = sorted(
        max(r["step_prompt_tokens"]) for r in fc_runs
        if r.get("step_prompt_tokens") and len(r["step_prompt_tokens"]) > 0
    )
    n = len(peaks)
    if n == 0:
        print(f"ERROR: no FC runs had non-empty step_prompt_tokens")
        return 1

    # Distribution snapshot
    print(f"=== FC peak step_prompt_tokens distribution ({tag}, n={n}) ===")
    print(f"  min={peaks[0]:>7}  p10={percentile(peaks, 0.10):>7}  "
          f"p25={percentile(peaks, 0.25):>7}  p50={percentile(peaks, 0.50):>7}")
    print(f"  p75={percentile(peaks, 0.75):>7}  p90={percentile(peaks, 0.90):>7}  "
          f"max={peaks[-1]:>7}  mean={int(sum(peaks)/n):>7}")
    print()

    print("Trigger rate at candidate budgets:")
    for b in CANDIDATE_BUDGETS:
        tr = trigger_rate(peaks, b) * 100
        bar = "█" * int(tr / 2)
        print(f"  {b//1000:>3}k → {tr:>5.1f}%  {bar}")
    print()

    # Pick budgets at target rates
    chosen = {}
    all_within_tolerance = True
    print("=== Calibrated budgets (Option B: match 35B reference rates ±5pp) ===")
    for label, target_rate in REFERENCE_TARGETS:
        # Budget at percentile (1 - target_rate) of peaks gives trigger rate ≈ target_rate
        raw_budget = percentile(peaks, 1.0 - target_rate)
        budget = round_to_1k(raw_budget)
        if budget < 1000:
            budget = 1000  # floor
        actual_rate = trigger_rate(peaks, budget) * 100
        target_pct = target_rate * 100
        delta = actual_rate - target_pct
        ok = abs(delta) <= TOLERANCE_PP
        if not ok:
            all_within_tolerance = False
        flag = "✓" if ok else "✗ OUT-OF-TOLERANCE"
        print(f"  {label:<7} target={target_pct:>4.0f}%  budget={budget:>6}  "
              f"actual={actual_rate:>5.1f}%  Δ={delta:+5.1f}pp  {flag}")
        chosen[label] = (budget, actual_rate)

    # Ensure budgets are distinct (round-collision)
    seen = {}
    for label, target_rate in REFERENCE_TARGETS:
        b = chosen[label][0]
        if b in seen:
            print(f"WARNING: {label} budget {b} collides with {seen[b]} after rounding to 1k")
            all_within_tolerance = False
        seen[b] = label

    # Write sourceable file
    out = ROOT / "logs" / f"{tag}_calibrated_budgets.sh"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w") as f:
        f.write(f"# Calibrated budgets for {tag}\n")
        f.write(f"# Generated {datetime.utcnow().isoformat()}Z by Review1/calibrate_budgets.py\n")
        f.write(f"# Methodology: Option B — match Qwen3.5-35B-A3B reference trigger rates ±5pp\n")
        f.write(f"# n_FC_runs={n}\n")
        for label, _ in REFERENCE_TARGETS:
            b, r = chosen[label]
            f.write(f"# {label}: budget={b}, actual_trigger={r:.1f}%\n")
        for label, _ in REFERENCE_TARGETS:
            f.write(f"{label}_BUDGET={chosen[label][0]}\n")
        f.write(f'CALIBRATED_AT="{datetime.utcnow().isoformat()}Z"\n')
        f.write(f"ALL_WITHIN_TOLERANCE={'true' if all_within_tolerance else 'false'}\n")

    print(f"\nWrote {out.relative_to(ROOT)}")
    if not all_within_tolerance:
        print("\nFAIL: at least one budget is outside ±5pp tolerance. Manual review required.")
        return 1
    print("\nPASS: all budgets within ±5pp tolerance.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
