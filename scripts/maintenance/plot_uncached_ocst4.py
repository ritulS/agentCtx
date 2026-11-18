#!/usr/bin/env python3
"""Uncached agent input tokens per run on the ocst4 pilot tasks: OCSA vs OCST vs
full context (the fc25 uncached-input figure with the threshold-select cell added).

Inputs (written by scripts/maintenance/estimate_uncached_prompt.py, the same
prefix-cache simulation for every cell: longest common message prefix with any
earlier prompt of the run, 16-token blocks, served tokens):
  data/r2/probes/uncached_prompt_estimate/per_run.csv        OCSA (a) and FC (b), fc25
  data/r2/probes/uncached_prompt_estimate_ocst/per_run.csv   OCST (a), 2026-11-12 pilot
For OCST the server also reported `cached_tokens` per call (the pilot's vLLM ran
with --enable-prompt-tokens-details), so the measured uncached total of each run
is read from token_log.json and drawn as a marker on the OCST bar.

Usage: venv/bin/python scripts/maintenance/plot_uncached_ocst4.py [--out PNG]
"""
from __future__ import annotations
import argparse, csv, json, statistics as st, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EST_FC25 = ROOT / "data/r2/probes/uncached_prompt_estimate/per_run.csv"
EST_OCST = ROOT / "data/r2/probes/uncached_prompt_estimate_ocst/per_run.csv"
OCST_CELL = ROOT / "data/r2/swebench/p30s/devstral24b-iso-fc20-dsflash/di__binf__ocst"
TASKS = ["scikit-learn__scikit-learn-10297", "django__django-15278", "sympy__sympy-14531", "sympy__sympy-12419"]


def load(path: Path, cell: str) -> dict[str, list[float]]:
    out: dict[str, list[float]] = {}
    for r in csv.DictReader(open(path)):
        if r["cell"] == cell and r["instance_id"] in TASKS:
            out.setdefault(r["instance_id"], []).append(float(r["uncached_any"]))
    return out


def measured_ocst() -> dict[str, list[float]]:
    out: dict[str, list[float]] = {}
    for tl in sorted(OCST_CELL.glob("*/*/run_*/token_log.json")):
        d = json.load(open(tl)); recs = d.get("model_call_records") or []
        if not recs or not any(r.get("cached_tokens") for r in recs):
            continue   # server without --enable-prompt-tokens-details
        unc = sum((r.get("prompt_tokens") or 0) - (r.get("cached_tokens") or 0) for r in recs)
        out.setdefault(tl.parts[-4], []).append(unc)
    return out


