"""Selected ICLR plot bank: four maintained figure renderers.

Run `venv/bin/python ICLR_analysis/Iclr_plot_bank.py` to generate all figures.
Use --list or --help for selection and input/output options.
Shared visual conventions live in plot_style.py; data definitions and usage
are documented in Iclr_plot_bank.md. No files are written on import.
"""
from pathlib import Path
import argparse
import numpy as np
import pandas as pd
import matplotlib
if __name__ == "__main__":
    matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import to_rgba, LinearSegmentedColormap, Normalize
from matplotlib.lines import Line2D
from matplotlib.patches import Patch, Rectangle, Ellipse
try:
    from .plot_style import (PAPER_STYLE, KNOB_STYLE, ORDER, MK, PSTYLE, PDARK,
                             PLIGHT, pcol, pmark, prim_handles, save_figure)
    from .paper_figures import load_qwen_overview, load_q2_runs
except ImportError:
    from plot_style import (PAPER_STYLE, KNOB_STYLE, ORDER, MK, PSTYLE, PDARK,
                            PLIGHT, pcol, pmark, prim_handles, save_figure)
    from paper_figures import load_qwen_overview, load_q2_runs

ROOT = Path(__file__).resolve().parent.parent
ROWS = ORDER + ["FC"]
DT = dict(zip(["tr", "su-full", "su-partial", "ss", "ss-partial"], ["TR", "SU", "SU-p", "SS", "SS-p"]))
MARK = {p: MK["qwen35b"] for p in DT.values()}
FIGURES = {
    "q1_24_qwen_overview": "q1",
    "q1_26_knob_execution": "q1",
    "q2_qwen_task_map_only": "q1",
    "q3_policy_preferences_and_design": "q3",
}

