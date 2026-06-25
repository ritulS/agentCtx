"""Generate four standalone figures for §4.1 and §4.3 at the 15k budget.

Outputs (all under Review1/figures_n100/):
  fig_4_1_pareto_resolve_tokens.png   — Pareto: resolve % vs total tokens
  fig_4_1_pareto_resolve_latency.png  — Pareto: resolve % vs end-to-end latency
  fig_4_1_depth_heatmap.png           — Primitive (8 rows) x depth (3 cols) resolve %
  fig_4_3_failure_modes.png           — Stacked 4-bucket failure-mode bar
"""
from pathlib import Path
import csv
import statistics

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from adjustText import adjust_text

REVIEW = Path(__file__).parent
CSV    = REVIEW / "Review1.csv"
OUT    = REVIEW / "figures_n100"
OUT.mkdir(exist_ok=True)

with open(CSV) as f:
    rows = list(csv.DictReader(f))


# ============================================================================
# Primitive ordering / family / trigger encoding
# ============================================================================
RULE_BASED    = {"TR", "TRC"}
LLM_BASED     = {"SU-full", "SU-partial", "SS", "SS-partial"}
STACK_THRESH  = {"TRC+SU", "TRC+SS"}
STACK_ONLINE  = {"OTRC+TR", "OTRC+SU-partial", "OTRC+SS-partial"}

FAMILY = {}
for p in RULE_BASED:   FAMILY[p] = "rule"
for p in LLM_BASED:    FAMILY[p] = "llm"
for p in STACK_THRESH: FAMILY[p] = "stack_thresh"
for p in STACK_ONLINE: FAMILY[p] = "stack_online"
FAMILY["FC"]   = "baseline"
FAMILY["OTRC"] = "baseline"

FAMILY_COLOR = {
    "rule":         "#2563EB",   # blue
    "llm":          "#DC2626",   # red
    "stack_thresh": "#7C3AED",   # purple
    "stack_online": "#059669",   # green
    "baseline":     "#374151",   # dark grey
}
FAMILY_MARKER = {
    "rule":         "o",
    "llm":          "^",
    "stack_thresh": "s",
    "stack_online": "D",
    "baseline":     "X",
}

# Eleven primitives at 15k/d=0.5 (display order: rule, llm, stack_thresh, stack_online)
PRIMS_15K = [
    "TR", "TRC",
    "SU-full", "SU-partial", "SS", "SS-partial",
    "TRC+SU", "TRC+SS",
    "OTRC+TR", "OTRC+SU-partial", "OTRC+SS-partial",
]
BASELINES = ["FC", "OTRC"]

# Eight primitives swept across depth at 15k
DEPTH_PRIMS = [
    "TR", "SU-full", "SU-partial", "SS", "SS-partial",
    "OTRC+TR", "OTRC+SU-partial", "OTRC+SS-partial",
]
DEPTH_TUNABLE_PRIMS = ["TR", "SU-full", "SU-partial", "SS", "SS-partial"]
DEPTHS = [0.3, 0.5, 0.7]


# ============================================================================
# Helpers
# ============================================================================
def cell_stats(primitive: str, budget_filter, depth: float | None = None) -> dict:
    """Return resolve %, mean total_prompt_tokens, mean latency_e2e_s, n."""
    if callable(budget_filter):
        sub = [r for r in rows if r["primitive"] == primitive and budget_filter(r["token_budget"])]
    else:
        sub = [r for r in rows if r["primitive"] == primitive and r["token_budget"] == str(budget_filter)]
    if depth is not None:
        sub = [r for r in sub if r["depth"] == str(depth)]
    if not sub:
        return {}
    n = len(sub)
    resolve = sum(1 for r in sub if r["resolved"] == "True") / n * 100
    toks = statistics.mean(int(r["total_prompt_tokens"]) for r in sub if r["total_prompt_tokens"] not in ("", "None"))
    lat  = statistics.mean(float(r["latency_e2e_s"]) for r in sub if r["latency_e2e_s"] not in ("", "None"))
    fm = {b: 0 for b in ("resolved", "submitted_unresolved", "limits_exceeded", "silent_crash")}
    for r in sub:
        m = r["failure_mode"]
        if m in fm: fm[m] += 1
    return {"resolve": resolve, "tokens": toks, "latency": lat, "n": n, "failure_mode": fm}


