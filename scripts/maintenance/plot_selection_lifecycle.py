#!/usr/bin/env python3
"""Lifecycle raster of one online-claude-select run (ocs / ocsa):
which history messages the selector kept, trimmed, dropped and brought back,
step by step.

Rows are the history messages in the order they entered the history (newest at
the bottom), columns the selection steps. A cell is coloured by the message's
status in the agent's context at that step:

  dark grey   protected (system prompt, task statement)
  mid grey    newest turns, verbatim (keep_recent; not the selector's decision)
  blue        kept whole by the selector
  light blue  kept in part (a line range)
  near white  dropped (not in the context)
  blank       not yet in the history

An orange dot marks a revival: a message that was dropped at the previous step
and is kept (whole or in part) at this one. The right panel zooms into the
first steps with one label per message (uid, role, command category, head).

Reads the export of scripts/maintenance/export_selection_views.py
(matrix.csv, messages.csv, selections.csv) for the run.

  venv/bin/python scripts/maintenance/plot_selection_lifecycle.py \\
      data/r2/probes/ocsa_dsflash_selection/sympy__sympy-15875__r1 \\
      --zoom-steps 20 --out figures/sympy-15875_r1_lifecycle.png
"""
from __future__ import annotations

import argparse
import csv
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.colors import ListedColormap  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402
import numpy as np  # noqa: E402

# status codes in matrix.csv -> integer class for the raster
CODES = {"": 0, ".": 1, "T": 2, "W": 3, "P": 4, "D": 5}
COLORS = {
    0: "#ffffff00",  # not yet in the history: transparent
    1: "#52514e",    # protected
    2: "#b3b2ad",    # newest turns, verbatim
    3: "#2a78d6",    # kept whole
    4: "#a9c9ef",    # kept in part
    5: "#f1f0ec",    # dropped
}
REVIVE = "#eb6834"
TEXT = "#0b0b0b"
MUTED = "#52514e"
GRID = "#e4e3df"


def load(run_dir: str):
    rows = list(csv.DictReader(open(os.path.join(run_dir, "matrix.csv"))))
    steps = [k for k in rows[0].keys() if k.isdigit()]
    steps.sort(key=int)
    # Loops before the selector's first firing: nothing was selectable (every
    # message sat in the protected prefix or the keep_recent tail), so show the
    # context of those loops as protected cells rather than leaving them out.
    first = int(steps[0]) if steps else 1
    early = [str(k) for k in range(0, first)]
    for r in rows:
        protected = r["role"] == "system" or (r["role"] == "user" and r["cat"] == "no_command")
        for k in early:
            r[k] = ("." if protected else "T") if int(r["step"]) <= int(k) else ""
    steps = early + steps
    msgs = {r["uid"]: r for r in csv.DictReader(open(os.path.join(run_dir, "messages.csv")))}
    sel = {r["step"]: r for r in csv.DictReader(open(os.path.join(run_dir, "selections.csv")))} \
        if os.path.exists(os.path.join(run_dir, "selections.csv")) else {}
    return rows, steps, msgs, sel


def raster(rows, steps):
    grid = np.zeros((len(rows), len(steps)), dtype=int)
    revive = []
    for i, r in enumerate(rows):
        prev = ""
        for j, s in enumerate(steps):
            v = r.get(s, "") or ""
            grid[i, j] = CODES.get(v, 0)
            if prev == "D" and v in ("W", "P"):
                revive.append((i, j))
            if v:
                prev = v
    return grid, revive


def simple_label(r: dict) -> str:
    """Row label without uid / command text: the loop and the message's side of the model call."""
    if r["role"] == "system":
        return " " * len("loop NN  ") + "system prompt"
    if r["role"] == "user" and r["cat"] == "no_command":
        return " " * len("loop NN  ") + "task statement"
    if r["role"] == "assistant":
        side = "LLM reply (command)"
    elif r["cat"] == "format_error":
        side = "format error"
    else:
        side = "tool output"
    return f"loop {int(r['step']):>2}  {side}"