def fig_qwen_overview(frames, columns=(0, 1, 2, 3, 4)):
    """Qwen reference layout, using the same style and marker helpers as O2.

    A wide master keeps the requested 2x5 arrangement legible. The two
    companion exports fit the 5.5-inch paper width without shrinking fonts.
    """
    wide = len(columns) == 5
    size = (11.0, 4.7) if wide else (5.5, 4.2 if len(columns) == 3 else 4.0)
    fig, axes = plt.subplots(2, len(columns), figsize=size, squeeze=False)
    fig.subplots_adjust(left=0.064 if wide else 0.112, right=0.987,
                        bottom=0.12 if wide else 0.14,
                        top=0.855 if wide else (0.73 if len(columns) == 3 else 0.755),
                        wspace=0.62 if wide else 0.72, hspace=0.42 if wide else 0.60)
    panels = [
        ("usage", "dres", "success", "token usage / FC", "success vs FC (pp)"),
        ("usage", "time", "latency", "token usage / FC", "wall-clock / FC"),
        ("usage", "bill", "billed cost", "token usage / FC", "billed input cost / FC"),
        ("resolve", "bill", "billed cost", "resolve rate (%)", "billed input cost / FC"),
        ("resolve", "time", "latency", "resolve rate (%)", "wall-clock / FC"),
    ]
    for row, (benchmark, label) in enumerate([("swebench", "SWE-bench"), ("terminalbench", "Terminal-Bench")]):
        frame = frames[benchmark]
        fc = frame.loc["FC"]
        # Shared metric limits within each row; include every displayed CI.
        bounds = {}
        for metric, reference in [("dres", 0), ("time", 1), ("bill", 1), ("resolve", fc.resolve)]:
            low = min(frame[metric + "_lo"].min(), reference)
            high = max(frame[metric + "_hi"].max(), reference)
            margin = max((high - low) * 0.075, 0.04 if metric in ["time", "bill"] else 0.5)
            bounds[metric] = (low - margin, high + margin)
        usage_bounds = (max(0, frame.usage.min() - 0.055), 1.045)
        for position, index in enumerate(columns):
            ax = axes[row, position]
            xmetric, ymetric, title, xlabel, ylabel = panels[index]
            ylim = bounds[ymetric]
            xlim = usage_bounds if xmetric == "usage" else bounds["resolve"]
            if ymetric == "bill":
                ax.axhspan(1, ylim[1], color="#f1f1f1", zorder=-1)
            ax.axhline(fc[ymetric], color="#999999", lw=0.6, ls="--", zorder=0)
            ax.axvline(fc[xmetric], color="#999999", lw=0.6, ls="--", zorder=0)
            if (xmetric, ymetric) == ("usage", "bill"):
                xx = np.array(xlim)
                ax.plot(xx, xx, color="#999999", lw=0.6, ls=":", zorder=0)
            for policy in ORDER:
                r = frame.loc[policy]
                errors = {"yerr": [[r[ymetric] - r[ymetric + "_lo"]], [r[ymetric + "_hi"] - r[ymetric]]]}
                ax.errorbar(r[xmetric], r[ymetric], **errors,
                            fmt="none", ecolor="#c8c8c8", elinewidth=0.7, capsize=0, zorder=1)
                pmark(ax, r[xmetric], r[ymetric], policy, MK["qwen35b"], s=36)
            ax.scatter(fc[xmetric], fc[ymetric], marker="*", color="black", s=110, zorder=5)
            ax.set_xlim(xlim); ax.set_ylim(ylim)
            separator = ", " if len(columns) == 2 else "\n"
            ax.set_title(label + separator + title, loc="left", pad=4, fontsize=9.5 if wide else 9)
            if row == 1:
                ax.set_xlabel(xlabel, labelpad=4, fontsize=9 if wide else 8.5)
            ax.set_ylabel(ylabel, labelpad=4, fontsize=9 if wide else 8.5)
            ax.tick_params(axis="both", labelsize=8.5 if wide else 8)
            ax.grid(alpha=0.2, lw=0.5)
            ax.locator_params(axis="both", nbins=4)

    handles = [Line2D([], [], marker="*", ls="", color="black", ms=10, label="full context")] + prim_handles()
    for handle in handles[1:]:
        handle.set_markersize(6)
    if wide:
        fig.text(0.014, 0.985, "Qwen", fontsize=12, weight="bold", va="top")
        fig.legend(handles=handles, loc="upper right", ncol=len(handles), frameon=False,
                   handletextpad=0.2, columnspacing=0.85, fontsize=7.5, bbox_to_anchor=(0.99, 1.0))
    else:
        fig.text(0.018, 0.985, "Qwen", fontsize=10, weight="bold", va="top")
        rows = [handles[:5], handles[5:10], handles[10:]]
        # Matplotlib fills legend columns; balance the rows for a larger key.
        sizes = [3, 3, 3, 2, 2]
        ordered = []
        row_index = [0, 0, 0]
        for size in sizes:
            for row in range(size):
                ordered.append(rows[row][row_index[row]])
                row_index[row] += 1
        fig.legend(handles=ordered, loc="upper center", ncol=5, frameon=False,
                   handletextpad=0.2, columnspacing=0.75, fontsize=7, bbox_to_anchor=(0.52, 0.935))
    return fig


def sweep_series(S, sweep, pol, col):
    """Sweep line including the shared primary point at its slot."""
    xs = [.3, .5, .7] if sweep == "depth" else [10., 15., 20.]
    prim_x = .5 if sweep == "depth" else 15.
    g = S[S.policy.eq(pol)]
    return xs, [g.loc[g.sweep.eq("primary") if v == prim_x
                      else g.sweep.eq(sweep) & g.x.eq(v), col].iloc[0] for v in xs]


