#!/usr/bin/env python3
"""Render DASHBOARD.html — the human-friendly coverage dashboard.

Reads COVERAGE.csv and COVERAGE_TB.csv (regenerate them first with the
benchmark-specific coverage builders) and writes a self-contained HTML page
at the repo root. Re-run after every completed run:

    python dashboard/build_coverage_sb.py
    python dashboard/build_coverage_tb.py
    python dashboard/build_dashboard.py
"""

import argparse
import csv
import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "DASHBOARD.html"
HISTORY = ROOT / "dashboard_progress_history.jsonl"
RATE_WINDOW_HOURS = 3
HISTORY_RETENTION_DAYS = 14

MAIN = "Qwen3.5-35B-A3B"

FAMILIES = [
    ("Depth-tunable", ["TR", "SU-full", "SU-partial", "SS", "SS-partial"]),
    ("Depth-invariant", ["TRC", "TRC+SU", "TRC+SS", "OTRC+TR", "OTRC+SU-partial", "OTRC+SS-partial"]),
    ("∞-budget baselines", ["FC", "OTRC"]),
]
DEPTHS = ["0.3", "0.5", "0.7"]

BUDGET_ORDER = {
    "2k": 2, "3k": 3, "4k": 4, "5k": 5, "7k": 7,
    "8k": 8, "10k": 10, "12k": 12, "13k": 13,
    "15k": 15, "17k": 17, "20k": 20, "21k": 21, "24k": 24,
    "35k": 35, "38k": 38, "43k": 43, "45k": 45, "49k": 49,
    "58k": 58,
    "inf": 999,
}


def load_cells():
    swe_cells = {}
    tb_cells = {}
    invariant = {
        "FC", "OTRC", "TRC", "TRC+SU", "TRC+SS",
        "OTRC+TR", "OTRC+SU-partial", "OTRC+SS-partial",
    }
    for path, benchmark in (
        (ROOT / "COVERAGE.csv", "swebench"),
        (ROOT / "COVERAGE_TB.csv", "terminal-bench"),
    ):
        for r in csv.DictReader(open(path)):
            budget = r["budget"].lower()
            if benchmark == "terminal-bench":
                depth = "DI" if r["primitive"] in invariant else r["depth"]
                tb_cells[(r["model"], r["primitive"], budget, depth)] = r
            else:
                swe_cells[(r["model"], r["primitive"], budget, r["depth"])] = r
    return swe_cells, tb_cells


def chip(cell, depth):
    """One depth chip. State drives color: filled=have, red=missing,
    grey=out-of-scope extra."""
    if cell is None:
        return f'<span class="chip none">{depth}</span>'
    status, notes = cell["status"], cell["notes"]
    title = (f'{cell["model"]} · {cell["primitive"]} · {cell["budget"]} · d={cell["depth"]} — '
             f'{cell["status"]}; {cell["tasks_on_disk"]} tasks / {cell["runs_on_disk"]} runs on disk; '
             f'min {cell.get("runs_per_task_min", "?")} runs/task; '
             f'cohort {cell["cohort_covered"] or "—"}'
             + (f'; {notes}' if notes else ''))
    if status == "MISSING":
        cls = "missing"
    elif status == "EXTRA":
        cls = "extra"
    else:  # COMPLETE / HAVE / PARTIAL
        cls = "have" if status != "PARTIAL" else "partial"
    # cohort is the second visual axis: solid fill = full P100, outline = ABL-30
    if cls != "missing" and cell["cohort_covered"]:
        cls += " p100" if cell["cohort_covered"].startswith("P100") else " abl"
    return f'<span class="chip {cls}" title="{title}">{depth}</span>'


def matrix(cells, model, budgets, primitives_by_family, depths=DEPTHS):
    head = "".join(f'<th>{b if b != "inf" else "∞"}</th>' for b in budgets)
    body = []
    for fam, prims in primitives_by_family:
        present = [p for p in prims
                   if any((model, p, b, d) in cells for b in budgets for d in depths)]
        if not present:
            continue
        body.append(f'<tr class="fam"><td colspan="{len(budgets)+1}">{fam}</td></tr>')
        for p in present:
            tds = []
            for b in budgets:
                found = [chip(cells.get((model, p, b, d)), d)
                         for d in depths if (model, p, b, d) in cells]
                tds.append(f'<td>{"".join(found) or "<span class=chipdash>–</span>"}</td>')
            body.append(f'<tr><td class="prim">{p}</td>{"".join(tds)}</tr>')
    return (f'<div class="tablewrap"><table><thead><tr><th>primitive</th>{head}</tr></thead>'
            f'<tbody>{"".join(body)}</tbody></table></div>')


def budgets_for(cells, model):
    bs = {k[2] for k in cells if k[0] == model}
    return sorted(bs, key=lambda b: BUDGET_ORDER.get(b, 500))


def plan_chip(label, cohort, title):
    """A chip in a planned-experiment matrix (separate from coverage state)."""
    return f'<span class="plan-chip {cohort}" title="{title}">{label}</span>'


def planned_matrix(budgets, rows):
    """Render a roadmap matrix with the same visual grammar as the coverage grid."""
    head = "".join(f"<th>{budget}</th>" for budget in budgets)
    body = []
    for label, cells in rows:
        if cells is None:
            body.append(f'<tr class="fam"><td colspan="{len(budgets) + 1}">{label}</td></tr>')
            continue
        rendered = []
        for cell in cells:
            rendered.append(f'<td>{cell or "<span class=chipdash>–</span>"}</td>')
        body.append(f'<tr><td class="prim">{label}</td>{"".join(rendered)}</tr>')
    return (
        '<div class="tablewrap plan-table"><table><thead><tr><th>primitive</th>'
        f'{head}</tr></thead><tbody>{"".join(body)}</tbody></table></div>'
    )