# ============================================================================
# Figure 1 — Pareto: resolve vs total tokens (15k/d=0.5 + unbounded baselines)
# ============================================================================
# Per-primitive label offsets: (dx_pt, dy_pt, ha, draw_arrow).
# When draw_arrow=True a thin leader line connects the label back to its marker —
# used for the dense cluster where labels must sit well outside their points.
# Default: (8, 5, "left", False).
LABEL_OFFSETS_TOKENS = {
    # Central cluster at (~580-610K, 43-47%): push labels outward with leaders.
    "TRC":              (-55,  14, "right", True),   # up-left with arrow
    "OTRC@∞":           ( 14,   2, "left",  False),  # right of marker (top of chart)
    "TRC+SS":           ( 30, -22, "left",  True),   # down-right with arrow
    "TRC+SU":           ( 14,   8, "left",  False),  # up-right (clear of cluster)
    "OTRC+TR":          (-95, -10, "right", True),   # far left with arrow
    "SU-partial":       (-12, -18, "right", False),  # below-left
    "SU-full":          ( 10,   2, "left",  False),  # right (isolated)
    "SS":               ( 10,  -3, "left",  False),  # right (isolated)
    "SS-partial":       ( 10, -14, "left",  False),  # down-right (avoid OTRC labels)
    # Left zone: keep OTRC+SS-partial and OTRC+SU-partial well separated
    "OTRC+SS-partial":  (-14,   2, "right", False),  # LEFT of marker (leftmost x)
    "OTRC+SU-partial":  ( 10,  10, "left",  False),  # up-right (above SS-partial below)
    "TR":               ( 10,  -3, "left",  False),  # right (isolated)
    "FC@∞":             (-14,  -2, "right", False),  # left of marker (rightmost point)
}
LABEL_OFFSETS_LATENCY = {
    # Cluster at ~725-740s, 42-45% — push labels outward with leaders.
    "TRC+SS":           (-18,  14, "right", True),   # up-left with arrow
    "FC@∞":             ( 18, -16, "left",  True),   # down-right with arrow
    "OTRC+SS-partial":  ( 28,  10, "left",  True),   # up-right with arrow
    "SS":               ( 10,  -3, "left",  False),  # right (isolated below cluster)
    # SU-full / SU-partial cluster at high latency (~815s)
    "SU-full":          (-10, -16, "right", False),  # below-left
    "SU-partial":       (-10,  12, "right", False),  # above-left
    # Left side
    "TRC":              ( 12,   2, "left",  False),  # right (isolated leftmost)
    "OTRC@∞":           ( 14,   2, "left",  False),  # right of marker (top)
    "OTRC+TR":          ( 12,  -3, "left",  False),  # right
    "TR":               (-10, -16, "right", False),  # below-left
    # Other
    "TRC+SU":           ( 12,   4, "left",  False),  # right
    "OTRC+SU-partial":  ( 10, -16, "left",  False),  # down-right (clear of cluster)
    "SS-partial":       (-12,   0, "right", False),  # left (rightmost in latency)
}


PARETO_LABEL = {
    "SU-partial":      "SU-p",
    "SS-partial":      "SS-p",
    "OTRC":            "TRC/St",
    "OTRC+TR":         "TRC/St+TR",
    "OTRC+SU-partial": "TRC/St+SU-p",
    "OTRC+SS-partial": "TRC/St+SS-p",
}