def fig_knob_execution(S, resolve_grid):
    fc = S[S.policy.eq("FC")].iloc[0]
    with plt.rc_context(KNOB_STYLE):
        fig = plt.figure(figsize=(12.8, 5.8))
        grid = fig.add_gridspec(3, 3, width_ratios=[1, 1, 3.1],
                                left=.047, right=.993, bottom=.075, top=.875,
                                wspace=.20, hspace=.28)
        metrics = [("events", "Compressions / run", None),
                   ("bill", "Billed input (K tok)", 1e-3),
                   ("e2e", "Latency (s)", None)]
        handles = []
        for row, (col_name, ylab, scale) in enumerate(metrics):
            row_axes = []
            for col, sweep in enumerate(("depth", "threshold")):
                ax = fig.add_subplot(grid[row, col])
                row_axes.append(ax)
                for pol in DT.values():
                    xs, ys = sweep_series(S, sweep, pol, col_name)
                    ys = np.array(ys) * (scale or 1)
                    partial = pol.endswith("-p")
                    line, = ax.plot(range(3), ys, color=pcol(pol), marker=MARK[pol],
                                    ms=3.6, lw=1.2, ls="--" if partial else "-",
                                    mfc="white" if partial else pcol(pol), label=pol)
                    if row == 0 and col == 0:
                        handles.append(line)
                if col_name != "events":
                    ax.axhline(fc[col_name] * (scale or 1), color=".4", ls=":", lw=.9)
                    if col == 0:
                        ax.annotate("FC", (2.02, fc[col_name] * (scale or 1)),
                                    fontsize=6.5, color=".35", va="center")
                ax.set_xticks(range(3), ["0.3", "0.5", "0.7"] if sweep == "depth"
                              else ["10K", "15K", "20K"])
                ax.set_xlim(-.2, 2.2)
                if row == 0:
                    ax.set_ylim(0, 7.2)
                    ax.set_title("(a) Depth sweep" if col == 0 else "(b) Trigger sweep",
                                 loc="left", pad=8)
                if col == 0:
                    ax.set_ylabel(ylab)
                if row == 2:
                    ax.set_xlabel("Depth (fraction removed)" if sweep == "depth"
                                  else "Trigger threshold")
                ax.grid(axis="y", color="#ececec", lw=.5)
                ax.set_axisbelow(True)
                ax.spines[["top", "right"]].set_visible(False)
            lims = [a.get_ylim() for a in row_axes]
            lo, hi = min(l for l, _ in lims), max(h for _, h in lims)
            for a in row_axes:
                a.set_ylim(lo, hi)

        ax = fig.add_subplot(grid[:, 2])
        ax.set_axis_off()
        ax.set_title("(c) Resolve rate, cost, and latency", loc="left", pad=8)
        ax.set_xlim(0, 11.3)
        ax.set_ylim(.25, 19.35)
        left = 2.2
        ax.text(.02, 17.92, "Primitive", fontsize=8.5, va="center")
        ax.text(1.15, 17.92, "Trigger", fontsize=8.5, va="center")
        for j, (depth, label) in enumerate(((.3, "Shallow (0.3)"), (.5, "Depth 0.5"), (.7, "Deep (0.7)"))):
            center = left + 3*j + 1.5
            ax.text(center, 18.93, label, ha="center", va="center", fontsize=9.5, fontweight="bold")
            ax.plot([left + 3*j + .08, left + 3*j + 2.92], [18.45, 18.45], color=".65", lw=.5)
            if depth == .5:
                ax.fill_between([left + 3*j, left + 3*j + 3], .48, 18.43,
                                facecolor="#eef1f5", zorder=0)
            for k, label in enumerate(("RR (%)", "Cost/FC", "Lat. (s)")):
                ax.text(left + 3*j + k + .5, 17.92, label, ha="center", va="center", fontsize=8)
        ax.plot([0, 11.2], [17.36, 17.36], color=".35", lw=.65)
        for i, pol in enumerate(DT.values()):
            ytop = 16.66 - 3.4*i
            ax.text(.02, ytop-1, pol, color="black", fontweight="bold", fontsize=9.5, va="center")
            for k, budget in enumerate((10, 15, 20)):
                y = ytop-k
                g = resolve_grid[resolve_grid.policy.eq(pol) & resolve_grid.threshold_k.eq(budget)]
                assert len(g) == 3
                best, cheapest, fastest = g.resolve.max(), g.bill_vs_fc.min(), g.latency_all.min()
                ax.text(1.35, y, f"{budget}K", ha="center", fontsize=8.5, va="center")
                for j, depth in enumerate((.3, .5, .7)):
                    r = g[g.depth_removed.eq(depth)].iloc[0]
                    xresolve, xcost, xlatency = [left + 3*j + t + .5 for t in range(3)]
                    if np.isclose(r.resolve, best):
                        ax.add_patch(Rectangle((xresolve-.42, y-.35), .84, .70, fill=False,
                                               edgecolor=".15", linewidth=.9, linestyle="-", zorder=4))
                    if np.isclose(r.bill_vs_fc, cheapest):
                        ax.add_patch(Rectangle((xcost-.42, y-.35), .84, .70, fill=False,
                                               edgecolor=".15", linewidth=.9, linestyle=(0, (2.2, 1.3)), zorder=4))
                    if np.isclose(r.latency_all, fastest):
                        ax.add_patch(Ellipse((xlatency, y), .94, .76, fill=False,
                                             edgecolor=".15", linewidth=.9, zorder=4))
                    ax.text(xlatency, y, f"{r.latency_all:.0f}", ha="center", va="center", fontsize=9,
                            fontweight="bold" if np.isclose(r.latency_all, fastest) else "normal")
                    ax.text(xresolve, y, f"{100*r.resolve:.1f}", ha="center", va="center", fontsize=9,
                            fontweight="bold" if np.isclose(r.resolve, best) else "normal")
                    ax.text(xcost, y, f"{r.bill_vs_fc:.2f}", ha="center", va="center", fontsize=9,
                            fontweight="bold" if np.isclose(r.bill_vs_fc, cheapest) else "normal")
            if i < 4:
                ax.plot([0, 11.2], [ytop-2.7, ytop-2.7], color=".82", lw=.45)
        ax.plot([0, 11.2], [.48, .48], color=".35", lw=.65)
        # Legend placement follows the centers of the two plot blocks.
        left_center = (grid[0, 0].get_position(fig).x0 + grid[0, 1].get_position(fig).x1) / 2
        right_center = (grid[0, 2].get_position(fig).x0 + grid[0, 2].get_position(fig).x1) / 2
        fc_handle = Line2D([], [], color=".45", ls=":", lw=.9, label="FC")
        fig.legend(handles=handles + [fc_handle], loc="upper center", ncol=6, frameon=False,
                   bbox_to_anchor=(left_center, .985), handlelength=1.3, columnspacing=.65)
        winners = [Patch(facecolor="none", edgecolor=".15", linewidth=.9,
                         linestyle="-", label="Highest resolve"),
                   Patch(facecolor="none", edgecolor=".15", linewidth=.9,
                         linestyle=(0, (2.2, 1.3)), label="Lowest cost"),
                   Line2D([], [], linestyle="none", marker="o", markerfacecolor="none",
                          markeredgecolor=".15", markersize=7, label="Lowest latency"),
                   Line2D([], [], linestyle="none", label=f"FC: {100*fc.resolve:.1f}% / 1.00× / "
                          f"{resolve_grid.loc[resolve_grid.policy.eq('FC'), 'latency_all'].iloc[0]:.0f}s")]
        fig.legend(handles=winners, loc="upper center", ncol=4, frameon=False,
                   bbox_to_anchor=(right_center, .985), handlelength=1.4,
                   columnspacing=.6, handletextpad=.3, fontsize=8)
        return fig