def _int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def coverage_progress(
    cells, model, primitives, budget, depth, tasks, runs_per_task, baseline_runs=0
):
    """Aggregate SWE progress without exposing one row per primitive."""
    target_each = tasks * (runs_per_task - baseline_runs)
    total_required_each = tasks * runs_per_task
    actual_total = 0
    complete = True
    for primitive in primitives:
        cell = cells.get((model, primitive, budget.lower(), depth))
        if not cell:
            complete = False
            continue
        disk_tasks = _int(cell.get("tasks_on_disk"))
        disk_runs = _int(cell.get("runs_on_disk"))
        min_runs = _int(cell.get("runs_per_task_min"))
        cohort = (
            "p100" if tasks == 100 else
            "abl30" if tasks == 30 else
            "tb15" if tasks == 15 else
            "tb40" if tasks == 40 else
            "tb20" if tasks == 20 else
            "all" if tasks == 80 else
            None
        )
        capped_key = f"runs_capped_{runs_per_task}_{cohort}" if cohort else None
        baseline_key = f"runs_capped_{baseline_runs}_{cohort}" if cohort and baseline_runs else None
        has_exact_counts = capped_key and cell.get(capped_key, "") != ""

        if has_exact_counts:
            # These counts are constructed task-by-task in the benchmark's
            # coverage builder.
            # Subtracting two capped totals exactly counts runs in
            # (baseline_runs, runs_per_task], without cohort scaling or
            # over-counting tasks that happen to have extra retries.
            total_progress = _int(cell[capped_key])
            baseline_progress = _int(cell[baseline_key]) if baseline_key else 0
            incremental_progress = total_progress - baseline_progress
        elif disk_tasks:
            # Backward-compatible fallback for coverage files generated before
            # cohort-specific capped counts were added.
            disk_progress = round(disk_runs * min(tasks, disk_tasks) / disk_tasks)
            total_progress = disk_progress
            incremental_progress = max(0, total_progress - tasks * baseline_runs)
        else:
            total_progress = 0
            incremental_progress = 0
        actual_total += min(target_each, incremental_progress)
        exact_done = has_exact_counts and total_progress >= total_required_each
        disk_done = exact_done or (not has_exact_counts and disk_tasks >= tasks and (
            min_runs >= runs_per_task
            or (min_runs == 0 and disk_runs >= disk_tasks * runs_per_task)
        ))
        complete = complete and disk_done
    return complete, actual_total, target_each * len(primitives)


def status_badge(complete, actual, target):
    """Keep status data structured until its budget-labelled chip is rendered."""
    return complete, actual, target


def tracking_table(rows):
    """Rows: model, scope, depth, budget, dataset, target, status HTML."""
    grouped = {}
    group_order = []
    for row in rows:
        key = (row[0], row[1], row[2], row[4], row[5])
        if key not in grouped:
            grouped[key] = []
            group_order.append(key)
        grouped[key].append((row[3], row[6]))

    compact_rows = []
    for model, scope, depth, dataset, target in group_order:
        budget_statuses = grouped[(model, scope, depth, dataset, target)]
        chips = []
        for budget, (complete, actual, target_runs) in budget_statuses:
            cls = "done" if complete else "pending"
            label = budget if complete else f"{budget}, {actual:,}/{target_runs:,} runs"
            chips.append(
                f'<span class="track-status {cls}">{label}</span>'
            )
        budget_progress = f'<div class="status-chips">{"".join(chips)}</div>'
        compact_rows.append([dataset, model, scope, depth, budget_progress])

    rendered_rows = []
    previous = None
    for row in compact_rows:
        display = list(row)
        if previous is not None and row[0] == previous[0]:
            display[0] = ""
            if row[1] == previous[1]:
                display[1] = ""
                if row[2] == previous[2]:
                    display[2] = ""
                    if row[3] == previous[3]:
                        display[3] = ""
        tds = "".join(
            '<td class="repeat"></td>' if cell == "" else f'<td>{cell}</td>'
            for cell in display
        )
        rendered_rows.append(f"<tr>{tds}</tr>")
        previous = row
    body = "".join(rendered_rows)
    return (
        '<div class="tablewrap tracking"><table><thead><tr>'
        '<th>dataset</th><th>model</th><th>primitive scope</th>'
        '<th>depth</th><th>budget</th></tr></thead>'
        f'<tbody>{body}</tbody></table></div>'
    )


def load_progress_history():
    """Load valid progress snapshots, tolerating a partial final JSONL line."""
    snapshots = []
    if not HISTORY.exists():
        return snapshots
    for line in HISTORY.read_text().splitlines():
        try:
            item = json.loads(line)
            item["when"] = datetime.fromisoformat(item["timestamp"].replace("Z", "+00:00"))
            if isinstance(item.get("progress"), dict):
                snapshots.append(item)
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            continue
    return sorted(snapshots, key=lambda item: item["when"])


def recent_rate(history, key, actual, now, hours=RATE_WINDOW_HOURS):
    """Return average runs/hour using the sample closest to the window start."""
    candidates = [item for item in history if key in item["progress"] and item["when"] < now]
    if not candidates:
        return None
    cutoff = now - timedelta(hours=hours)
    baseline = min(candidates, key=lambda item: abs((item["when"] - cutoff).total_seconds()))
    elapsed_hours = (now - baseline["when"]).total_seconds() / 3600
    delta = actual - _int(baseline["progress"][key])
    if elapsed_hours <= 0 or delta < 0:
        return None
    return delta / elapsed_hours


def since_previous(history, key, actual, now):
    """Return growth since the preceding published snapshot.

    The publisher records the current coverage before GitHub Actions rebuilds
    the page.  In that rebuild, compare the matching latest snapshot with its
    predecessor instead of comparing timestamps from two different machines.
    """
    candidates = [item for item in history if key in item["progress"]]
    if not candidates:
        return None

    latest = max(candidates, key=lambda item: item["when"])
    if _int(latest["progress"][key]) == actual:
        predecessors = [item for item in candidates if item["when"] < latest["when"]]
        if not predecessors:
            return None
        previous = max(predecessors, key=lambda item: item["when"])
        elapsed_seconds = (latest["when"] - previous["when"]).total_seconds()
    else:
        previous = latest
        elapsed_seconds = (now - previous["when"]).total_seconds()

    delta = actual - _int(previous["progress"][key])
    if elapsed_seconds <= 0 or delta < 0:
        return None
    return delta, elapsed_seconds


def format_elapsed(seconds):
    """Format a snapshot interval compactly for the progress header."""
    minutes = max(0, round(seconds / 60))
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h {minutes}m" if minutes else f"{hours}h"
    return f"{minutes}m"


def write_progress_history(history, progress, now):
    """Append this build's snapshot and keep the tracked file compact."""
    cutoff = now - timedelta(days=HISTORY_RETENTION_DAYS)
    kept = [item for item in history if item["when"] >= cutoff]
    kept.append({"timestamp": now.isoformat().replace("+00:00", "Z"), "progress": progress})
    lines = []
    for item in kept:
        lines.append(json.dumps({
            "timestamp": item["timestamp"],
            "progress": item["progress"],
        }, sort_keys=True, separators=(",", ":")))
    HISTORY.write_text("\n".join(lines) + "\n")