def _draw_pareto_panel(ax, x_key, x_label, x_scale, left_pad=0.22):
    """Draw one Pareto panel on the given axes — labels placed by adjust_text."""
    plotted = []
    for prim in PRIMS_15K:
        s = cell_stats(prim, 15000, 0.5)
        if not s: continue
        fam = FAMILY[prim]
        ax.scatter(s[x_key] / x_scale, s["resolve"],
                   marker=FAMILY_MARKER[fam], color=FAMILY_COLOR[fam],
                   s=130, edgecolor="white", linewidth=1.0, zorder=3)
        plotted.append((PARETO_LABEL.get(prim, prim), s[x_key] / x_scale, s["resolve"]))
    for prim in BASELINES:
        s = cell_stats(prim, 999999999)
        if not s: continue
        ax.scatter(s[x_key] / x_scale, s["resolve"],
                   marker=FAMILY_MARKER["baseline"], color=FAMILY_COLOR["baseline"],
                   s=170, edgecolor="white", linewidth=1.0, zorder=3)
        plotted.append((f"{PARETO_LABEL.get(prim, prim)}@∞", s[x_key] / x_scale, s["resolve"]))

    # Pad the axes BEFORE laying out labels so adjust_text has room to route.
    x_min, x_max = ax.get_xlim()
    ax.set_xlim(x_min - (x_max - x_min) * left_pad, x_max + (x_max - x_min) * 0.10)
    y_min, y_max = ax.get_ylim()
    ax.set_ylim(y_min - (y_max - y_min) * 0.18, y_max + (y_max - y_min) * 0.18)

    texts = [ax.text(x, y, label, fontsize=19, color="#1F2937", zorder=4)
             for label, x, y in plotted]
    adjust_text(
        texts, ax=ax,
        arrowprops=dict(arrowstyle="-", color="#D1D5DB", lw=0.5, shrinkA=2, shrinkB=6),
        expand_text=(2.40, 2.60),
        expand_points=(2.80, 3.20),
        force_text=(2.8, 3.6),
        force_points=(2.4, 2.8),
        only_move={"points": "xy", "text": "xy"},
        max_move=(200, 200),
    )

    ax.set_xlabel(x_label, fontsize=23)
    ax.tick_params(axis="both", labelsize=19)
    ax.grid(alpha=0.25, linestyle="--", linewidth=0.5)


def fig_pareto_combined():
    """Two-panel trade-off plot with a single shared legend on top."""
    fig, axes = plt.subplots(1, 2, figsize=(17.5, 5.7), sharey=True,
                             gridspec_kw={"wspace": 0.12})

    _draw_pareto_panel(axes[0], "tokens",  "Total prompt tokens (K)", 1000.0, left_pad=0.38)
    _draw_pareto_panel(axes[1], "latency", "End-to-end latency (s)",  1.0,    left_pad=0.32)

    axes[0].set_ylabel("Resolve rate (%)", fontsize=23)
    plt.setp(axes[1].get_yticklabels(), visible=True)
    axes[1].tick_params(axis="y", labelleft=True, labelsize=19)

    # Shared legend on top
    handles = [plt.Line2D([0], [0], marker=FAMILY_MARKER[f], color="w",
                          markerfacecolor=FAMILY_COLOR[f], markersize=17,
                          label=lbl, markeredgecolor="white")
               for f, lbl in [("rule", "Rule-based"),
                              ("llm", "LLM-based"),
                              ("stack_thresh", "Stacked (threshold)"),
                              ("stack_online", "Stacked (per-step)"),
                              ("baseline", "Unbounded")]]
    fig.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, 1.02),
               ncol=5, fontsize=20, frameon=False,
               handletextpad=0.4, columnspacing=1.2)

    plt.tight_layout(rect=[0, 0, 1, 0.90])
    out = OUT / "fig_4_1_pareto_combined.png"
    plt.savefig(out, dpi=200, bbox_inches="tight")
    plt.close()
    print(f"wrote {out}")


# ============================================================================
# Figure 2 — Primitive x depth heatmap at 15k
# ============================================================================
def fig_depth_heatmap():
    M = np.zeros((len(DEPTH_PRIMS), len(DEPTHS)))
    for i, prim in enumerate(DEPTH_PRIMS):
        for j, d in enumerate(DEPTHS):
            s = cell_stats(prim, 15000, d)
            M[i, j] = s["resolve"] if s else np.nan

    fig, ax = plt.subplots(figsize=(5.0, 5.5))
    im = ax.imshow(M, cmap="RdYlGn", aspect="auto", vmin=25, vmax=50)
    ax.set_xticks(range(len(DEPTHS)))
    ax.set_xticklabels([f"d = {d}" for d in DEPTHS], fontsize=10)
    ax.set_yticks(range(len(DEPTH_PRIMS)))
    ax.set_yticklabels(DEPTH_PRIMS, fontsize=10)
    ax.set_title("Resolve rate by primitive x depth at 15k budget",
                 fontsize=10.5, pad=8)

    # Annotate each cell with the % value
    for i in range(M.shape[0]):
        for j in range(M.shape[1]):
            v = M[i, j]
            if np.isnan(v): continue
            txt_color = "white" if v < 33 or v > 47 else "black"
            ax.text(j, i, f"{v:.1f}%", ha="center", va="center",
                    fontsize=9, color=txt_color, fontweight="bold")

    cbar = fig.colorbar(im, ax=ax, fraction=0.04, pad=0.04)
    cbar.set_label("Resolve rate (%)", fontsize=9)

    plt.tight_layout()
    out = OUT / "fig_4_1_depth_heatmap.png"
    plt.savefig(out, dpi=200, bbox_inches="tight")
    plt.close()
    print(f"wrote {out}")