def fig_task_map(solved, missed, shared):
    """Qwen SWE task map, then paired successful steps on SWE and Terminal-Bench."""
    n_tasks = len(solved)
    fig = plt.figure(figsize=(5.5,2.25))
    bottom, height = .17, .58
    totals = fig.add_axes([.144,bottom,.044,height])
    cell_width = .217 / n_tasks
    missed_width, solved_width = len(missed)*cell_width, len(shared)*cell_width
    miss_ax = fig.add_axes([.208,bottom,missed_width,height],sharey=totals)
    gain_left = .208 + missed_width + .016
    gain_ax = fig.add_axes([gain_left,bottom,.042,height],sharey=totals)
    shared_ax = fig.add_axes([gain_left+.061,bottom,solved_width,height],sharey=totals)
    loss_ax = fig.add_axes([.518,bottom,.037,height],sharey=totals)
    map_axes = [totals, miss_ax, gain_ax, shared_ax, loss_ax]
    all_axes = map_axes
    fig.text(.15, .95, 'Qwen · SWE-bench · 15K', fontsize=7.2)
    handles = [Line2D([], [], marker='s', ls='', mfc='#525252', mec='none', ms=3.5, label='Solved'),
               Line2D([], [], marker='x', ls='', color='#666666', ms=3.5, mew=.6, label='Lost'),
               Patch(facecolor='#f4f4f4', edgecolor='#cccccc', lw=.3, label='Neither')]
    fig.legend(handles=handles, ncol=3, loc='upper left', bbox_to_anchor=(.57,.993),
               frameon=False, fontsize=5.9, handlelength=1, handletextpad=.3,
               columnspacing=.7, borderaxespad=0)

    for ax,tasks,is_missed in [(miss_ax,missed,True),(shared_ax,shared,False)]:
        pixels = np.ones((len(ROWS),len(tasks),4))
        for j,p in enumerate(ROWS):
            for i,t in enumerate(tasks):
                if solved.loc[t,p]:pixels[j,i] = to_rgba(pcol(p))
                elif is_missed:pixels[j,i] = to_rgba('#f4f4f4')
        ax.imshow(pixels,interpolation='nearest',aspect='auto',extent=[-.5,len(tasks)-.5,len(ROWS)-.5,-.5])
        for x in np.arange(-.5,len(tasks)):ax.axvline(x,color='white',alpha=.45,lw=.18,zorder=2)
        for y in np.arange(.5,len(ROWS)):ax.axhline(y,color='white',lw=.55,zorder=3)
        ax.set_xlim(-.5,len(tasks)-.5)
    for j,p in enumerate(ROWS):
        lost = [i for i,t in enumerate(shared) if not solved.loc[t,p]]
        shared_ax.scatter(lost,[j]*len(lost),marker='x',s=4,color='#666666',linewidths=.4,zorder=4)
        hollow = p!='FC' and PSTYLE[p][2]
        totals.scatter(-.15,j,s=15 if p=='FC' else 10,marker='*' if p=='FC' else 'o',
                       facecolors='white' if hollow else pcol(p),edgecolors=pcol(p),linewidths=.8,
                       clip_on=False,transform=totals.get_yaxis_transform(),zorder=5)
        count = int(solved[p].sum())
        if count>solved.FC.sum():totals.axhspan(j-.44,j+.44,xmin=.02,xmax=.98,facecolor='#eaf2e5',edgecolor='none')
        totals.text(.5,j,str(count),ha='center',va='center',fontsize=6.2,
                    fontweight='bold' if count>solved.FC.sum() else 'normal',color='#333333')
        gain = int((~solved.FC&solved[p]).sum())
        loss = int((solved.FC&~solved[p]).sum())
        gain_ax.text(.5,j,f'+{gain}',ha='center',va='center',fontsize=6.2,color='#333333')
        loss_ax.text(.5,j,f'−{loss}' if loss else '0',ha='center',va='center',fontsize=6.2,color='#333333')
    for ax in map_axes:
        ax.set_xticks([])
        for spine in ax.spines.values():spine.set_visible(False)
    for ax in all_axes:
        if ax is not totals:ax.tick_params(axis='y',left=False,labelleft=False)
        for boundary in [1.5,5.5,7.5,10.5,11.5]:
            ax.axhline(boundary,color='white' if ax in [miss_ax,shared_ax] else '#e5e5e5',
                       lw=1.4 if ax in [miss_ax,shared_ax] else .35,zorder=3 if ax in [miss_ax,shared_ax] else 0)
    totals.set_ylim(len(ROWS)-.4,-.6)
    totals.set_yticks(np.arange(len(ROWS)),ROWS)
    totals.tick_params(axis='y',length=0,pad=11,labelsize=6.1)
    for ax in [totals,gain_ax,loss_ax]:ax.set_xlim(0,1)
    headers = [(totals,'Solved'),(miss_ax,f'FC missed\n{len(missed)} tasks'),
               (gain_ax,'Gained'),(shared_ax,f'FC solved\n{len(shared)} tasks'),(loss_ax,'Lost')]
    for ax,header in headers:
        ax.text(.5,1.025,header,transform=ax.transAxes,ha='center',va='bottom',fontsize=5.65)

    for ax in map_axes:
        pos = ax.get_position()
        ax.set_position([.15+(pos.x0-.144)*2.02, .035, pos.width*2.02, .735])
    return fig


