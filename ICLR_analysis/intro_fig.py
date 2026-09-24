"""Figure 1 schematic of context growth and repeated policy execution.

The illustrated policy uses a threshold trigger and a depth-tunable rewrite.
Hatching denotes the shorter history retained after compression, not removed
text. Depth is measured on the compressible history above the fixed prompt.
The policy definitions intentionally omit the experiment grid from Sec2.
"""
from pathlib import Path

import matplotlib
if __name__ == "__main__":
    matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, Rectangle
try:
    from .plot_style import PAPER_STYLE, PDARK, PLIGHT, save_figure
except ImportError:  # Direct script invocation.
    from plot_style import PAPER_STYLE, PDARK, PLIGHT, save_figure

OUT = Path(__file__).resolve().parent / "plots" / "setup"
INK = "#222222"
GREY = "#bdbdbd"
BLUE = PLIGHT["rule"]
THRESHOLD = 6.0
BAR_WIDTH = 0.72


def block(ax, x, bottom, height, *, compressed=False, prompt=False):
    ax.add_patch(Rectangle(
        (x - BAR_WIDTH / 2, bottom), BAR_WIDTH, height,
        facecolor=GREY if prompt else ("white" if compressed else BLUE),
        edgecolor=PDARK["rule"] if compressed else "white",
        hatch="////" if compressed else None, linewidth=0.55, zorder=3,
    ))


def bar(ax, x, fresh, history=0):
    """Fixed prompt, optional compressed history, then new interaction blocks."""
    block(ax, x, 0, 1, prompt=True)
    bottom = 1
    if history:
        block(ax, x, bottom, history, compressed=True)
        bottom += history
    for _ in range(fresh):
        block(ax, x, bottom, 1)
        bottom += 1
    return bottom


def rewrite_arrow(ax, start, end):
    arrow = FancyArrowPatch(
        start, end, connectionstyle="arc3,rad=-0.28", arrowstyle="-|>",
        mutation_scale=7, linewidth=1, color=PDARK["rule"], zorder=4,
    )
    ax.add_patch(arrow)
    return arrow


def left_panel(ax):
    # Compression is an event between agent steps, not an extra numbered step.
    for step in range(5):
        bar(ax, step, fresh=step + 1)
    bar(ax, 6.2, fresh=0, history=2)
    for x, fresh in [(7.3, 1), (8.4, 2), (9.5, 3)]:
        bar(ax, x, fresh=fresh, history=2)
    bar(ax, 11.2, fresh=0, history=2)

    ax.axhline(THRESHOLD, color=PDARK["stack"], linewidth=0.8,
               linestyle=(0, (3, 2)), zorder=1)
    ax.text(-0.35, 6.18, r"Trigger threshold $\mathbf{(T)}$", fontsize=6.5,
            color=PDARK["stack"], va="bottom")
    ax.text(6.1, 7.52, r"Primitive $\mathbf{(P)}$", fontsize=7.5,
            color=PDARK["rule"], ha="center", va="center")
    first_rewrite = rewrite_arrow(ax, (4.05, 6.65), (6.18, 3.18))
    first_rewrite.set_gid("primitive-rewrite")
    rewrite_arrow(ax, (9.53, 6.30), (11.18, 3.18))

    ax.annotate("", (5.25, 3), (5.25, 6), arrowprops=dict(
        arrowstyle="<->", color=PDARK["llm"], lw=0.85,
        shrinkA=0, shrinkB=0, mutation_scale=7,
    ))
    ax.text(6.0, 5.38, r"Depth $\mathbf{(D)}$", fontsize=6.5,
            color=PDARK["llm"], va="center")
    ax.text(12.0, 1.5, "…", fontsize=9, ha="center", va="center")

    ax.set_xlim(-0.55, 12.5)
    ax.set_ylim(0, 10.6)
    ax.set_xticks([0, 1, 2, 3, 4, 7.3, 8.4, 9.5])
    ax.set_xticklabels(range(1, 9), fontsize=6.5)
    ax.set_yticks([])
    ax.set_xlabel("Agent step", fontsize=7, labelpad=2)
    ax.set_ylabel("Context tokens", fontsize=7, labelpad=3)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.spines["left"].set_bounds(0, 6)
    ax.spines["bottom"].set_color("#737373")
    ax.spines["left"].set_color("#737373")
    ax.tick_params(length=2, pad=2)


def right_panel(ax):
    ax.set_axis_off()
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    rows = [
        (r"Primitive $\mathbf{(P)}$", "How context is changed", PDARK["rule"]),
        (r"Trigger $\mathbf{(T)}$", "When compression fires", PDARK["stack"]),
        (r"Depth $\mathbf{(D)}$", "What fraction is removed", PDARK["llm"]),
    ]
    for y, (name, definition, color) in zip([0.80, 0.51, 0.22], rows):
        ax.add_patch(Rectangle((0, y - 0.16), 1, 0.24,
                               facecolor="#f5f5f5", edgecolor="none"))
        ax.add_patch(Rectangle((0, y - 0.16), 0.018, 0.24,
                               facecolor=color, edgecolor="none"))
        ax.text(0.065, y + 0.018, name, fontsize=7.5,
                color=color, va="center")
        ax.text(0.065, y - 0.085, definition, fontsize=6.5, va="center")