def progress_bar(rows, key, history, now, snapshot):
    """Horizontal aggregate progress bar for one plan section."""
    actual = sum(row[6][1] for row in rows)
    target = sum(row[6][2] for row in rows)
    snapshot[key] = actual
    percent = min(100, (actual / target * 100) if target else 0)
    rate = recent_rate(history, key, actual, now)
    rate_text = "— runs/hour" if rate is None else f"{rate:,.1f} runs/hour"
    previous = since_previous(history, key, actual, now)
    previous_text = (
        "since last: — runs / —"
        if previous is None else
        f"since last: +{previous[0]:,} runs / {format_elapsed(previous[1])}"
    )
    return (
        '<div class="section-progress">'
        '<div class="progress-meta"><span>Progress</span>'
        '<span class="progress-numbers">'
        f'<span class="progress-rate" title="Average over the last {RATE_WINDOW_HOURS} hours">'
        f'last {RATE_WINDOW_HOURS}h: {rate_text}</span>'
        f'<span class="progress-since" title="Increase and elapsed time since the previous snapshot">'
        f'{previous_text}</span>'
        f'<strong>{actual:,} / {target:,} runs</strong></span></div>'
        '<div class="progress-track" role="progressbar" '
        f'aria-valuenow="{actual}" aria-valuemin="0" aria-valuemax="{target}">'
        f'<span style="width:{percent:.1f}%"></span></div></div>'
    )