# ============================================================================
# Figure 2b — Two-panel depth heatmap (resolve + tokens) for depth-tunable primitives
# ============================================================================
def fig_depth_heatmap_combined():
    """Two-panel heatmap. Left = resolve %, right = total prompt tokens (K).

    Restricted to the 5 depth-tunable primitives at 15k. The depth-invariant
    OTRC primitives are excluded since compression_ratio does not engage for them.
    """
    R = np.full((len(DEPTH_TUNABLE_PRIMS), len(DEPTHS)), np.nan)
    T = np.full((len(DEPTH_TUNABLE_PRIMS), len(DEPTHS)), np.nan)
    for i, prim in enumerate(DEPTH_TUNABLE_PRIMS):
        for j, d in enumerate(DEPTHS):
            s = cell_stats(prim, 15000, d)
            if s:
                R[i, j] = s["resolve"]
                T[i, j] = s["tokens"] / 1000.0

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))

    # Left panel — resolve %
    ax = axes[0]
    im = ax.imshow(R, cmap="RdYlGn", aspect="auto", vmin=25, vmax=50)
    ax.set_xticks(range(len(DEPTHS)))
    ax.set_xticklabels([f"d = {d}" for d in DEPTHS], fontsize=11)
    ax.set_yticks(range(len(DEPTH_TUNABLE_PRIMS)))
    ax.set_yticklabels(DEPTH_TUNABLE_PRIMS, fontsize=11)
    ax.set_title("(a) Resolve rate (%)", fontsize=12, pad=8)
    for i in range(R.shape[0]):
        for j in range(R.shape[1]):
            v = R[i, j]
            if np.isnan(v): continue
            txt_color = "white" if v < 33 or v > 47 else "black"
            ax.text(j, i, f"{v:.1f}%", ha="center", va="center",
                    fontsize=10, color=txt_color, fontweight="bold")
    cbar = fig.colorbar(im, ax=ax, fraction=0.04, pad=0.04)
    cbar.set_label("Resolve rate (%)", fontsize=9)

    # Right panel — tokens (K). Reversed colormap so green = low cost.
    ax = axes[1]
    t_min = float(np.nanmin(T))
    t_max = float(np.nanmax(T))
    im = ax.imshow(T, cmap="RdYlGn_r", aspect="auto", vmin=t_min, vmax=t_max)
    ax.set_xticks(range(len(DEPTHS)))
    ax.set_xticklabels([f"d = {d}" for d in DEPTHS], fontsize=11)
    ax.set_yticks(range(len(DEPTH_TUNABLE_PRIMS)))
    ax.set_yticklabels(DEPTH_TUNABLE_PRIMS, fontsize=11)
    ax.set_title("(b) Total prompt tokens (K)", fontsize=12, pad=8)
    span = t_max - t_min if t_max > t_min else 1.0
    for i in range(T.shape[0]):
        for j in range(T.shape[1]):
            v = T[i, j]
            if np.isnan(v): continue
            rel = (v - t_min) / span
            txt_color = "white" if rel < 0.18 or rel > 0.82 else "black"
            ax.text(j, i, f"{v:.0f}k", ha="center", va="center",
                    fontsize=10, color=txt_color, fontweight="bold")
    cbar = fig.colorbar(im, ax=ax, fraction=0.04, pad=0.04)
    cbar.set_label("Total prompt tokens (K)", fontsize=9)

    fig.suptitle("Depth-tunable primitives at 15k budget: resolve and token cost across depths",
                 fontsize=12.5, y=1.02)
    plt.tight_layout()
    out = OUT / "fig_4_1_depth_heatmap_combined.png"
    plt.savefig(out, dpi=200, bbox_inches="tight")
    plt.close()
    print(f"wrote {out}")