def draw(ax, grid, revive, steps, rows, *, labels: bool, dot_size: float, title: str, simple: bool = False):
    cmap = ListedColormap([COLORS[k] for k in range(6)])
    ax.imshow(grid, cmap=cmap, vmin=-0.5, vmax=5.5, aspect="auto", interpolation="nearest")
    if revive:
        ys, xs = zip(*revive)
        ax.scatter(xs, ys, s=dot_size, color=REVIVE, edgecolors="white", linewidths=0.4, zorder=3)
    ax.set_title(title, loc="left", fontsize=20, color=TEXT, pad=12)
    ax.set_xlabel("loop\n(context given to the LLM at this loop)", color=TEXT, fontsize=22, linespacing=1.4)
    n = len(steps)
    tick_every = 1 if n <= 40 else (5 if n <= 80 else (10 if n <= 160 else 20))
    xt = [j for j, s in enumerate(steps) if (int(s) + 1) % tick_every == 0 or j == 0]
    ax.set_xticks(xt)
    ax.set_xticklabels([str(int(steps[j]) + 1) for j in xt], fontsize=17, color=TEXT)
    if labels:
        ax.set_yticks(range(len(rows)))
        simple_labels = [simple_label(r) for r in rows]
        # write "loop N" only on the first row of each loop
        for i in range(1, len(rows)):
            if rows[i]["step"] == rows[i - 1]["step"]:
                simple_labels[i] = " " * len("loop NN") + simple_labels[i][len("loop NN"):]
        width = max(len(x) for x in simple_labels)
        ax.set_yticklabels(
            [x.ljust(width) for x in simple_labels] if simple else
            [f"loop {int(r['step']):>2}  {r['uid']}  {r['role'][:9]:9} {r['cat'][:12]:12} {r['head'][:44]:44}" for r in rows],
            fontsize=17 if simple else 7, family="monospace", color=TEXT)
        if simple:
            ax.set_ylabel("messages in the history (one row per message)", color=TEXT, fontsize=22, labelpad=22)
    elif simple:
        # whole run: a tick at the first row of every k-th loop
        n_loops = int(rows[-1]["step"]) if rows else 0
        every = 5 if n_loops <= 60 else (10 if n_loops <= 150 else 20)
        yt, yl = [], []
        seen = set()
        for i, r in enumerate(rows):
            st = int(r["step"])
            if st % every == 0 and st not in seen and st > 0:
                seen.add(st); yt.append(i); yl.append(f"loop {st}")
        ax.set_yticks(yt)
        ax.set_yticklabels(yl, fontsize=17, family="monospace", color=TEXT)
        ax.set_ylabel("messages in the history (one row per message)", color=TEXT, fontsize=22, labelpad=22)
    else:
        ax.set_ylabel("history message (order of arrival; newest at the bottom)", color=MUTED, fontsize=9)
        yt = list(range(0, len(rows), max(1, len(rows) // 8)))
        ax.set_yticks(yt)
        ax.set_yticklabels([rows[i]["uid"] for i in yt], fontsize=8, family="monospace", color=MUTED)
    for sp in ax.spines.values():
        sp.set_color(GRID)
    ax.tick_params(length=0)
    if labels:
        # thin separators between agent turns (steps) so pairs read as units
        for i in range(1, len(rows)):
            if rows[i]["step"] != rows[i - 1]["step"]:
                ax.axhline(i - 0.5, color="white", lw=1.2)
        for j in range(1, len(steps)):
            ax.axvline(j - 0.5, color="white", lw=1.2)


def legend(fig):
    handles = [
        Patch(color=COLORS[1], label="system prompt, task statement (protected)"),
        Patch(color=COLORS[2], label="newest 2 loops (protected)"),
        Patch(color=COLORS[3], label="kept whole by the selector"),
        Patch(color=COLORS[4], label="kept in part (line range)"),
        Patch(facecolor=COLORS[5], edgecolor=GRID, label="dropped"),
        Line2D([0], [0], marker="o", color="none", markerfacecolor=REVIVE, markeredgecolor="white",
               markersize=8, label="revived (dropped last loop, kept now)"),
    ]
    fig.legend(handles=handles, loc="lower center", ncol=3, frameon=False, fontsize=17,
               bbox_to_anchor=(0.5, 0.01))


def summarize(grid, revive, rows, steps):
    sel = grid[:, :] >= 3
    ever_dropped = int(((grid == 5).any(axis=1)).sum())
    ever_revived = len({i for i, _ in revive})
    kept_last = int((grid[:, -1] >= 1).sum() - (grid[:, -1] == 5).sum())
    return (f"{len(rows)} messages, {len(steps)} selection steps; "
            f"{ever_dropped} messages dropped at some point, {ever_revived} of them brought back at least once "
            f"({len(revive)} revivals in all); {kept_last} messages in the final context")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run_dir", help="an export folder of export_selection_views.py (holds matrix.csv)")
    ap.add_argument("--zoom-steps", type=int, default=20, help="last step of the zoom panel (default 20)")
    ap.add_argument("--out", required=True, help="PNG path")
    ap.add_argument("--title", default=None)
    ap.add_argument("--zoom-only", action="store_true", help="only the zoom panel (first --zoom-steps loops)")
    ap.add_argument("--simple-labels", action="store_true",
                    help="row labels as 'loop N  LLM output / LLM input' only (no uid, no command text)")
    ap.add_argument("--full", action="store_true",
                    help="the whole run in one panel (no per-row labels; a tick every few loops)")
    args = ap.parse_args()

    if args.full:
        rows, steps, msgs, sel = load(args.run_dir)
        grid, revive = raster(rows, steps)
        title = args.title or os.path.basename(os.path.normpath(args.run_dir)).replace("__", " ")
        fig = plt.figure(figsize=(22, 16), facecolor="white")
        ax1 = fig.add_subplot(111)
        fig.subplots_adjust(left=0.1, right=0.98, top=0.9, bottom=0.14)
        draw(ax1, grid, revive, steps, rows, labels=False, dot_size=14, simple=True, title=title)
        fig.suptitle("Which history messages the selector kept, trimmed, dropped and brought back"
                     f" (all {len(steps)} loops)",
                     x=0.02, ha="left", fontsize=24, color=TEXT, y=0.975)
        legend(fig)
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        fig.savefig(args.out, dpi=130)
        print(args.out)
        return

    rows, steps, msgs, sel = load(args.run_dir)
    grid, revive = raster(rows, steps)
    title = args.title or os.path.basename(os.path.normpath(args.run_dir)).replace("__", " ")

    zsteps = [s for s in steps if int(s) <= args.zoom_steps - 1]
    zrows = [r for r in rows if int(r["step"]) <= args.zoom_steps - 1]
    zgrid, zrev = raster(zrows, zsteps)

    if args.zoom_only:
        ncol = len(zsteps)
        fig = plt.figure(figsize=((0.6 * ncol + 8.0) if args.simple_labels else 14, 0.36 * len(zrows) + 4.5),
                         facecolor="white")
        ax1 = fig.add_subplot(111)
        width_in = fig.get_figwidth()
        fig.subplots_adjust(left=(6.6 / width_in) if args.simple_labels else 0.36, right=1 - 0.4 / width_in,
                            top=0.93, bottom=0.14)
        draw(ax1, zgrid, zrev, zsteps, zrows, labels=True, dot_size=110, simple=args.simple_labels,
             title=title)
        fig.suptitle("Which history messages the selector kept, trimmed, dropped and brought back"
                     f" (first {args.zoom_steps} loops)",
                     x=0.02, ha="left", fontsize=24, color=TEXT, y=0.985)
        legend(fig)
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        fig.savefig(args.out, dpi=130)
        print(args.out)
        return
    fig = plt.figure(figsize=(19, 10), facecolor="white")
    gs = fig.add_gridspec(1, 2, width_ratios=[1.0, 1.1], wspace=0.06, left=0.04, right=0.74, top=0.87, bottom=0.12)
    ax0 = fig.add_subplot(gs[0, 0])
    ax1 = fig.add_subplot(gs[0, 1])
    draw(ax0, grid, revive, steps, rows, labels=False, dot_size=6,
         title=f"{title}: whole run")
    draw(ax1, zgrid, zrev, zsteps, zrows, labels=True, dot_size=40,
         title=f"first {args.zoom_steps} steps, one row per message")
    ax1.yaxis.tick_right()
    fig.suptitle("Which history messages the selector kept, trimmed, dropped and brought back",
                 x=0.04, ha="left", fontsize=13, color=TEXT, y=0.965)
    fig.text(0.04, 0.915, summarize(grid, revive, rows, steps), fontsize=9.5, color=MUTED)
    legend(fig)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    fig.savefig(args.out, dpi=130)
    print(args.out)
    print(summarize(grid, revive, rows, steps))


if __name__ == "__main__":
    main()