def summarizer_tracking_table(rows):
    """Priority 4 table: agent and summarizer get separate columns; no depth column."""
    body = []
    previous = None
    for exp_id, dataset, agent, summarizer, primitives, budget, status in rows:
        complete, actual, target = status
        cls = "done" if complete else "pending"
        label = budget if complete else f"{budget}, {actual:,}/{target:,} runs"
        display = [exp_id, dataset, agent, summarizer, primitives,
                   f'<span class="track-status {cls}">{label}</span>']
        if previous is not None:
            # Only suppress adjacent repetitions within this compact four-row table.
            for i in range(1, 5):
                if display[i] == previous[i]:
                    display[i] = ""
        body.append('<tr>' + ''.join(
            '<td class="repeat"></td>' if cell == "" else f'<td>{cell}</td>'
            for cell in display
        ) + '</tr>')
        previous = [exp_id, dataset, agent, summarizer, primitives,
                    f'<span class="track-status {cls}">{label}</span>']
    return (
        '<div class="tablewrap tracking summarizer-tracking"><table><thead><tr>'
        '<th>experiment</th><th>dataset</th><th>agent model</th>'
        '<th>summarizer model</th><th>primitives</th><th>budget</th>'
        f'</tr></thead><tbody>{"".join(body)}</tbody></table></div>'
    )


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--record-history", action="store_true",
        help="append progress totals used for runs/hour calculations",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    cells, tb_cells = load_cells()
    rows = list(cells.values())
    tb_rows = list(tb_cells.values())
    generated_at = datetime.now(ZoneInfo("America/Chicago")).strftime(
        "%Y-%m-%d %H:%M %Z"
    )

    # ---- headline stats -----------------------------------------------------
    disk_runs = sum(int(r["runs_on_disk"]) for r in rows)
    n_missing = sum(r["status"] == "MISSING" for r in rows)

    tb_runs = sum(_int(r.get("runs_on_disk")) for r in tb_rows)

    covered = [r for r in rows if r["cohort_covered"]]
    n_p100 = sum(r["cohort_covered"].startswith("P100") for r in covered)
    n_abl = len(covered) - n_p100

    stats = [
        (str(1 + bool(tb_rows)), "benchmarks with valid results"),
        ("6", "models"),
        ("100", "SWE-bench tasks (P100)"),
        ("11 + 2", "primitives + baselines"),
        (f"{n_p100} / {n_abl}", "cells at full P100 / ABL-30 only"),
        (f"{disk_runs:,}", "trajectories on this disk"),
        (f"{tb_runs:,}", "valid Terminal-Bench runs in COVERAGE_TB.csv"),
    ]
    stat_html = "".join(
        f'<div class="stat"><div class="n">{n}</div><div class="l">{l}</div></div>'
        for n, l in stats)

    # ---- attention panel ----------------------------------------------------
    attention = []
    for r in rows:
        if r["status"] == "MISSING":
            attention.append(f'<li><span class="dot missing"></span><strong>{r["model"]} · '
                             f'{r["primitive"]} @ {"∞" if r["budget"] == "inf" else r["budget"]}'
                             f'</strong> — not run yet (required: {r["required_cohort"]}).</li>')
    # ---- expansion model cards ----------------------------------------------
    exp_cards = []
    for model, note in [
        ("Devstral-Small-2-24B", "Albus. Own calibrated budgets. Shows the −33.4pp clearing reversal at ∞."),
        ("Qwen2.5-Coder-32B", "Albus. FC = OTRC = 10.0% at ∞ — floor-limited, uninformative."),
        ("Llama-3.3-70B", "Albus. FC@∞ done; OTRC@∞ is the one missing arm."),
    ]:
        exp_cards.append(
            f'<div class="card"><h3>{model}</h3><p class="note">{note}</p>'
            + matrix(cells, model, budgets_for(cells, model), FAMILIES) + '</div>')

    # quant sweep: 4 precision variants of a different base model
    quant_models = sorted({r["model"] for r in rows if r["model"].startswith("Qwen3-30B-A3B-2507/")})
    qprims = ["FC", "TR", "SU-full", "TRC+SS"]
    qhead = "".join(f"<th>{m.split('/')[1]}</th>" for m in quant_models)
    qbody = []
    for p in qprims:
        tds = []
        for m in quant_models:
            b = "inf" if p == "FC" else "20k"
            tds.append(f'<td>{chip(cells.get((m, p, b, "0.5")), "0.5")}</td>')
        label = p + (" @∞" if p == "FC" else " @20k")
        qbody.append(f'<tr><td class="prim">{label}</td>{"".join(tds)}</tr>')
    quant_card = (
        '<div class="card"><h3>Precision sweep — Qwen3-30B-A3B-Instruct-2507</h3>'
        '<p class="note">Different base model (appendix only). ABL-30, d=0.5, 2 runs. '
        'Resolve at ∞: fp16 9.17% &gt; fp8 7.08% &gt; gptq 3.33% &gt; awq 2.92%.</p>'
        f'<div class="tablewrap"><table><thead><tr><th>cell</th>{qhead}</tr></thead>'
        f'<tbody>{"".join(qbody)}</tbody></table></div></div>')

    main_matrix = matrix(cells, MAIN, ["10k", "15k", "20k", "inf"], FAMILIES)

    # ---- follow-up experiment roadmap (Priority 1–4) -----------------------
    tunable = ["TR", "SU-full", "SU-partial", "SS", "SS-partial"]
    invariant = ["TRC", "TRC+SU", "TRC+SS", "OTRC+TR", "OTRC+SU-partial", "OTRC+SS-partial"]

    def depth_set(main_name, abl_name, budget, include_main=True, include_abl=True):
        parts = []
        if include_abl:
            parts.append(plan_chip("0.3", "ablation", f"{abl_name} · {budget} · depth 0.3 · planned"))
        if include_main:
            parts.append(plan_chip("0.5", "main", f"{main_name} · {budget} · depth 0.5 · planned"))
        elif include_abl:
            parts.append(plan_chip("0.5", "ablation", f"{abl_name} · {budget} · depth 0.5 · planned"))
        if include_abl:
            parts.append(plan_chip("0.7", "ablation", f"{abl_name} · {budget} · depth 0.7 · planned"))
        return "".join(parts)

    p1_rows = [("Depth-tunable", None)]
    p1_rows += [(p, [depth_set("SB:P-100", "SB:ABL-30", b) for b in ("10K", "15K", "20K")] + [""])
                for p in tunable]
    p1_rows.append(("Depth-invariant", None))
    p1_rows += [(p, [plan_chip("DI", "main", f"SB:P-100 · {b} · depth-invariant · planned")
                     for b in ("10K", "15K", "20K")] + [""])
                for p in invariant]
    p1_rows.append(("∞-budget baselines", None))
    p1_rows += [(p, ["", "", "", plan_chip("DI", "main", "SB:P-100 · unlimited budget · depth-invariant · planned")])
                for p in ("FC", "OTRC")]
    p1_matrix = planned_matrix(["10K", "15K", "20K", "∞"], p1_rows)

    def model_plan_matrix(budgets, main_name, abl_name, calibration=False):
        rows_ = [("Depth-tunable", None)]
        for p in tunable:
            grid = []
            for i, b in enumerate(budgets[:3]):
                cell = depth_set(main_name, abl_name, b, include_main=(i == 1), include_abl=True)
                if calibration:
                    cell = cell.replace('plan-chip ablation', 'plan-chip calibration')
                    if i == 1:
                        cell = cell.replace('plan-chip main', 'plan-chip calibration-main')
                grid.append(cell)
            rows_.append((p, grid + [""]))
        rows_.append(("Depth-invariant", None))
        for p in invariant:
            grid = []
            for i, b in enumerate(budgets[:3]):
                cohort = "main" if i == 1 else "ablation"
                if calibration:
                    cohort = "calibration-main" if i == 1 else "calibration"
                dataset = main_name if i == 1 else abl_name
                grid.append(plan_chip("DI", cohort, f"{dataset} · {b} · depth-invariant · planned"))
            rows_.append((p, grid + [""]))
        rows_.append(("∞-budget baselines", None))
        rows_ += [(p, ["", "", "", plan_chip("DI", "main", f"{main_name} · unlimited budget · depth-invariant · planned")])
                  for p in ("FC", "OTRC")]
        return planned_matrix(budgets, rows_)

    p2_devstral = model_plan_matrix(["17K", "21K", "24K", "∞"], "SB:P-100", "SB:ABL-30")
    p2_glm = model_plan_matrix(["10K", "13K", "15K", "∞"], "SB:P-100", "SB:ABL-30")
    p3_qwen = model_plan_matrix(
        ["2K", "3K", "4K", "∞"],
        "TB:P-40", "TB:P-15", calibration=True,
    )
    p3_devstral = model_plan_matrix(
        ["3K", "4K", "7K", "∞"],
        "TB:P-40", "TB:P-15", calibration=True,
    )
    p3_glm = model_plan_matrix(
        ["2K", "3K", "5K", "∞"],
        "TB:P-40", "TB:P-15", calibration=True,
    )

    roadmap_overview = """
<div class="tablewrap roadmap-overview"><table>
<thead><tr><th>priority</th><th>experiment</th><th>dataset</th><th>planned runs</th></tr></thead>
<tbody>
<tr><td class="priority">P1</td><td><a href="#priority-1">Increase runs/task: 2 → 3</a></td><td>SB:P-100 + SB:ABL-30</td><td>4,400 additional</td></tr>
<tr><td class="priority">P2</td><td><a href="#priority-2">Add Devstral and GLM</a></td><td>SB:P-100 + SB:ABL-30</td><td>17,160</td></tr>
<tr><td class="priority">P3</td><td><a href="#priority-3">Terminal-Bench evaluation</a></td><td>TB:P-40 + TB:P-15</td><td>11,700</td></tr>
<tr><td class="priority">P4</td><td><a href="#priority-4">Summarizer ablation</a></td><td>SB:ABL-30 + TB:ABL-20</td><td>760</td></tr>
</tbody></table></div>"""

    p4_table = """
<div class="tablewrap"><table>
<thead><tr><th>summarizer</th><th>primitive</th><th>SB:ABL-30</th><th>TB:ABL-20</th><th>total</th></tr></thead>
<tbody>
<tr><td rowspan="2" class="prim">Qwen3.5-9B</td><td class="prim">SU-full <span class="plan-chip ablation">0.5</span></td><td>90</td><td>100</td><td>190</td></tr>
<tr><td class="prim">TRC+SU <span class="plan-chip ablation">DI</span></td><td>90</td><td>100</td><td>190</td></tr>
<tr><td rowspan="2" class="prim">Gemma-4-12B</td><td class="prim">SU-full <span class="plan-chip ablation">0.5</span></td><td>90</td><td>100</td><td>190</td></tr>
<tr><td class="prim">TRC+SU <span class="plan-chip ablation">DI</span></td><td>90</td><td>100</td><td>190</td></tr>
<tr class="total"><td colspan="2">Total</td><td>360</td><td>400</td><td>760</td></tr>
</tbody></table></div>"""

    # ---- progress tables at model × family × depth × budget granularity ----
    tunable_label = "Depth-tunable (5 primitives)"
    invariant_label = "Depth-invariant (6 primitives)"
    baseline_label = "FC, OTRC (2 baselines)"

    def swe_track(
        model, label, primitives, depth_label, budget_label, dataset, tasks, rpt,
        baseline_runs=0,
    ):
        query_depth = "0.5" if depth_label == "DI" else depth_label
        query_budget = "inf" if budget_label == "∞" else budget_label.lower()
        done, actual, target = coverage_progress(
            cells, model, primitives, query_budget, query_depth, tasks, rpt,
            baseline_runs=baseline_runs,
        )
        tracked_runs = rpt - baseline_runs
        target_text = f"{tasks} tasks × {tracked_runs} runs × {len(primitives)}"
        return [model, label, depth_label, budget_label, dataset, target_text,
                status_badge(done, actual, target)]

    def tb_track(
        model, label, primitives, depth, budget, dataset, tasks, rpt,
        display_budget=None,
    ):
        done, actual, target = coverage_progress(
            tb_cells, model, primitives, budget, depth, tasks, rpt
        )
        target_text = f"{tasks} tasks × {rpt} runs × {len(primitives)}"
        shown_budget = display_budget or (budget.upper() if budget != "inf" else "∞")
        return [model, label, depth, shown_budget, dataset,
                target_text, status_badge(done, actual, target)]

    p1_tracking_rows = []
    for budget in ("10K", "15K", "20K"):
        p1_tracking_rows.append(swe_track(MAIN, tunable_label, tunable, "0.5", budget,
                                                "SB:P-100", 100, 3, baseline_runs=2))
    for depth in ("0.3", "0.7"):
        for budget in ("10K", "15K", "20K"):
            p1_tracking_rows.append(swe_track(MAIN, tunable_label, tunable, depth, budget,
                                                    "SB:ABL-30", 30, 3, baseline_runs=2))
    for budget in ("10K", "15K", "20K"):
        p1_tracking_rows.append(swe_track(MAIN, invariant_label, invariant, "DI", budget,
                                                "SB:P-100", 100, 3, baseline_runs=2))
    p1_tracking_rows.append(swe_track(MAIN, baseline_label, ["FC", "OTRC"], "DI", "∞",
                                            "SB:P-100", 100, 3, baseline_runs=2))
    p1_tracking = tracking_table(p1_tracking_rows)

    p2a_rows = [
        swe_track("Devstral-Small-2-24B", tunable_label, tunable, "0.5", "21K", "SB:P-100", 100, 3),
        swe_track("Devstral-Small-2-24B", invariant_label, invariant, "DI", "21K", "SB:P-100", 100, 3),
        swe_track("Devstral-Small-2-24B", baseline_label, ["FC", "OTRC"], "DI", "∞", "SB:P-100", 100, 3),
    ]
    p2a_tracking = tracking_table(p2a_rows)
    p2b_rows = [
        swe_track("GLM-4.7-Flash", tunable_label, tunable, "0.5", "13K", "SB:P-100", 100, 3),
        swe_track("GLM-4.7-Flash", invariant_label, invariant, "DI", "13K", "SB:P-100", 100, 3),
        swe_track("GLM-4.7-Flash", baseline_label, ["FC", "OTRC"], "DI", "∞", "SB:P-100", 100, 3),
    ]
    p2b_tracking = tracking_table(p2b_rows)

    def ablation_tracking_rows(model, budgets):
        rows_ = []
        for depth in ("0.3", "0.7"):
            for budget in budgets:
                rows_.append(swe_track(model, tunable_label, tunable, depth, budget,
                                             "SB:ABL-30", 30, 3))
        for budget in (budgets[0], budgets[-1]):
            rows_.append(swe_track(model, tunable_label, tunable, "0.5", budget,
                                         "SB:ABL-30", 30, 3))
            rows_.append(swe_track(model, invariant_label, invariant, "DI", budget,
                                         "SB:ABL-30", 30, 3))
        return rows_

    p2c_rows = ablation_tracking_rows("Devstral-Small-2-24B", ["17K", "21K", "24K"])
    p2d_rows = ablation_tracking_rows("GLM-4.7-Flash", ["10K", "13K", "15K"])
    p2c_tracking = tracking_table(p2c_rows)
    p2d_tracking = tracking_table(p2d_rows)

    p3a_rows = []
    for model, primary_budget in (
        (MAIN, "3k"),
        ("Devstral-Small-2-24B", "4k"),
        ("GLM-4.7-Flash", "3k"),
    ):
        p3a_rows.append(tb_track(model, tunable_label, tunable, "0.5", primary_budget, "TB:P-40", 40, 3))
        p3a_rows.append(tb_track(model, invariant_label, invariant, "DI", primary_budget, "TB:P-40", 40, 3))
        p3a_rows.append(tb_track(model, baseline_label, ["FC", "OTRC"], "DI", "inf", "TB:P-40", 40, 3))
    p3a_tracking = tracking_table(p3a_rows)

    p3b_rows = []
    for model, budgets in (
        (MAIN, [("2k", "2K"), ("3k", "3K"), ("4k", "4K")]),
        ("Devstral-Small-2-24B", [("3k", "3K"), ("4k", "4K"), ("7k", "7K")]),
        ("GLM-4.7-Flash", [("2k", "2K"), ("3k", "3K"), ("5k", "5K")]),
    ):
        for depth in ("0.3", "0.7"):
            for budget, display_budget in budgets:
                p3b_rows.append(tb_track(model, tunable_label, tunable, depth, budget,
                                               "TB:P-15", 15, 3, display_budget))
        for budget, display_budget in (budgets[0], budgets[-1]):
            p3b_rows.append(tb_track(model, tunable_label, tunable, "0.5", budget,
                                           "TB:P-15", 15, 3, display_budget))
            p3b_rows.append(tb_track(model, invariant_label, invariant, "DI", budget,
                                           "TB:P-15", 15, 3, display_budget))
    p3b_tracking = tracking_table(p3b_rows)

    p4_tracking_rows = []
    p4_specs = [
        ("4.a", "Qwen3.5-9B", "SB:ABL-30", 30, 3),
        ("4.b", "Qwen3.5-9B", "TB:ABL-20", 20, 5),
        ("4.c", "Gemma-4-12B", "SB:ABL-30", 30, 3),
        ("4.d", "Gemma-4-12B", "TB:ABL-20", 20, 5),
    ]
    p4_display_rows = []
    for exp_id, summarizer, dataset, tasks, rpt in p4_specs:
        budget = "3K" if dataset == "TB:ABL-20" else "15K"
        target = tasks * rpt * 2
        # No summarizer-specific run source exists yet. Missing data is zero;
        # once those results are recorded, replace this with automatic discovery.
        actual = 0
        status = status_badge(actual >= target, min(actual, target), target)
        p4_tracking_rows.append([
            MAIN, "SU-full (0.5), TRC+SU (DI)", "mixed", budget, dataset,
            f"{tasks} tasks × {rpt} runs × 2",
            status,
        ])
        p4_display_rows.append([
            f"({exp_id})", dataset, MAIN, summarizer,
            "SU-full (0.5), TRC+SU (DI)", budget, status,
        ])
    p4_tracking = summarizer_tracking_table(p4_display_rows)

    history = load_progress_history()
    now_utc = datetime.now(timezone.utc)
    snapshot = {}
    p1_progress = progress_bar(p1_tracking_rows, "p1", history, now_utc, snapshot)
    p2a_progress = progress_bar(p2a_rows, "p2a", history, now_utc, snapshot)
    p2b_progress = progress_bar(p2b_rows, "p2b", history, now_utc, snapshot)
    p2c_progress = progress_bar(p2c_rows, "p2c", history, now_utc, snapshot)
    p2d_progress = progress_bar(p2d_rows, "p2d", history, now_utc, snapshot)
    p2_progress = progress_bar(p2a_rows + p2b_rows + p2c_rows + p2d_rows, "p2", history, now_utc, snapshot)
    p3a_progress = progress_bar(p3a_rows, "p3a", history, now_utc, snapshot)
    p3b_progress = progress_bar(p3b_rows, "p3b", history, now_utc, snapshot)
    p3_progress = progress_bar(p3a_rows + p3b_rows, "p3", history, now_utc, snapshot)
    p4_progress = progress_bar(p4_tracking_rows, "p4", history, now_utc, snapshot)
    if args.record_history:
        write_progress_history(history, snapshot, now_utc)

    html = f"""<title>agentCtx Follow-up Experiments</title>
<meta name="robots" content="noindex, nofollow, noarchive">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Schibsted+Grotesk:wght@500;700&family=Source+Sans+3:ital,wght@0,400;0,600;1,400&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
:root {{
  --bg:#F7F8F6; --surface:#FFFFFF; --ink:#202824; --muted:#5C6B63;
  --line:#DDE3DF; --accent:#0E7C6B; --accent-ink:#0A5A4E;
  --have:#0E7C6B; --have-bg:#E2F0EC;
  --pending:#A8721D; --pending-bg:#F6EBD7;
  --missing:#B54233; --missing-bg:#F7E4E0;
  --extra:#97A39D; --extra-bg:#EEF1EF;
  --csvonly:#4E7FA0; --csvonly-bg:#E4EDF3;
  --on-solid:#FFFFFF;
}}
@media (prefers-color-scheme: dark) {{
  :root:not([data-theme="light"]) {{
    --bg:#121815; --surface:#1A211D; --ink:#E4EAE6; --muted:#93A29A;
    --line:#2C3630; --accent:#45BFA5; --accent-ink:#6FD2BC;
    --have:#45BFA5; --have-bg:#1D302A;
    --pending:#D19A3F; --pending-bg:#332916;
    --missing:#D86A57; --missing-bg:#38201B;
    --extra:#6C7A73; --extra-bg:#232B26;
    --csvonly:#7FAECB; --csvonly-bg:#1D2A33;
    --on-solid:#0F1512;
  }}
}}
:root[data-theme="dark"] {{
  --bg:#121815; --surface:#1A211D; --ink:#E4EAE6; --muted:#93A29A;
  --line:#2C3630; --accent:#45BFA5; --accent-ink:#6FD2BC;
  --have:#45BFA5; --have-bg:#1D302A;
  --pending:#D19A3F; --pending-bg:#332916;
  --missing:#D86A57; --missing-bg:#38201B;
  --extra:#6C7A73; --extra-bg:#232B26;
  --csvonly:#7FAECB; --csvonly-bg:#1D2A33;
  --on-solid:#0F1512;
}}
* {{ box-sizing:border-box; }}
body {{ background:var(--bg); color:var(--ink); margin:0;
  font:16px/1.55 "Source Sans 3",system-ui,sans-serif; }}
.wrap {{ max-width:1080px; margin:0 auto; padding:40px 24px 72px; }}
h1,h2,h3 {{ font-family:"Schibsted Grotesk","Source Sans 3",sans-serif; text-wrap:balance; }}
h1 {{ font-size:1.9rem; font-weight:700; margin:0 0 4px; }}
h2 {{ font-size:1.25rem; font-weight:700; margin:44px 0 12px; }}
h3 {{ font-size:1.02rem; font-weight:700; margin:0 0 6px; }}
.sub {{ color:var(--muted); margin:0; }}
.sub code, .note code, li code {{ font-family:"IBM Plex Mono",monospace; font-size:.85em;
  background:var(--extra-bg); padding:1px 5px; border-radius:4px; }}
.stats {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr));
  gap:10px; margin:26px 0 8px; }}
.stat {{ background:var(--surface); border:1px solid var(--line); border-radius:8px;
  padding:12px 14px; }}
.stat .n {{ font-family:"IBM Plex Mono",monospace; font-size:1.35rem; font-weight:500;
  color:var(--accent-ink); font-variant-numeric:tabular-nums; }}
.stat .l {{ color:var(--muted); font-size:.82rem; margin-top:2px; }}
.legend {{ display:flex; flex-wrap:wrap; gap:14px; color:var(--muted);
  font-size:.85rem; margin:10px 0 16px; align-items:center; }}
.legend .chip {{ cursor:default; }}
.tablewrap {{ overflow-x:auto; background:var(--surface); border:1px solid var(--line);
  border-radius:8px; }}
table {{ border-collapse:collapse; width:100%; font-size:.9rem; }}
th {{ text-align:left; font-family:"IBM Plex Mono",monospace; font-weight:500;
  font-size:.78rem; letter-spacing:.04em; text-transform:uppercase;
  color:var(--muted); padding:10px 12px; border-bottom:1px solid var(--line); }}
td {{ padding:7px 12px; border-bottom:1px solid var(--line); white-space:nowrap; }}
tr:last-child td {{ border-bottom:none; }}
tr.fam td {{ font-family:"Schibsted Grotesk",sans-serif; font-weight:700; font-size:.8rem;
  letter-spacing:.05em; text-transform:uppercase; color:var(--muted);
  background:var(--bg); padding-top:9px; padding-bottom:9px; }}
td.prim {{ font-family:"IBM Plex Mono",monospace; font-size:.84rem; }}
.chip {{ display:inline-block; font-family:"IBM Plex Mono",monospace; font-size:.74rem;
  padding:1px 7px; border-radius:20px; margin-right:4px; border:1px solid transparent; }}
.chip.have    {{ background:var(--have-bg);    color:var(--have);    border-color:var(--have); }}
.chip.partial {{ background:var(--pending-bg); color:var(--pending); border-color:var(--pending); }}
.chip.pending {{ background:var(--pending-bg); color:var(--pending); border-color:var(--pending); }}
.chip.missing {{ background:var(--missing-bg); color:var(--missing); border-color:var(--missing); }}
.chip.extra   {{ background:var(--extra-bg);   color:var(--extra);   border-color:var(--line); }}
.chip.csvonly {{ background:var(--csvonly-bg); color:var(--csvonly); border-color:var(--csvonly); border-style:dashed; }}
.chip.have.p100    {{ background:var(--have);    color:var(--on-solid); }}
.chip.pending.p100 {{ background:var(--pending); color:var(--on-solid); }}
.chip.extra.p100   {{ background:var(--extra);   color:var(--on-solid); border-color:var(--extra); }}
.chip.csvonly.p100 {{ background:var(--csvonly); color:var(--on-solid); border-style:solid; }}
.chip.none {{ color:var(--line); }}
.chipdash {{ color:var(--line); }}
.cards {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(340px,1fr)); gap:14px; }}
.card {{ background:var(--surface); border:1px solid var(--line); border-radius:8px;
  padding:16px 18px; }}
.card .tablewrap {{ border:none; border-top:1px solid var(--line); border-radius:0; margin-top:8px; }}
.note {{ color:var(--muted); font-size:.88rem; margin:0 0 4px; }}
ul.attn {{ list-style:none; padding:0; margin:0; display:flex; flex-direction:column; gap:8px; }}
ul.attn li {{ background:var(--surface); border:1px solid var(--line); border-radius:8px;
  padding:10px 14px; }}
.dot {{ display:inline-block; width:9px; height:9px; border-radius:50%; margin-right:8px; }}
.dot.missing {{ background:var(--missing); }}
.dot.pending {{ background:var(--pending); }}
.bench {{ margin-top:52px; padding-top:20px; border-top:2px solid var(--line); }}
.eyebrow {{ font-family:"IBM Plex Mono",monospace; font-size:.72rem; font-weight:500;
  letter-spacing:.14em; text-transform:uppercase; color:var(--accent-ink); }}
.bench-title {{ margin:2px 0 6px; font-size:1.5rem; }}
.subhead {{ font-size:1.1rem; margin:28px 0 8px; }}
.tablewrap.tb {{ max-width:440px; }}
.where td:first-child {{ font-family:"IBM Plex Mono",monospace; font-size:.82rem; }}
.roadmap {{ margin:18px 0 36px; padding:18px; background:var(--surface);
  border:1px solid var(--line); border-radius:10px; }}
.roadmap > h2 {{ margin-top:36px; padding-top:18px; border-top:1px solid var(--line); }}
.roadmap > h2:first-child {{ margin-top:0; padding-top:0; border-top:none; }}
.roadmap > h3 {{ font-size:1.18rem; margin:28px 0 8px; }}
.roadmap h4 {{ font-family:"Schibsted Grotesk",sans-serif; font-size:1rem;
  margin:26px 0 5px; }}
.roadmap td {{ white-space:normal; vertical-align:top; }}
.roadmap ul {{ margin:12px 0 18px; }}
.tracking {{ margin-top:10px; }}
.tracking th:nth-child(5), .tracking td:nth-child(5) {{ min-width:240px; }}
.summarizer-tracking th:nth-child(5), .summarizer-tracking td:nth-child(5) {{ min-width:210px; }}
.summarizer-tracking th:nth-child(6), .summarizer-tracking td:nth-child(6) {{ min-width:150px; }}
.tracking td.repeat {{ background:color-mix(in srgb, var(--bg) 45%, transparent); }}
.track-status {{ display:inline-block; font-family:"IBM Plex Mono",monospace;
  font-size:.74rem; font-weight:500; padding:3px 9px; border-radius:20px;
  border:1px solid; white-space:nowrap; }}
.track-status.done {{ color:var(--on-solid); background:var(--have); border-color:var(--have); }}
.track-status.pending {{ color:var(--pending); background:var(--pending-bg); border-color:var(--pending); }}
.status-chips {{ display:flex; flex-wrap:wrap; gap:6px; }}
.section-progress {{ margin:8px 0 16px; }}
.progress-meta {{ display:flex; justify-content:space-between; gap:16px; align-items:baseline;
  color:var(--muted); font-size:.82rem; }}
.progress-meta strong {{ color:var(--ink); font-family:"IBM Plex Mono",monospace;
  font-size:.8rem; font-weight:500; }}
.progress-numbers {{ display:flex; flex-wrap:wrap; justify-content:flex-end;
  gap:3px 14px; align-items:baseline; }}
.progress-rate {{ color:var(--accent-ink); font-family:"IBM Plex Mono",monospace;
  font-size:.76rem; white-space:nowrap; }}
.progress-since {{ color:var(--muted); font-family:"IBM Plex Mono",monospace;
  font-size:.76rem; white-space:nowrap; }}
.progress-track {{ height:9px; margin-top:5px; overflow:hidden; border-radius:999px;
  background:var(--pending-bg); border:1px solid var(--line); }}
.progress-track > span {{ display:block; height:100%; border-radius:inherit; background:var(--have); }}
.roadmap-overview {{ margin-top:14px; }}
.roadmap-overview td {{ white-space:normal; }}
.priority {{ font-family:"IBM Plex Mono",monospace; color:var(--accent-ink); font-weight:500; }}
.plan-legend {{ display:flex; flex-wrap:wrap; align-items:center; gap:12px;
  color:var(--muted); font-size:.84rem; margin:12px 0; }}
.plan-chip {{ display:inline-block; font-family:"IBM Plex Mono",monospace; font-size:.74rem;
  padding:1px 7px; border-radius:20px; margin-right:4px; border:1px solid; }}
.plan-chip.main {{ background:var(--csvonly); color:var(--on-solid); border-color:var(--csvonly); }}
.plan-chip.ablation {{ background:transparent; color:var(--csvonly); border-color:var(--csvonly); }}
.plan-chip.calibration-main {{ background:var(--pending); color:var(--on-solid); border-color:var(--pending); }}
.plan-chip.calibration {{ background:transparent; color:var(--pending); border-color:var(--pending); }}
.plan-table {{ margin-top:10px; }}
.plan-card {{ margin-top:12px; }}
.plan-card + .plan-card {{ margin-top:16px; }}
.plan-card h4 {{ margin-top:0; }}
tr.total td {{ font-weight:700; background:var(--bg); }}
.current-label {{ margin-top:36px; padding-top:24px; border-top:1px solid var(--line); }}
footer {{ color:var(--muted); font-size:.85rem; margin-top:40px;
  border-top:1px solid var(--line); padding-top:14px; }}
a {{ color:var(--accent-ink); }}
</style>

<div class="wrap">
<h1>Follow-up Experiments Plan</h1>
<p class="sub">Generated {generated_at} from
<code>exp_plans/FOLLOWUP_EXPERIMENTS.md</code>.</p>

<div class="roadmap">
<h2>Overview</h2>
<div class="tablewrap roadmap-overview"><table>
<thead><tr><th>priority</th><th>experiment</th><th>dataset(s)</th><th>runs</th></tr></thead>
<tbody>
<tr><td class="priority">1</td><td><a href="#exp-runs">Increase runs/task</a></td><td>SB:P-100 + SB:ABL-30</td><td>4,400</td></tr>
<tr><td class="priority">2</td><td><a href="#exp-models">Add 2 agent models</a></td><td>SB:P-100 + SB:ABL-30</td><td>17,160</td></tr>
<tr><td class="priority">3</td><td><a href="#exp-tb">Terminal-Bench evaluation</a></td><td>TB:P-40 + TB:P-15</td><td>11,700</td></tr>
<tr><td class="priority">4</td><td><a href="#exp-summarizer">Summarizer ablation</a></td><td>SB:ABL-30 + TB:ABL-20</td><td>760</td></tr>
</tbody></table></div>
<ul>
<li>SWE-Bench env: <strong>Dobby (GPU: 4× A100 80GB)</strong></li>
<li>Terminal-Bench env: <strong>Albus (GPU: gpu0-3)</strong></li>
<li>Metrics: resolve rate (SWE-Bench), accuracy (Terminal-Bench), token cost, latency, compression behavior</li>
</ul>
<div class="plan-legend">
  <span class="track-status done">15K</span> completed
  <span class="track-status pending">10K, 0/500 runs</span> planned work remains
  <span>· Status is aggregated by model × primitive family × depth × budget × dataset.</span>
</div>

<h2 id="exp-runs">1. [Priority] SWE-Bench: Runs/task: 2 → 3</h2>
{p1_progress}
<ul>
<li>ETA: 3–5 days</li>
<li>Model (agent &amp; summarizer): Qwen3.5-35B-A3B-Instruct</li>
<li>Runs/task: <strong>3 (mostly 1 additional run/task)</strong></li>
</ul>
<p class="note">Progress and budget chips count only the additional third run (the existing
2 runs/task are excluded). Status is tracked per depth and budget. The unused full-depth P100
alternative is excluded.</p>
{p1_tracking}

<h2 id="exp-models">2. [Priority] SWE-Bench: Add 2 agent models</h2>
{p2_progress}
<ul>
<li><strong>Calibrated budgets (FC@∞ run_1 P5/P15/P25):</strong> Devstral 17K/21K/24K; GLM 10K/13K/15K.</li>
<li>Runs/task: 3</li>
</ul>
<div class="tablewrap"><table>
<thead><tr><th>experiment</th><th>model (agent &amp; summarizer)</th><th>dataset</th><th>notes</th><th>runs</th></tr></thead>
<tbody>
<tr><td><a href="#exp-models-devstral-main">(2.a) Devstral-24B Main</a></td><td>Devstral-Small-2-24B</td><td>SB:P-100</td><td>Depth: 0.5 or DI / Budget: 21K (or ∞)</td><td>3,900</td></tr>
<tr><td><a href="#exp-models-glm-main">(2.b) GLM Main</a></td><td>GLM-4.7-Flash (30B-A3B MoE)</td><td>SB:P-100</td><td>Depth: 0.5 or DI / Budget: 13K (or ∞)</td><td>3,900</td></tr>
<tr><td><a href="#exp-models-devstral-abl">(2.c) Devstral-24B Ablation</a></td><td>Devstral-Small-2-24B</td><td>SB:ABL-30</td><td>Depth &amp; budget ablation</td><td>4,680</td></tr>
<tr><td><a href="#exp-models-glm-abl">(2.d) GLM Ablation</a></td><td>GLM-4.7-Flash (30B-A3B MoE)</td><td>SB:ABL-30</td><td>Depth &amp; budget ablation</td><td>4,680</td></tr>
</tbody></table></div>

<h3 id="exp-models-devstral-main">(2.a) Devstral-24B Main</h3>
{p2a_progress}
{p2a_tracking}

<h3 id="exp-models-glm-main">(2.b) GLM Main</h3>
{p2b_progress}
{p2b_tracking}

<h3 id="exp-models-devstral-abl">(2.c) Devstral-24B Ablation</h3>
{p2c_progress}
{p2c_tracking}

<h3 id="exp-models-glm-abl">(2.d) GLM Ablation</h3>
{p2d_progress}
{p2d_tracking}

<h2 id="exp-tb">3. [Priority] Terminal-Bench Evaluation</h2>
{p3_progress}
<ul>
<li>Terminal-Bench 1.0 (80 tasks)</li>
<li>Runs/task: 3</li>
<li>Models (agent &amp; summarizer): Qwen3.5-35B-A3B-Instruct, Devstral-Small-2-24B, GLM-4.7-Flash (30B-A3B MoE)</li>
<li><strong>Model budgets (A/P/B):</strong> Qwen 2K/3K/4K; Devstral 3K/4K/7K; GLM 2K/3K/5K.</li>
</ul>
<div class="tablewrap"><table><thead><tr><th>experiment</th><th>dataset</th><th>notes</th><th>runs</th></tr></thead><tbody>
<tr><td><a href="#exp-tb-main">(3.a) TB Main</a></td><td>TB:P-40</td><td>Depth: 0.5 or DI / Budget: model-calibrated primary (or ∞)</td><td>4,680</td></tr>
<tr><td><a href="#exp-tb-abl">(3.b) TB Ablation</a></td><td>TB:P-15</td><td>Depth &amp; budget ablation</td><td>7,020</td></tr>
</tbody></table></div>

<h3 id="exp-tb-main">(3.a) TB Main</h3>
{p3a_progress}
{p3a_tracking}

<h3 id="exp-tb-abl">(3.b) TB Ablation</h3>
{p3b_progress}
{p3b_tracking}

<h2 id="exp-summarizer">4. [Priority] Summarizer Ablation</h2>
{p4_progress}
<ul>
<li>ETA: TBD (760 runs)</li>
</ul>
<p>Existing self-summarization runs are used as the baseline.</p>
{p4_tracking}
</div>
</div>
"""
    OUT.write_text(html)
    print(f"Wrote {OUT.relative_to(ROOT)} ({len(html):,} chars)")


if __name__ == "__main__":
    main()