def figure_legend(fig, *, anchor=(0.375, 0.96)):
    """One compact row, ordered from fixed context to rewritten history."""
    handles = [
        Rectangle((0, 0), 1, 1, fc=GREY, ec="white"),
        Rectangle((0, 0), 1, 1, fc=BLUE, ec="white"),
        Rectangle((0, 0), 1, 1, fc="white", ec=PDARK["rule"], hatch="////", lw=0.55),
    ]
    labels = ["Fixed prompt", "New history", "Compressed history"]
    fig.legend(handles, labels, loc="upper center", bbox_to_anchor=anchor,
               ncol=3, frameon=False, fontsize=6.5, handlelength=1.2,
               handleheight=1.0, handletextpad=0.4, columnspacing=0.8,
               borderaxespad=0, borderpad=0)


def connect_primitive_label(fig):
    """End the leader on the rendered curve after the panel geometry is set."""
    fig.canvas.draw()
    ax = fig.axes[0]
    arrow = next(p for p in ax.patches if p.get_gid() == "primitive-rewrite")
    start, control, end = arrow.get_path().vertices[:3]
    t = 0.18
    target = (1 - t) ** 2 * start + 2 * (1 - t) * t * control + t ** 2 * end
    ax.plot([6.1, target[0]], [7.13, target[1]],
            color=PDARK["rule"], lw=0.6, zorder=5)


def make_figure():
    fig = plt.figure(figsize=(5.5, 2.15))
    left_panel(fig.add_axes([0.067, 0.17, 0.615, 0.72]))
    right_panel(fig.add_axes([0.715, 0.14, 0.27, 0.82]))
    figure_legend(fig)
    connect_primitive_label(fig)
    return fig


def make_wrap_figure():
    """Native-size inset for wrapping intro prose on a 5.5 inch text block."""
    fig = plt.figure(figsize=(3.2, 1.9))
    # Preserve the plot and definition sizes while removing the heading space.
    vertical_scale = 2.2 / 1.9
    plot_left, plot_right = 0.082, 0.98
    plot_center = (plot_left + plot_right) / 2
    ax = fig.add_axes([plot_left, 0.28 * vertical_scale,
                       plot_right - plot_left, 0.51 * vertical_scale])
    left_panel(ax)
    ax.set_ylim(0, 8.05)
    ax.yaxis.labelpad = 1
    figure_legend(fig, anchor=(plot_center, 0.99))

    # Trigger and depth share the upper row; primitive spans the lower row.
    # Keep all copy at its native print size in the compact inset.
    group_width = 0.88
    group_left = plot_center - group_width / 2
    gap = 0.014
    trigger_width = 0.51
    points_per_width = fig.get_figwidth() * 72

    def definition_box(x, y, width, height, color):
        fig.add_artist(Rectangle(
            (x, y * vertical_scale), width, height * vertical_scale,
            transform=fig.transFigure,
            facecolor="#f5f5f5", edgecolor="#d9d9d9", linewidth=0.45,
            zorder=0,
        ))
        fig.add_artist(Rectangle(
            (x, y * vertical_scale), 0.008, height * vertical_scale,
            transform=fig.transFigure,
            facecolor=color, edgecolor="none", zorder=1,
        ))

    for x, width, name, definition, label_width, color in [
        (group_left, trigger_width, r"Trigger $\mathbf{(T)}$",
         "When primitive fires", 43, PDARK["stack"]),
        (group_left + trigger_width + gap, group_width - trigger_width - gap,
         r"Depth $\mathbf{(D)}$", "How much", 40, PDARK["llm"]),
    ]:
        definition_box(x, 0.080, width, 0.064, color)
        fig.text(x + 3 / points_per_width, 0.112 * vertical_scale, name,
                 fontsize=7.5, color=color, va="center")
        fig.text(x + (label_width + 6) / points_per_width, 0.112 * vertical_scale,
                 definition, fontsize=6.5, va="center")

    definition_box(group_left, 0.008, group_width, 0.064, PDARK["rule"])
    name = fig.text(0, 0.040 * vertical_scale, r"Primitive $\mathbf{(P)}$",
                    fontsize=7.5, color=PDARK["rule"], va="center")
    definition = fig.text(0, 0.040 * vertical_scale, "How context is changed",
                          fontsize=6.5, va="center")
    connect_primitive_label(fig)
    renderer = fig.canvas.get_renderer()
    name_width = name.get_window_extent(renderer).width / fig.bbox.width
    definition_width = definition.get_window_extent(renderer).width / fig.bbox.width
    text_gap = 6 / points_per_width
    text_left = plot_center - (name_width + text_gap + definition_width) / 2
    name.set_x(text_left)
    definition.set_x(text_left + name_width + text_gap)
    return fig


def main():
    with plt.rc_context(PAPER_STYLE):
        fig = make_figure()
        save_figure(fig, OUT, "intro_01_policy_axes", dpi=300)
        plt.close(fig)
        inset = make_wrap_figure()
        save_figure(inset, OUT, "intro_01_policy_axes_wrap", dpi=300)
        plt.close(inset)


if __name__ == "__main__":
    main()