# ============================================================================
# Figure 2c — Slope graphs: resolve and tokens vs depth (depth-tunable primitives)
# ============================================================================
def fig_depth_slope():
    """Two-panel slope graph. Left = resolve vs depth, right = tokens vs depth.

    One line per depth-tunable primitive across {0.3, 0.5, 0.7} at 15k. The
    slope of each line is the per-primitive depth-sensitivity. Lines that move
    show depth-sensitive primitives; flat lines show depth-insensitive ones.
    """
    PRIM_COLORS = {
        "TR":         "#1F77B4",  # blue
        "SU-full":    "#D62728",  # red
        "SU-partial": "#FF7F0E",  # orange
        "SS":         "#9467BD",  # purple
        "SS-partial": "#2CA02C",  # green
    }
    PRIM_MARKERS = {
        "TR":         "o",
        "SU-full":    "^",
        "SU-partial": "s",
        "SS":         "D",
        "SS-partial": "v",
    }

    # Paper defines depth as the fraction REMOVED (D = 1 - target/current), so
    # paper D = 0.7 corresponds to code d = 0.3 (most aggressive). Plot in paper
    # convention with x ascending left-to-right (low D = gentle, high D = aggressive).
    PAPER_DEPTHS = [0.3, 0.5, 0.7]
    R = {}
    T = {}
    for prim in DEPTH_TUNABLE_PRIMS:
        R[prim] = []
        T[prim] = []
        for paper_d in PAPER_DEPTHS:
            code_d = round(1.0 - paper_d, 2)
            s = cell_stats(prim, 15000, code_d)
            R[prim].append(s["resolve"] if s else np.nan)
            T[prim].append(s["tokens"] / 1000.0 if s else np.nan)

    fig, axes = plt.subplots(1, 2, figsize=(10, 5.0))

    def _draw(ax, data, ylabel):
        for prim in DEPTH_TUNABLE_PRIMS:
            ax.plot(PAPER_DEPTHS, data[prim],
                    color=PRIM_COLORS[prim], marker=PRIM_MARKERS[prim],
                    markersize=14, linewidth=2.6, zorder=3,
                    markeredgecolor="white", markeredgewidth=0.9,
                    label=prim)
        ax.set_xticks(PAPER_DEPTHS)
        ax.set_xticklabels([f"{d}" for d in PAPER_DEPTHS], fontsize=21)
        ax.set_ylabel(ylabel, fontsize=23, labelpad=1)
        ax.grid(alpha=0.3, linestyle="--", linewidth=1.25)
        ax.tick_params(axis="both", labelsize=21)
        xmin, xmax = ax.get_xlim()
        ax.set_xlim(xmin - (xmax - xmin) * 0.05, xmax + (xmax - xmin) * 0.05)

    _draw(axes[0], R, "Resolve rate (%)")
    _draw(axes[1], T, "Prompt tokens")

    # Shared legend on top — two centered rows (3 + 2) since 5 primitives
    # would leave the second row left-aligned with default ncol behaviour.
    handles = [plt.Line2D([0], [0], marker=PRIM_MARKERS[p], color=PRIM_COLORS[p],
                          markersize=15, linewidth=2.6, label=p,
                          markeredgecolor="white", markeredgewidth=0.9)
               for p in DEPTH_TUNABLE_PRIMS]
    leg_top = fig.legend(handles=handles[:3], loc="upper center",
                         bbox_to_anchor=(0.5, 1.02), ncol=3, fontsize=23,
                         frameon=False, handletextpad=0.4, columnspacing=1.4)
    fig.legend(handles=handles[3:], loc="upper center",
               bbox_to_anchor=(0.5, 0.94), ncol=2, fontsize=23,
               frameon=False, handletextpad=0.4, columnspacing=1.4)
    fig.add_artist(leg_top)

    plt.subplots_adjust(left=0.08, right=0.98, top=0.80, bottom=0.18, wspace=0.24)
    fig.supxlabel("Compression depth", fontsize=24.5, y=0.02, va="bottom")
    out = OUT / "fig_4_1_depth_slope.png"
    plt.savefig(out, dpi=200)
    plt.close()
    print(f"wrote {out}")


