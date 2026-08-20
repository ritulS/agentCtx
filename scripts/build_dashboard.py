#!/usr/bin/env python3
"""Render DASHBOARD.html — the human-friendly coverage dashboard.

Reads COVERAGE.csv (regenerate that first with scripts/build_coverage.py)
plus data/tbench/experiment_results.json, and writes a self-contained HTML
page at the repo root. Re-run after every completed run:

    python scripts/build_coverage.py && python scripts/build_dashboard.py
"""

import csv
import json
from collections import defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "DASHBOARD.html"

MAIN = "Qwen3.5-35B-A3B"

FAMILIES = [
    ("Depth-tunable", ["TR", "SU-full", "SU-partial", "SS", "SS-partial"]),
    ("Depth-invariant", ["TRC", "TRC+SU", "TRC+SS", "OTRC+TR", "OTRC+SU-partial", "OTRC+SS-partial"]),
    ("∞-budget baselines", ["FC", "OTRC"]),
]
DEPTHS = ["0.3", "0.5", "0.7"]

BUDGET_ORDER = {"4k": 4, "8k": 8, "10k": 10, "12k": 12, "15k": 15, "20k": 20, "24k": 24, "inf": 999}


def load_cells():
    cells = {}
    for r in csv.DictReader(open(ROOT / "COVERAGE.csv")):
        cells[(r["model"], r["primitive"], r["budget"], r["depth"])] = r
    return cells


def chip(cell, depth):
    """One depth chip. State drives color: filled=have, amber=not ingested,
    red=missing, grey=out-of-scope extra, dashed=csv-only (raw on Albus)."""
    if cell is None:
        return f'<span class="chip none">{depth}</span>'
    status, notes = cell["status"], cell["notes"]
    title = (f'{cell["model"]} · {cell["primitive"]} · {cell["budget"]} · d={cell["depth"]} — '
             f'{cell["status"]}; {cell["tasks_on_disk"]} tasks / {cell["runs_on_disk"]} runs on disk; '
             f'{cell["rows_in_csv"]} CSV rows; min {cell.get("runs_per_task_min", "?")} runs/task; '
             f'cohort {cell["cohort_covered"] or "—"}'
             + (f'; {notes}' if notes else ''))
    if status == "MISSING":
        cls = "missing"
    elif "NOT in Review1.csv" in notes:
        cls = "pending"
    elif status == "HAVE (csv-only)":
        cls = "csvonly"
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


