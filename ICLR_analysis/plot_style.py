"""Shared ICLR figure style. See Iclr_plot_bank.md for encoding conventions.
Importing this module does not mutate matplotlib rcParams.
"""
from pathlib import Path
from matplotlib.lines import Line2D

PAPER_STYLE = {
    "font.family": "DejaVu Sans", "font.size": 7.5, "axes.titlesize": 8,
    "axes.labelsize": 7.5, "xtick.labelsize": 7, "ytick.labelsize": 7,
    "legend.fontsize": 7, "axes.linewidth": 0.6, "pdf.fonttype": 42,
    "savefig.facecolor": "white",
}
Q2_STYLE = {**PAPER_STYLE, "font.size": 6}
MODELS = [("qwen35b", "Qwen", "o"), ("devstral24b", "Devstral", "^"), ("glm47flash", "GLM", "D")]
MK = {m: k for m, _, k in MODELS}
ORDER = ["TR", "TRC", "SU", "SU-p", "SS", "SS-p", "TRC+SU", "TRC+SS", "OTRC+TR", "OTRC+SU-p", "OTRC+SS-p", "OTRC"]
# Hue = policy family; shade = primitive; hollow = partial rewrite.
PDARK = {"rule": "#2171b5", "llm": "#d94801", "stack": "#238b45", "step": "#525252"}
PLIGHT = {"rule": "#6baed6", "llm": "#fd8d3c", "stack": "#74c476", "step": "#969696"}
PSTYLE = {"TR": ("rule", "d", False), "TRC": ("rule", "l", False),
          "SU": ("llm", "d", False), "SU-p": ("llm", "d", True), "SS": ("llm", "l", False), "SS-p": ("llm", "l", True),
          "TRC+SU": ("stack", "d", False), "TRC+SS": ("stack", "l", False),
          "OTRC+TR": ("step", "d", False), "OTRC+SU-p": ("step", "d", True), "OTRC+SS-p": ("step", "l", True),
          "OTRC": ("otrc", "d", True)}
# Per-policy overrides of the family palette: the OTRC-stacked family gets
# distinct purples (blue-leaning for OTRC+TR, red-leaning for OTRC+SU-p, light
# for OTRC+SS-p) instead of greys, so its members are not confused with each
# other or with hollow-black OTRC (2026-09-24 reviewer round).
POLICY_COLORS = {"OTRC+TR": "#8a4fd3", "OTRC+SU-p": "#c41cad", "OTRC+SS-p": "#7f6bd0"}


def pcol(p):
    """Policy color shared by all figures (FC is black)."""
    if p == "FC":
        return "#000000"
    if p in POLICY_COLORS:
        return POLICY_COLORS[p]
    g, shade, _ = PSTYLE[p]
    if g == "otrc":
        return "#000000"
    return PDARK[g] if shade == "d" else PLIGHT[g]


def pmark(ax, x, y, p, marker, s=22, force_hollow=False):
    """Draw a policy marker; marker shape encodes the model."""
    c = pcol(p)
    hollow = PSTYLE[p][2] or force_hollow
    if hollow:
        ax.scatter(x, y, marker=marker, s=s, facecolors="white", edgecolors=c,
                   linewidths=1.0, zorder=3)
    else:
        ax.scatter(x, y, marker=marker, s=s, color=c, edgecolors="#444444",
                   linewidths=0.3, zorder=3)


def prim_handles():
    h = []
    for p in ORDER:
        c = pcol(p); hollow = PSTYLE[p][2]
        h.append(Line2D([], [], marker="o", ls="", ms=4.5, mfc="white" if hollow else c, mec=c, mew=1.0 if hollow else 0.3, label=p))
    return h

def model_handles():
    return [Line2D([], [], marker=k, ls="", color="#555555", ms=5, label=n) for _, n, k in MODELS]



def save_figure(fig, output_dir, name, dpi=200):
    """Write a fixed-size PDF and PNG; preserve the selected layout margins."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    for suffix in ("pdf", "png"):
        fig.savefig(output_dir / f"{name}.{suffix}", dpi=dpi)



KNOB_STYLE = {**PAPER_STYLE, "font.size": 13, "axes.titlesize": 14,
              "axes.labelsize": 12.5, "xtick.labelsize": 12,
              "ytick.labelsize": 12, "legend.fontsize": 12}
RESOLVE_HIGHLIGHT = "#ffe680"  # highest resolve in a primitive/trigger triplet
COST_HIGHLIGHT = "#d9edcf"     # lowest billed cost in the triplet