# ============================================================================
# Figure 3 — Stacked failure-mode bar at 15k/d=0.5
# ============================================================================
def fig_failure_modes():
    """3-bucket stacked bar (resolved / silent / visible), sorted by visible-share."""
    # Collapse the four raw modes into three: visible = limits_exceeded + silent_crash.
    BUCKET_COLORS = {
        "resolved": "#3FA34D",   # green
        "silent":   "#E59500",   # orange — submitted-wrong, silent failure
        "visible":  "#8B1A1A",   # dark red — combined limits-exceeded + silent-crash
    }
    BUCKET_LABELS = {
        "resolved": "Resolved",
        "silent":   "Submitted (wrong)  ← silent failure",
        "visible":  "Did not submit  ← visible failure",
    }

    # Gather both baselines + 11 primitives, compute 3-bucket shares.
    raw = []
    for prim in BASELINES:
        s = cell_stats(prim, 999999999)
        if s: raw.append((f"{prim}@∞", s))
    for prim in PRIMS_15K:
        s = cell_stats(prim, 15000, 0.5)
        if s: raw.append((prim, s))

    rows_out = []
    for name, s in raw:
        n = s["n"]
        fm = s["failure_mode"]
        rows_out.append({
            "name":    name,
            "resolved": fm["resolved"] / n * 100,
            "silent":   fm["submitted_unresolved"] / n * 100,
            "visible":  (fm["limits_exceeded"] + fm["silent_crash"]) / n * 100,
            "n":        n,
        })

    # Sort ascending by visible-failure share — left = "still silent",
    # right = "fails visibly". Story reads left→right.
    rows_out.sort(key=lambda r: r["visible"])

    labels = [r["name"] for r in rows_out]
    pct = {b: np.array([r[b] for r in rows_out]) for b in BUCKET_COLORS}

    fig, ax = plt.subplots(figsize=(11.0, 5.4))
    x = np.arange(len(labels))
    bottoms = np.zeros(len(labels))
    for b in ("resolved", "silent", "visible"):
        ax.bar(x, pct[b], bottom=bottoms, color=BUCKET_COLORS[b],
               label=BUCKET_LABELS[b], edgecolor="white", linewidth=0.5)
        bottoms += pct[b]

    # Reference lines: FC baseline shares (so the reader sees movement vs FC).
    fc = next(r for r in rows_out if r["name"] == "FC@∞")
    silent_floor  = fc["resolved"] + fc["silent"]
    visible_floor = silent_floor  # top of silent = bottom of visible
    ax.axhline(visible_floor, color="#1F2937", linestyle=":", linewidth=1.0,
               alpha=0.75, zorder=4)
    ax.text(len(labels) - 0.45, visible_floor + 0.6,
            f"FC silent ceiling = {visible_floor:.1f}%",
            fontsize=10, ha="right", color="#1F2937")

    # Bold the two baseline tick labels.
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=40, ha="right", fontsize=12)
    for tick_label, name in zip(ax.get_xticklabels(), labels):
        if name.endswith("@∞"):
            tick_label.set_fontweight("bold")

    ax.set_ylabel("Share of runs (%)", fontsize=13)
    ax.set_ylim(0, 100)
    ax.set_title("Failure-mode share by primitive (15k budget, depth 0.5; "
                 "sorted by visible-failure share)",
                 fontsize=13, pad=10)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.30), ncol=3,
              fontsize=12, frameon=False)
    ax.grid(axis="y", alpha=0.25, linestyle="--", linewidth=0.5)
    ax.set_axisbelow(True)

    plt.tight_layout()
    out = OUT / "fig_4_3_failure_modes.png"
    plt.savefig(out, dpi=200, bbox_inches="tight")
    plt.close()
    print(f"wrote {out}")