def main():
    cells = load_cells()
    rows = list(cells.values())
    today = date.today().isoformat()

    # ---- headline stats -----------------------------------------------------
    disk_runs = sum(int(r["runs_on_disk"]) for r in rows)
    albus_rows = sum(int(r["rows_in_csv"]) for r in rows if r["runs_on_disk"] == "0")
    n_missing = sum(r["status"] == "MISSING" for r in rows)
    n_pending = sum("NOT in Review1.csv" in r["notes"] for r in rows)

    tb_recs = json.load(open(ROOT / "data/tbench/experiment_results.json"))
    if isinstance(tb_recs, dict):
        tb_recs = tb_recs.get("results", [])
    tb_tasks = len({r.get("instance_id") for r in tb_recs})
    tb_conds = sorted({r.get("condition") for r in tb_recs})

    covered = [r for r in rows if r["cohort_covered"]]
    n_p100 = sum(r["cohort_covered"].startswith("P100") for r in covered)
    n_abl = len(covered) - n_p100

    stats = [
        ("2", "benchmarks"),
        ("6", "models"),
        ("100", "SWE-bench tasks (P100)"),
        ("11 + 2", "primitives + baselines"),
        (f"{n_p100} / {n_abl}", "cells at full P100 / ABL-30 only"),
        (f"{disk_runs:,}", "trajectories on this disk"),
        (f"{albus_rows:,}", "runs in CSVs (raw on Albus)"),
        (f"{tb_tasks} × {len(tb_conds)}", "Terminal-Bench tasks × conds"),
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
    if n_pending:
        attention.append(f'<li><span class="dot pending"></span><strong>{n_pending} cells on disk '
                         'but not in Review1.csv</strong> — the 20k tail-depth runs '
                         '(d=0.3 / 0.7, all five depth-tunable primitives, plus TRC variants). '
                         'One <code>build_review1.py</code> pass away.</li>')

    # ---- expansion model cards ----------------------------------------------
    exp_cards = []
    for model, note in [
        ("Devstral-Small-2-24B", "Albus. Own calibrated budgets. Shows the −33.4pp clearing reversal at ∞."),
        ("Qwen2.5-Coder-32B", "Albus. FC = OTRC = 10.0% at ∞ — floor-limited, uninformative."),
        ("Llama-3.3-70B", "Albus. FC@∞ done; OTRC@∞ is the one missing arm."),
        ("Qwen2.5-7B", "Albus only — cells live in Review1_qwen25-7b.csv; raw trajectories not on this disk."),
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

    # Terminal-Bench per-condition table (own benchmark section)
    tb_by_cond = defaultdict(lambda: {"tasks": set(), "runs": 0})
    for r in tb_recs:
        tb_by_cond[r["condition"]]["tasks"].add(r.get("instance_id"))
        tb_by_cond[r["condition"]]["runs"] += 1
    tb_rows = "".join(
        f'<tr><td class="prim">{c}</td>'
        f'<td>{len(v["tasks"])}</td><td>{v["runs"]}</td></tr>'
        for c, v in sorted(tb_by_cond.items()))
    tb_section = (
        f'<p class="note">Transfer check for the main model (Qwen3.5-35B-A3B), '
        f'terminal-bench-core 0.1.1. {tb_tasks} stratified tasks, 15k budget, d=0.5, '
        f'{len(tb_recs)} records. Raw data in <code>data/tbench/</code>; run log in '
        f'<code>data/tbench/STATUS.md</code>.</p>'
        f'<div class="tablewrap tb"><table><thead><tr><th>condition</th>'
        f'<th>tasks</th><th>runs</th></tr></thead><tbody>{tb_rows}</tbody></table></div>')

    main_matrix = matrix(cells, MAIN, ["10k", "15k", "20k", "inf"], FAMILIES)

    html = f"""<title>agentCtx Coverage</title>
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
footer {{ color:var(--muted); font-size:.85rem; margin-top:40px;
  border-top:1px solid var(--line); padding-top:14px; }}
a {{ color:var(--accent-ink); }}
</style>

<div class="wrap">
<h1>agentCtx Coverage</h1>
<p class="sub">Context-compression grid on SWE-bench Verified — what has already been run,
per model × primitive × budget × depth. Generated {today} from
<code>COVERAGE.csv</code> by <code>scripts/build_dashboard.py</code>.</p>

<div class="stats">{stat_html}</div>

<div class="legend">
  <span class="chip have p100">0.5</span> full 100-task set (P100)
  <span class="chip have abl">0.5</span> ablation set only (ABL-30)
  <span class="chip pending abl">0.5</span> on disk, not yet in Review1.csv
  <span class="chip csvonly abl">0.5</span> in CSV, raw trajectories on Albus
  <span class="chip extra abl">0.5</span> out-of-scope extra
  <span class="chip missing">0.5</span> missing
  <span>· chip label = depth · hover any chip for tasks / runs / cohort</span>
</div>

<section class="bench">
<div class="eyebrow">Benchmark</div>
<h2 class="bench-title">SWE-bench Verified</h2>

<h3 class="subhead">Main model — Qwen3.5-35B-A3B (Dobby)</h3>
<p class="note">Scope: depth-tunable primitives at all 3 depths (P100 cohort at 15k, ABL-30 at
10k/20k); depth-invariant primitives at d=0.5 on P100 at every budget; FC and OTRC baselines at
unlimited budget. A cell only turns solid/complete once every task has 3 runs (Expansion 1,
<code>exp_plans/SWE_EXPANSION.md</code>) — cells with the right cohort but fewer runs show as
partial. Solid chips carry the full 100-task set; outlined chips are ABL-30 only. Not drawn:
out-of-scope extras at depths 0.4/0.6 and the dropped staggered pilot — they live in
<code>COVERAGE.csv</code>.</p>
{main_matrix}

<h3 class="subhead">Model expansion (Albus)</h3>
<div class="cards">
{"".join(exp_cards)}
{quant_card}
</div>
</section>

<section class="bench">
<div class="eyebrow">Benchmark</div>
<h2 class="bench-title">Terminal-Bench 1.0</h2>
{tb_section}
</section>

<h2>Needs attention</h2>
<ul class="attn">
{"".join(attention) or "<li>Nothing — all in-scope cells covered and ingested.</li>"}
</ul>

<h2>Where the data lives</h2>
<div class="tablewrap"><table class="where">
<thead><tr><th>path</th><th>what</th></tr></thead>
<tbody>
<tr><td>data/swebench/ablations/</td><td>canonical grid — trajectory.json per (task, condition, run)</td></tr>
<tr><td>data/swebench/source_runs/</td><td>backing store for deduplicated runs (symlinked from ablations)</td></tr>
<tr><td>Review1/Review1.csv</td><td>canonical distilled table, main model (git-tracked)</td></tr>
<tr><td>Review1/Review1_qwen25-7b.csv · _quant.csv</td><td>Albus per-model aggregations</td></tr>
<tr><td>data/tbench/</td><td>Terminal-Bench runs + STATUS.md</td></tr>
<tr><td>COVERAGE.csv</td><td>machine-readable cell sheet behind this page</td></tr>
</tbody></table></div>

<footer>To update after new runs: <code>python scripts/build_coverage.py &amp;&amp;
python scripts/build_dashboard.py</code>, then republish. Each benchmark is its own
section — a new benchmark gets a new section in <code>scripts/build_dashboard.py</code>. Docs:
<code>project_runs_checklist.md</code> (narrative), <code>DATA.md</code> (transfer),
<code>Active_runs.md</code> (live runs).</footer>
</div>
"""
    OUT.write_text(html)
    print(f"Wrote {OUT.relative_to(ROOT)} ({len(html):,} chars)")


if __name__ == "__main__":
    main()