def short(t: str) -> str:
    repo, num = t.split("__")[1].rsplit("-", 1)
    return f"{repo.replace('scikit-learn', 'sklearn')}-{num}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=EST_OCST.parent / "uncached_input_tokens_ocst4.png")
    args = ap.parse_args()
    ocsa, fc, ocst, meas = load(EST_FC25, "a"), load(EST_FC25, "b"), load(EST_OCST, "a"), measured_ocst()

    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    rows = []
    for t in TASKS:
        rows.append({"t": t, "ocsa": st.mean(ocsa[t]), "fc": st.mean(fc[t]), "ocst": st.mean(ocst[t]),
                     "meas": st.mean(meas[t]) if t in meas else None})
    rows.sort(key=lambda r: r["ocsa"] / r["fc"])
    n = len(rows); names = [short(r["t"]) for r in rows]
    va = np.array([r["ocsa"] for r in rows]) / 1e6
    vt = np.array([r["ocst"] for r in rows]) / 1e6
    vb = np.array([r["fc"] for r in rows]) / 1e6
    vm = np.array([r["meas"] if r["meas"] is not None else np.nan for r in rows]) / 1e6
    ra, rt = va / vb, vt / vb
    col_a, col_t, col_b, ink, muted = "#E8641B", "#2A7F9E", "#C9C7BC", "#1F1F1F", "#6B6B6B"
    with open(args.out.with_suffix(".csv"), "w", newline="") as f:
        w = csv.writer(f); w.writerow(["instance_id", "ocsa_uncached", "ocst_uncached", "ocst_uncached_measured", "fc_uncached", "ocsa_over_fc", "ocst_over_fc"])
        for r, a_, t_, b_ in zip(rows, ra, rt, vb):
            w.writerow([r["t"], r["ocsa"], r["ocst"], r["meas"], r["fc"], f"{a_:.3f}", f"{t_:.3f}"])

    fig, (ax, axr) = plt.subplots(1, 2, figsize=(10.5, 5.2), gridspec_kw={"width_ratios": [2.6, 1.0], "wspace": 0.08})
    y = np.arange(n); h = 0.26
    ax.barh(y - h, va, h, color=col_a, label="OCSA (DeepSeek select, every step)")
    ax.barh(y, vt, h, color=col_t, label="OCST (DeepSeek select, fired above 30k)")
    ax.barh(y + h, vb, h, color=col_b, label="Full context")
    ok = ~np.isnan(vm)
    ax.plot(vm[ok], y[ok], marker="D", ls="none", ms=5, mfc="white", mec=col_t, mew=1.4,
            label="OCST measured (server cached_tokens)")
    for yi, a_, t_, b_ in zip(y, va, vt, vb):
        ax.text(a_ + 0.01, yi - h, f"{a_:.2f}M", va="center", fontsize=8, color=ink)
        ax.text(t_ + 0.01, yi, f"{t_:.2f}M", va="center", fontsize=8, color=ink)
        ax.text(b_ + 0.01, yi + h, f"{b_:.2f}M", va="center", fontsize=8, color=ink)
    ax.set_yticks(y); ax.set_yticklabels(names, fontsize=9); ax.invert_yaxis()
    ax.set_xlabel("Uncached input tokens per run (millions)", color=muted)
    ax.set_xlim(0, va.max() * 1.12)
    hs, ls = ax.get_legend_handles_labels()
    order = [1, 2, 3, 0]   # OCSA, OCST, FC, measured marker
    ax.legend([hs[i] for i in order], [ls[i] for i in order], loc="upper center", bbox_to_anchor=(0.5, -0.16),
              ncol=2, frameon=False, fontsize=8.5, columnspacing=1.6)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.spines["left"].set_color("#DDDDDD"); ax.spines["bottom"].set_color("#DDDDDD")
    ax.tick_params(axis="x", colors=muted); ax.grid(axis="x", color="#EEEEEE", lw=0.8); ax.set_axisbelow(True)

    axr.set_xscale("log")
    hr = 0.36
    for yi, r_a, r_t in zip(y, ra, rt):
        for off, r, c in ((-hr / 2, r_a, col_a), (hr / 2, r_t, col_t)):
            left, width = (r, 1 - r) if r < 1 else (1.0, r - 1)
            axr.barh(yi + off, width, hr, left=left, color=c)
            txt = f"{r:.2f}×"
            if r < 1:
                axr.text(r / 1.08, yi + off, txt, ha="right", va="center", fontsize=8, color=ink)
            else:
                axr.text(r * 1.08, yi + off, txt, ha="left", va="center", fontsize=8, color=ink)
    axr.axvline(1.0, color=ink, lw=1.2)
    axr.set_yticks(y); axr.set_yticklabels([]); axr.invert_yaxis()
    allr = np.concatenate([ra, rt])
    ticks = [t for t in (0.2, 0.5, 1, 2, 5, 10, 20, 50) if allr.min() / 2.5 <= t <= allr.max() * 2.5]
    axr.set_xticks(ticks); axr.set_xticklabels([f"{t:g}×" for t in ticks], fontsize=8, color=muted)
    axr.set_xlim(min(allr.min(), 1) / 2.5, max(allr.max(), 1) * 2.5)
    axr.set_xlabel("ratio to full context", color=muted)
    for s in ("top", "right", "left"):
        axr.spines[s].set_visible(False)
    axr.spines["bottom"].set_color("#DDDDDD"); axr.tick_params(axis="y", length=0)
    box = f"OCSA / FC median {np.median(ra):.1f}×\nOCST / FC median {np.median(rt):.2f}×"
    ax.text(0.97, 0.97, box, transform=ax.transAxes, ha="right", va="top", fontsize=9.5,
            bbox=dict(boxstyle="round,pad=0.5", fc="white", ec="#DDDDDD"))
    fig.suptitle("Firing the selector only above 30k keeps the input cached like full context",
                 x=0.01, y=0.985, ha="left", fontsize=13.5, fontweight="bold", color=ink)
    sub = ("SWE-bench Verified, the 4 ocst4 pilot tasks, mean per task (Full context: 3 runs, OCSA: 2 runs, OCST: 2 runs; Devstral-Small-2-24B, temperature 0)\n"
           "Bars: prefix-cache estimate, tokens beyond the longest common prefix with any earlier prompt of the same run (16-token blocks)\n"
           "Diamonds: OCST uncached tokens as reported by vLLM (cached_tokens); not available for the fc25 OCSA / full-context servers")
    fig.text(0.01, 0.93, sub, ha="left", va="top", fontsize=8.5, color=muted, linespacing=1.4)
    fig.subplots_adjust(top=0.79, bottom=0.22, left=0.11, right=0.98)
    fig.savefig(args.out, dpi=160)
    print(f"wrote {args.out} and {args.out.with_suffix('.csv')}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