# ============================================================================
# Figure §4.2 — Per-task outcome heatmap (100 tasks × 13 primitives @ 15k/d=0.5)
# ============================================================================
def fig_per_task_heatmap():
    """100 tasks (rows, sorted by ease) × 13 primitives (cols).
    One cell per (task, primitive); resolved if any run resolved."""
    from matplotlib.patches import Rectangle, Patch

    BUCKET_COLOR = {
        "resolved": "#3FA34D",
        "failed":   "#C0392B",
    }
    BUCKET_LABEL = {
        "resolved": "Resolved",
        "failed":   "Failed",
    }

    # 13 columns: FC@∞ | 11 primitives @ 15k/d=0.5 | OTRC@∞
    columns = ["FC"] + PRIMS_15K + ["OTRC"]
    # Compact display labels — "partial" → "p" for x-tick space.
    # OTRC is the legacy code name; paper convention is TRC/St.
    COL_LABEL = {
        "SU-full":         "SU",
        "SU-partial":      "SU-p",
        "SS-partial":      "SS-p",
        "OTRC":            "TRC/St",
        "OTRC+TR":         "TRC/St+TR",
        "OTRC+SU-partial": "TRC/St+SU-p",
        "OTRC+SS-partial": "TRC/St+SS-p",
    }
    col_labels = [COL_LABEL.get(c, c) for c in columns]

    # Build (task, prim) → bucket; resolved if any run resolved.
    # Score uses only compression primitives (not FC/OTRC baselines), so the
    # sort yields three clean bands — all-resolve, split, none-resolve.
    tasks = sorted({r["task_name"] for r in rows})
    cells = {}
    score = np.zeros(len(tasks))
    for i, t in enumerate(tasks):
        for j, prim in enumerate(columns):
            if prim in ("FC", "OTRC"):
                sub = [r for r in rows if r["primitive"] == prim
                       and r["task_name"] == t
                       and r["token_budget"] == "999999999"]
            else:
                sub = [r for r in rows if r["primitive"] == prim
                       and r["task_name"] == t
                       and r["token_budget"] == "15000"
                       and r["depth"] == "0.5"]
            if not sub:
                cells[(i, j)] = None
                continue
            any_resolved = any(r["resolved"] == "True" for r in sub)
            if any_resolved and prim not in ("FC", "OTRC"):
                score[i] += 1
            cells[(i, j)] = "resolved" if any_resolved else "failed"

    n_prims = len(PRIMS_15K)
    top_count    = int(np.sum(score == n_prims))
    bottom_count = int(np.sum(score == 0))
    order = np.argsort(-score)

    n_rows = len(tasks)
    n_cols = len(columns)
    fig, ax = plt.subplots(figsize=(15, 16))

    for new_i, old_i in enumerate(order):
        for j in range(n_cols):
            bucket = cells.get((old_i, j))
            color  = BUCKET_COLOR[bucket] if bucket else "#FFFFFF"
            ax.add_patch(Rectangle(
                (j - 0.5, new_i - 0.5), 1.0, 1.0,
                facecolor=color, edgecolor="white", linewidth=0.35))

    ax.set_xlim(-0.5, n_cols - 0.5)
    ax.set_ylim(n_rows - 0.5, -0.5)
    ax.set_xticks(range(n_cols))
    ax.set_xticklabels(col_labels, rotation=45, ha="right",
                       rotation_mode="anchor", fontsize=44)
    # Y-axis: tick at 1, 10, 20, 30, ..., 100 (no individual task names)
    yticks = [0] + list(range(9, n_rows, 10))
    ax.set_yticks(yticks)
    ax.set_yticklabels([str(t + 1) for t in yticks], fontsize=40)
    ax.set_ylabel("Task index", fontsize=50)

    # Horizontal separators between the three bands — all-resolve | split | none-resolve
    ax.axhline(top_count - 0.5,             color="black", linewidth=2.2)
    ax.axhline(n_rows - bottom_count - 0.5, color="black", linewidth=2.2)

    # Vertical separator after the FC baseline column (FC | compression primitives ...)
    ax.axvline(0.5, color="black", linewidth=2.2)

    handles = [Patch(facecolor=BUCKET_COLOR[b], label=BUCKET_LABEL[b])
               for b in ("resolved", "failed")]
    ax.legend(handles=handles, loc="lower center",
              bbox_to_anchor=(0.5, 1.001), ncol=2, frameon=False, fontsize=48,
              handlelength=1.4, handletextpad=0.5, columnspacing=1.6,
              borderaxespad=0.0, borderpad=0.0)

    ax.set_aspect("auto")
    plt.subplots_adjust(left=0.12, right=0.98, top=0.94, bottom=0.14)
    out = OUT / "fig_4_2_per_task_heatmap.png"
    plt.savefig(out, dpi=200, bbox_inches="tight")
    plt.close()
    print(f"wrote {out}")


if __name__ == "__main__":
    fig_pareto_combined()
    fig_depth_heatmap()
    fig_depth_heatmap_combined()
    fig_depth_slope()
    fig_failure_modes()
    fig_per_task_heatmap()