def fig_policy_preferences(l, d):
    """Policy ranks and paired design contrasts from the audited Q3 exports."""
    pol=['FC']+ORDER;models=['qwen35b','devstral24b','glm47flash'];names=['Qwen','Devstral','GLM']
    pairs=[('SS-p','SS'),('TRC+SS','SS'),('OTRC','TRC'),('OTRC+SS-p','OTRC')]
    labels=['Preserve recent history\nSS-p − SS','Clear before rewriting\nTRC+SS − SS','Clear every step\nOTRC − TRC','Add partial rewriting\nOTRC+SS-p − OTRC']
    # Neutral rank shading keeps policy-family hues reserved for row labels.
    rankmap=LinearSegmentedColormap.from_list('rank',[PDARK['rule'],'#f3f8fc']);rn=Normalize(1,13)
    diffmap=LinearSegmentedColormap.from_list('diff',[PDARK['llm'],PLIGHT['llm'],'#fafafa',PLIGHT['rule'],PDARK['rule']]);dn=Normalize(-20,20)
    with plt.rc_context(PAPER_STYLE):
     fig=plt.figure(figsize=(6.75,2.25))
     ax=fig.add_axes([.09,.205,.43,.575])
     vals=np.empty((13,9)); ranks=np.empty_like(vals)
     for j,m in enumerate(models):
      for k,metric in enumerate(['resolve','latency_ratio','billed_input_ratio']):
       a=l[(l.benchmark=='SWE-bench')&(l.model_key==m)&(l.metric==metric)].set_index('policy').loc[pol]
       vals[:,3*j+k]=a.value;ranks[:,3*j+k]=a['rank']
     im=ax.imshow(ranks,cmap=rankmap,norm=rn,aspect='auto')
     for col in range(9):
      v=vals[:,col];best=np.isclose(v,v.max() if col%3==0 else v.min(),atol=1e-10,rtol=0)
      for row in range(13):
       shade=np.dot(rankmap(rn(ranks[row,col]))[:3],[.2126,.7152,.0722])
       label=f'{v[row]:.1f}' if col%3==0 else f'{v[row]:.2f}'
       ax.text(col,row,label,ha='center',va='center',fontsize=5.5,color='white' if shade<.53 else '#222222',fontweight='bold' if best[row] else 'normal')
       if best[row]:
        ax.add_patch(Rectangle((col-.46,row-.43),.92,.86,fill=False,lw=.7,edgecolor='white'))
        ax.add_patch(Rectangle((col-.48,row-.46),.96,.92,fill=False,lw=.5,edgecolor='#222222'))
     ax.set_yticks(range(13),pol)
     for tick,p in zip(ax.get_yticklabels(),pol):tick.set_color(pcol(p))
     ax.set_xticks(range(9),['Res. ↑\n(%)','Lat. ↓\n/ FC','Bill ↓\n/ FC']*3);ax.xaxis.tick_top()
     for j,(name,bud) in enumerate(zip(names,['15K','21K','13K'])):
      ax.text((j+.5)/3,1.20,f'{name} ({bud})',transform=ax.transAxes,ha='center',fontsize=6)
     for x in [2.5,5.5]:ax.axvline(x,color='white',lw=2.5)
     def clean(a,nr,nc):
      a.set_xticks(np.arange(-.5,nc,1),minor=True);a.set_yticks(np.arange(-.5,nr,1),minor=True)
      a.grid(which='minor',color='white',lw=.6);a.tick_params(which='both',length=0,pad=2,labelsize=5.5)
      for s in a.spines.values():s.set_visible(False)
     clean(ax,13,9)
     fig.text(.012,.965,'(a) Policy preferences · SWE-bench',fontsize=7)
 
     decisions=['Preserve\nrecent history','Clear before\nrewriting','Clear every\nstep','Add partial\nrewriting']
     comparisons=['(SS-p vs SS)','(TRC+SS vs SS)','(OTRC vs TRC)','(OTRC+SS-p\nvs OTRC)']
     for bi,bench in enumerate(['SWE-bench','Terminal-Bench']):
      bottom=[.50,.205][bi];ar=fig.add_axes([.635,bottom,.355,.22]);v=np.empty((3,4));sig=np.zeros((3,4),bool)
      for j,(p,q) in enumerate(pairs):
       for i,m in enumerate(models):
        r=d[(d.benchmark==bench)&(d.model_key==m)&(d.p==p)&(d.q==q)].iloc[0]
        v[i,j]=r.estimate;sig[i,j]=r.lo>0 or r.hi<0
      dm=ar.imshow(v,cmap=diffmap,norm=dn,aspect='auto')
      for i in range(3):
       for j in range(4):
        lum=np.dot(diffmap(dn(v[i,j]))[:3],[.2126,.7152,.0722]);val=0 if abs(v[i,j])<1e-9 else v[i,j]
        ar.text(j,i,f'{val:+.1f}'+('*' if sig[i,j] else ''),ha='center',va='center',fontsize=6,color='white' if lum<.50 else '#222222')
      ar.set_yticks(range(3),names);ar.set_xticks([]);clean(ar,3,4)
      if bi==0:
       for j,(decision,comparison) in enumerate(zip(decisions,comparisons)):
        ar.text(j,1.80,decision,transform=ar.get_xaxis_transform(),ha='center',va='top',fontsize=5.2,fontweight='bold',linespacing=1.05)
        ar.text(j,1.46,comparison,transform=ar.get_xaxis_transform(),ha='center',va='top',fontsize=5.2,linespacing=1.05)
      fig.text(.635,bottom+.228,bench,fontsize=5.8,fontweight='bold')
     fig.text(.565,.965,'(b) Design decisions',fontsize=7)
     c=fig.colorbar(im,cax=fig.add_axes([.09,.165,.43,.016]),orientation='horizontal');c.set_ticks([1,4,7,10,13]);c.outline.set_visible(False);c.ax.tick_params(length=2,pad=1,labelsize=5)
     c.set_label('Policy rank (darker = better)',fontsize=5.5,labelpad=1)
     c=fig.colorbar(dm,cax=fig.add_axes([.635,.165,.355,.016]),orientation='horizontal');c.set_ticks([-20,-10,0,10,20]);c.outline.set_visible(False);c.ax.tick_params(length=2,pad=1,labelsize=5)
     c.set_label('Resolve-rate change (pp)',fontsize=5.5,labelpad=1)
    return fig


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--figure", nargs="+", choices=["all", *FIGURES], default=["all"])
    parser.add_argument("--list", action="store_true", help="List the selected figure names")
    parser.add_argument("--data-dir", type=Path, default=ROOT / "ICLR_analysis")
    parser.add_argument("--q3-data-dir", type=Path, default=ROOT / "ICLR_analysis/plots/q3")
    parser.add_argument("--outcomes", type=Path, default=ROOT / "analysis/outcomes/swebench_outcomes.csv")
    parser.add_argument("--tasks", type=Path, default=ROOT / "task_lists/p100_all_100_tasks.json")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "ICLR_analysis/plots",
                        help="Output root; preserves q1/ and q3/ subdirectories")
    args = parser.parse_args(argv)
    if args.list:
        print("\n".join(FIGURES))
        return
    selected = list(FIGURES) if "all" in args.figure else list(dict.fromkeys(args.figure))
    for name in selected:
        with plt.rc_context(PAPER_STYLE):
            if name == "q1_24_qwen_overview":
                fig = fig_qwen_overview(load_qwen_overview(args.data_dir))
            elif name == "q1_26_knob_execution":
                summary = pd.read_csv(args.data_dir / "q1_knob_execution.csv")
                grid = pd.read_csv(args.data_dir / "q1_knob_execution_resolve_grid.csv")
                if len(grid) != 46 or grid.duplicated(["policy", "threshold_k", "depth_removed"]).any():
                    raise ValueError("Knob grid must contain 45 distinct settings plus FC")
                fig = fig_knob_execution(summary, grid)
            elif name == "q2_qwen_task_map_only":
                runs = load_q2_runs(args.outcomes, args.tasks)
                solved = runs.groupby(["task", "policy"]).res.sum().unstack().loc[:, ROWS].ge(2)
                missed = sorted(solved.index[~solved.FC], key=lambda t: (-solved.loc[t, ORDER].sum(), t))
                shared = sorted(solved.index[solved.FC], key=lambda t: (-solved.loc[t, ORDER].sum(), t))
                fig = fig_task_map(solved, missed, shared)
            else:
                values = pd.read_csv(args.q3_data_dir / "q3_combined_policy_values.csv")
                contrasts = pd.read_csv(args.q3_data_dir / "q3_combined_design_contrasts.csv")
                if values.duplicated(["benchmark", "model_key", "policy", "metric"]).any():
                    raise ValueError("Duplicate Q3 policy values")
                if contrasts.duplicated(["benchmark", "model_key", "p", "q"]).any():
                    raise ValueError("Duplicate Q3 design contrasts")
                fig = fig_policy_preferences(values, contrasts)
            try:
                save_figure(fig, args.output_dir / FIGURES[name], name,
                            dpi=300 if name.startswith("q3") else 200)
            finally:
                plt.close(fig)
        print(f"Wrote {args.output_dir / FIGURES[name] / name}.{{pdf,png}}", flush=True)


if __name__ == "__main__":
    main()
