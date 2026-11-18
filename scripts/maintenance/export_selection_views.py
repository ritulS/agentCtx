#!/usr/bin/env python3
"""Export the per-step selections of an online-claude-select cell (ocs / ocsa /
ocsi) in human-readable form: one folder per run with

  view.html        self-contained page: a grid of history messages (rows) x
                   selection steps (columns) coloured kept / partial / dropped /
                   verbatim tail; click a column header for that step's agent
                   command, selector reasoning and directives; click a row for
                   the message text.
  matrix.csv       the same grid as text (W kept whole, P partial, D dropped,
                   T newest turn kept verbatim, . protected, blank = not yet
                   in the history).
  messages.csv     one row per history message: uid, step, role, command
                   category, returncode, tokens, lines, lifecycle summary.
  selections.csv   one row per selection step: newest command, counts
                   (window / kept / carried / added / removed), attempts,
                   rejections, selector cost, removed / added uids.
  selections.jsonl the selection rows plus the selector's reasoning and the
                   accepted directives, verbatim.

and an index.html / index.csv over the runs. Reads events.jsonl,
compression_events.jsonl, summary_attempts.jsonl and token_log.json of each
run (the event log written since 2026-10-11). Output goes under
data/r2/probes/ (gitignored) by default.

  python scripts/maintenance/export_selection_views.py \
      data/r2/swebench/p30s/devstral24b-iso-fc20-dsflash/di__binf__ocsa \
      --out data/r2/probes/ocsa_dsflash_selection
"""
from __future__ import annotations

import argparse
import csv
import glob
import html
import json
import os
import re
import sys
from collections import defaultdict

import tiktoken

ENC = tiktoken.get_encoding("cl100k_base")
CMD_RE = re.compile(r"```mswea_bash_command\s*\n(.*?)```", re.S)
N_PROTECTED = 2


def command_of(content: str) -> str | None:
    m = CMD_RE.search(content or "")
    return m.group(1).strip() if m else None


def categorize(cmd: str | None) -> str:
    """Coarse command category (regexes over the command text)."""
    if cmd is None:
        return "no_command"
    c = cmd.strip()
    first = c.split("\n")[0]
    if "complete_task_and_submit" in c.lower():
        return "submit"
    m = re.search(r"cat\s*>\s*([^\s<]+)\s*<<|cat\s*<<\s*['\"]?\w+['\"]?\s*>\s*([^\s]+)|tee\s+([^\s]+)", c)
    if m:
        path = (m.group(1) or m.group(2) or m.group(3) or "").lower()
        if re.search(r"test|repro|debug|check|verify|tmp|scratch|example|demo", os.path.basename(path)):
            return "write_script"
        return "edit_source"
    if re.search(r"\bsed\s+-i|\bpatch\b|git apply|\.write\(|open\([^)]*['\"]w['\"]|str_replace|replace_in_file|applypatch", c):
        return "edit_source"
    if re.search(r"python[0-9.]*\s+-\s*<<|python[0-9.]*\s*<<", c) and re.search(r"\.write\(|open\(", c):
        return "edit_source"
    if re.search(r"\bmake\b|setup\.py\s+(build|develop|install)|\bcython\b|\bgcc\b", c):
        return "env"
    if re.search(r"\bgit\s+(diff|status|log|show|stash|checkout|restore|reset)\b", c):
        return "git"
    if re.search(r"\bpytest\b|runtests\.py|bin/test\b|-m\s+unittest|-m\s+django\s+test|\btox\b|manage\.py\s+test", c):
        return "test_suite"
    if (re.search(r"python[0-9.]*\s+(\S*\.py)", c) or re.search(r"python[0-9.]*\s+-c\s", c)
            or re.search(r"python[0-9.]*\s+-\s*<<|python[0-9.]*\s*<<", c)):
        return "run_script"
    if re.search(r"\bpip[0-9.]*\b|\bapt\b|\bconda\b|\bexport\s|\bpython[0-9.]*\s+--version|\bwhich\b|\benv\b", c):
        return "env"
    if re.search(r"\b(grep|rg|ag|find|locate)\b", c):
        return "search"
    if re.search(r"^\s*(ls|tree|pwd|wc|file|du)\b", first) or re.search(r"\bls\b", first):
        return "list"
    if re.search(r"\b(cat|sed\s+-n|head|tail|less|more|nl|awk)\b", c):
        return "read"
    if re.search(r"\b(cd|echo|mkdir|rm|cp|mv|touch|chmod|ln|source)\b", first):
        return "shell_misc"
    return "other"


def ntok(s: str) -> int:
    return len(ENC.encode(s or ""))


def one_line(s: str | None, n: int = 120) -> str:
    s = re.sub(r"\s+", " ", (s or "").strip())
    return s[:n] + ("…" if len(s) > n else "")


def load_run(run_dir: str) -> dict:
    with open(f"{run_dir}/events.jsonl") as f:
        ev = [json.loads(l) for l in f]
    with open(f"{run_dir}/compression_events.jsonl") as f:
        ce = [json.loads(l) for l in f]
    sa_path = f"{run_dir}/summary_attempts.jsonl"
    sa = [json.loads(l) for l in open(sa_path)] if os.path.exists(sa_path) else []
    tl = json.load(open(f"{run_dir}/token_log.json"))
    sel_events = tl.get("online_claude_select_events") or []

    hist, order = {}, []
    for e in ev:
        m = e["message"]
        content = m.get("content") or ""
        rec = {"uid": e["uid"], "seq": e["seq"], "step": e["step"], "role": m["role"], "content": content,
               "tokens": ntok(content), "lines": len(content.split("\n"))}
        if m["role"] == "assistant":
            rec["cmd"] = command_of(content)
            rec["cat"] = categorize(rec["cmd"])
        elif m["role"] == "user":
            ex = m.get("extra") or {}
            rec["returncode"] = ex.get("returncode")
            rec["is_format_error"] = content.startswith("Format error")
        hist[rec["uid"]] = rec
        order.append(rec["uid"])
    by_step = defaultdict(list)
    for uid in order:
        by_step[hist[uid]["step"]].append(uid)
    for uids in by_step.values():
        a = [u for u in uids if hist[u]["role"] == "assistant"]
        o = [u for u in uids if hist[u]["role"] == "user"]
        if a and o:
            hist[o[-1]]["cat"] = hist[a[0]]["cat"]
            hist[o[-1]]["cmd"] = hist[a[0]]["cmd"]
            hist[o[-1]]["pair"] = a[0]
            hist[a[0]]["pair"] = o[-1]
        elif o and not a:
            for u in o:
                hist[u]["cat"] = "format_error" if hist[u].get("is_format_error") else "no_command"

    ce_by_step = {c["step"]: c for c in ce}
    att_by_seq = defaultdict(list)
    for s in sa:
        att_by_seq[s["request_seq"]].append(s)
    events = []
    prev_after = order[:N_PROTECTED]
    for i, se in enumerate(sel_events):
        S = se["step"]
        c = ce_by_step.get(S)
        full = [u for u in order if hist[u]["step"] <= S]
        compressible = full[N_PROTECTED:]
        keep_recent = (c or {}).get("keep_recent", 3) or 3
        k = max(0, len(compressible) - keep_recent)
        while k > 0 and hist[compressible[k]]["role"] != "assistant":
            k -= 1
        window, tail = compressible[:k], compressible[k:]
        sel = se.get("selection")
        keep = sel["keep"] if sel else None
        atts = att_by_seq.get(i + 1, [])
        acc = [a for a in atts if a.get("accepted")]
        if c is not None:
            after = c["after_uids"]
        else:
            fullset = set(full)
            after = [u for u in prev_after if u in fullset] + [u for u in tail if u not in set(prev_after)]
        prev_set = set(prev_after)
        events.append({
            "step": S, "window": window, "tail": tail, "keep": keep, "after": after, "sel": sel,
            "accepted": bool(se.get("accepted")), "n_attempts": len(atts),
            "rejections": [a.get("rejected") for a in atts if not a.get("accepted")],
            "reasoning": acc[-1].get("reasoning") if acc else None,
            "directives": acc[-1].get("content") if acc else None,
            "sel_prompt_tokens": se.get("prompt_tokens"), "sel_completion_tokens": se.get("completion_tokens"),
            "sel_latency_s": se.get("latency_s"), "tokens_full": se.get("tokens_full"),
            "tokens_after": se.get("tokens_after"),
            "removed_uids": [u for u in window if u in prev_set and not (keep and u in keep)],
            "added_uids": [u for u in window if u not in prev_set and keep and u in keep],
        })
        prev_after = after
    return {"hist": hist, "order": order, "events": events,
            "n_steps": max(hist[u]["step"] for u in order) if order else 0}


def status_grid(run: dict) -> tuple[list[str], dict[str, dict[int, str]]]:
    """uid -> {step: W|P|D|T|.}"""
    hist, order = run["hist"], run["order"]
    grid: dict[str, dict[int, str]] = defaultdict(dict)
    steps = []
    for e in run["events"]:
        S = e["step"]
        steps.append(S)
        for u in order[:N_PROTECTED]:
            grid[u][S] = "."
        for u in e["tail"]:
            grid[u][S] = "T"
        if e["keep"] is None:
            for u in e["window"]:
                grid[u][S] = "U"        # selection not accepted: context unchanged
            continue
        for u in e["window"]:
            grid[u][S] = "D" if u not in e["keep"] else ("W" if e["keep"][u] is None else "P")
    return steps, grid


def lifecycle(statuses: str) -> str:
    s = statuses.replace("U", "")
    if not s:
        return ""
    kept_any = "W" in s or "P" in s
    returns = len(re.findall(r"D+[WP]", s))
    if not kept_any:
        return "never"
    if s.rstrip("D") == s and returns == 0:
        return "kept_to_end"
    if returns == 0:
        return "kept_then_dropped"
    return f"returned x{returns}"


HTML_HEAD = """<!doctype html><html><head><meta charset="utf-8"><title>{title}</title>
<style>
body{{font-family:system-ui,sans-serif;font-size:12px;margin:0;display:flex;flex-direction:column;height:100vh}}
#top{{padding:8px 12px;border-bottom:1px solid #ccc;background:#fafafa}}
#main{{display:flex;flex:1;min-height:0}}
#gridwrap{{flex:1;overflow:auto;border-right:1px solid #ccc}}
#panel{{width:46%;overflow:auto;padding:8px 12px;white-space:pre-wrap;font-family:ui-monospace,monospace;font-size:11.5px}}
table{{border-collapse:collapse}}
th,td{{padding:0;border:1px solid #eee;text-align:center}}
td.c{{width:11px;min-width:11px;height:14px;cursor:pointer}}
th.step{{position:sticky;top:0;background:#fff;font-weight:normal;writing-mode:vertical-rl;transform:rotate(180deg);height:46px;font-size:9px;cursor:pointer;z-index:2}}
th.step.sel{{background:#ffd}}
td.lab{{position:sticky;left:0;background:#fff;text-align:left;white-space:nowrap;padding:0 6px;font-family:ui-monospace,monospace;font-size:10.5px;cursor:pointer;z-index:1;max-width:520px;overflow:hidden;text-overflow:ellipsis}}
td.lab.sel{{background:#ffd}}
.W{{background:#4caf50}} .P{{background:#ffc107}} .D{{background:#f8d7da}} .T{{background:#90caf9}} .dot{{background:#ddd}} .U{{background:#bbb}}
.legend span{{display:inline-block;padding:1px 6px;margin-right:6px;border:1px solid #ccc}}
.role-a{{color:#1a237e}} .role-u{{color:#444}}
h3{{margin:6px 0}} .meta{{color:#666}}
</style></head><body>
<div id="top"><b>{title}</b> &nbsp; {summary}<br>
<span class="legend"><span class="W">W kept whole</span><span class="P">P kept lines</span><span class="D">D dropped</span><span class="T">T newest turn (verbatim)</span><span class="dot">. protected</span><span class="U">U selector failed (unchanged)</span></span>
&nbsp; rows = history messages (uid, step, role, category, command / output head); columns = selection before the model call of step+1. Click a column header for the selector's reasoning, a row label for the message text.</div>
<div id="main"><div id="gridwrap"><table id="grid"></table></div><div id="panel">Click a column header (selection step) or a row label (message).</div></div>
<script>
const D = {data};
const esc = s => (s||"").replace(/&/g,"&amp;").replace(/</g,"&lt;");
const grid = document.getElementById("grid");
let h = "<tr><th style='position:sticky;left:0;top:0;background:#fff;z-index:3'></th>";
for (const s of D.steps) h += `<th class="step" data-step="${{s}}" title="selection at step ${{s}}">${{s}}</th>`;
h += "</tr>";
for (const m of D.messages) {{
  h += `<tr><td class="lab role-${{m.role[0]}}" data-uid="${{m.uid}}" title="${{esc(m.label)}}">${{esc(m.label)}}</td>`;
  const st = m.status;
  for (let i = 0; i < D.steps.length; i++) {{
    const c = st[i] || " ";
    const cls = c === "." ? "dot" : (c === " " ? "" : c);
    h += `<td class="c ${{cls}}" data-uid="${{m.uid}}" data-i="${{i}}"></td>`;
  }}
  h += "</tr>";
}}
grid.innerHTML = h;
const panel = document.getElementById("panel");
function showStep(i) {{
  const e = D.events[i];
  document.querySelectorAll("th.step").forEach((t, j) => t.classList.toggle("sel", j === i));
  let out = `<h3>Selection at step ${{e.step}}</h3><div class="meta">window ${{e.window}} msgs → kept ${{e.kept_whole}} whole + ${{e.kept_partial}} partial, dropped ${{e.dropped}}; carried ${{e.carried}} / added ${{e.added}} / removed ${{e.removed}}; selected ${{e.selected_tokens}} tok, agent context after ${{e.tokens_after}} tok (full history ${{e.tokens_full}}); attempts ${{e.n_attempts}}${{e.rejections.length ? " (" + e.rejections.join(", ") + ")" : ""}}; selector ${{e.sel_completion_tokens}} completion tok, ${{e.sel_latency_s}} s</div>`;
  out += `<h3>Newest turn (kept verbatim)</h3>` + esc(e.newest) + "\\n";
  out += `<h3>Removed</h3>` + esc(e.removed_uids.join(", ") || "-") + `\\n<h3>Added back</h3>` + esc(e.added_uids.join(", ") || "-") + "\\n";
  out += `<h3>Selector reasoning</h3>` + esc(e.reasoning || "(none returned)") + "\\n";
  out += `<h3>Directives</h3>` + esc(e.directives || "(none)");
  panel.innerHTML = out;
}}
function showMsg(uid) {{
  const m = D.messages.find(x => x.uid === uid);
  document.querySelectorAll("td.lab").forEach(t => t.classList.toggle("sel", t.dataset.uid === uid));
  let s = m.status.replace(/ /g, "·");
  panel.innerHTML = `<h3>${{m.uid}} — step ${{m.step}}, ${{m.role}}, ${{m.cat}}${{m.returncode !== null && m.returncode !== undefined ? ", rc " + m.returncode : ""}}, ${{m.tokens}} tok, ${{m.lines}} lines; lifecycle: ${{m.lifecycle}}</h3><div class="meta">status over selections: ${{s}}</div>\\n` + esc(m.content);
}}
grid.addEventListener("click", ev => {{
  const t = ev.target;
  if (t.classList.contains("step")) showStep(+t.dataset.step !== undefined ? D.steps.indexOf(+t.dataset.step) : 0);
  else if (t.classList.contains("lab")) showMsg(t.dataset.uid);
  else if (t.classList.contains("c")) {{ showStep(+t.dataset.i); }}
}});
</script></body></html>"""


def export_run(run: dict, key: str, meta: dict, out_dir: str) -> dict:
    os.makedirs(out_dir, exist_ok=True)
    hist, order, events = run["hist"], run["order"], run["events"]
    steps, grid = status_grid(run)
    # messages.csv + matrix.csv
    msgs = []
    with open(f"{out_dir}/matrix.csv", "w", newline="") as fm, open(f"{out_dir}/messages.csv", "w", newline="") as fc:
        wm = csv.writer(fm); wc = csv.writer(fc)
        wm.writerow(["uid", "step", "role", "cat", "head"] + [str(s) for s in steps])
        wc.writerow(["uid", "seq", "step", "role", "cat", "returncode", "tokens", "lines", "n_selections_in_window",
                     "n_kept", "first_kept_step", "last_kept_step", "lifecycle", "statuses", "command_or_head"])
        for uid in order:
            h = hist[uid]
            row = grid.get(uid, {})
            st = "".join(row.get(s, " ") for s in steps)
            head = one_line(h.get("cmd") if h["role"] == "assistant" else h["content"], 90)
            wm.writerow([uid, h["step"], h["role"], h.get("cat", ""), head] + [row.get(s, "") for s in steps])
            in_win = [s for s in steps if row.get(s) in ("W", "P", "D")]
            kept = [s for s in steps if row.get(s) in ("W", "P")]
            lc = lifecycle("".join(row.get(s, "") for s in steps if row.get(s) in ("W", "P", "D", "U")))
            wc.writerow([uid, h["seq"], h["step"], h["role"], h.get("cat", ""), h.get("returncode", ""), h["tokens"],
                         h["lines"], len(in_win), len(kept), kept[0] if kept else "", kept[-1] if kept else "", lc, st, head])
            label = f"{uid} s{h['step']:>3} {h['role'][0]} {h.get('cat', ''):<13} rc={h.get('returncode', '-') if h['role']=='user' else '-'} | {head}"
            msgs.append({"uid": uid, "step": h["step"], "role": h["role"], "cat": h.get("cat", ""),
                         "returncode": h.get("returncode"), "tokens": h["tokens"], "lines": h["lines"],
                         "label": label, "status": st, "lifecycle": lc, "content": h["content"]})
    # selections.csv / .jsonl
    ev_rows = []
    with open(f"{out_dir}/selections.csv", "w", newline="") as fs, open(f"{out_dir}/selections.jsonl", "w") as fj:
        ws = csv.writer(fs)
        ws.writerow(["step", "newest_cat", "newest_rc", "newest_command", "window", "kept_whole", "kept_partial", "dropped",
                     "carried", "added", "removed", "selected_tokens", "tokens_after", "tokens_full", "accepted",
                     "n_attempts", "rejections", "sel_prompt_tokens", "sel_completion_tokens", "sel_latency_s",
                     "reasoning_chars", "removed_uids", "added_uids"])
        for e in events:
            sel = e["sel"] or {}
            newest_a = next((u for u in e["tail"] if hist[u]["role"] == "assistant"), None)
            newest_o = next((u for u in reversed(e["tail"]) if hist[u]["role"] == "user"), None)
            newest = ""
            if newest_a:
                newest += f"[{newest_a}] {hist[newest_a].get('cmd') or one_line(hist[newest_a]['content'], 300)}\n"
            if newest_o:
                newest += f"[{newest_o}] rc={hist[newest_o].get('returncode')}\n{hist[newest_o]['content'][:1500]}"
            row = {"step": e["step"], "newest_cat": hist[newest_a]["cat"] if newest_a else "",
                   "newest_rc": hist[newest_o].get("returncode") if newest_o else None,
                   "newest_command": one_line(hist[newest_a].get("cmd") if newest_a else "", 200),
                   "window": len(e["window"]), "kept_whole": sel.get("kept_whole"), "kept_partial": sel.get("kept_partial"),
                   "dropped": sel.get("dropped"), "carried": sel.get("carried"), "added": sel.get("added"),
                   "removed": sel.get("removed"), "selected_tokens": sel.get("selected_tokens"),
                   "tokens_after": e["tokens_after"], "tokens_full": e["tokens_full"], "accepted": e["accepted"],
                   "n_attempts": e["n_attempts"], "rejections": e["rejections"],
                   "sel_prompt_tokens": e["sel_prompt_tokens"], "sel_completion_tokens": e["sel_completion_tokens"],
                   "sel_latency_s": e["sel_latency_s"], "reasoning_chars": len(e["reasoning"] or ""),
                   "removed_uids": e["removed_uids"], "added_uids": e["added_uids"]}
            ws.writerow([row[k] if not isinstance(row[k], list) else " ".join(map(str, row[k])) for k in row])
            fj.write(json.dumps({**row, "newest": newest, "reasoning": e["reasoning"], "directives": e["directives"],
                                 "keep": e["keep"]}) + "\n")
            ev_rows.append({**row, "newest": newest, "reasoning": e["reasoning"], "directives": e["directives"]})
    n_sel = len(events)
    summary = (f"resolved={meta.get('resolved')} exit={meta.get('exit_status')} steps={run['n_steps']} selections={n_sel} "
               f"messages={len(order)} truncated_attempts={sum(r.count('truncated') for r in (e['rejections'] for e in events))} "
               f"not_accepted={sum(1 for e in events if not e['accepted'])}")
    data = {"steps": steps, "messages": msgs, "events": ev_rows}
    with open(f"{out_dir}/view.html", "w") as f:
        f.write(HTML_HEAD.format(title=html.escape(key), summary=html.escape(summary),
                                 data=json.dumps(data).replace("</", "<\\/")))
    return {"key": key, "resolved": meta.get("resolved"), "exit_status": meta.get("exit_status"),
            "steps": run["n_steps"], "selections": n_sel, "messages": len(order),
            "truncated_attempts": sum(r.count("truncated") for r in (e["rejections"] for e in events)),
            "not_accepted": sum(1 for e in events if not e["accepted"]), "dir": os.path.basename(out_dir)}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cell", help="cell dir holding <task>/<condition>/run_<n>/ and experiment_results.json")
    ap.add_argument("--out", required=True, help="output dir (one sub-folder per run)")
    ap.add_argument("--condition", default="*", help="condition dir name glob (default: all)")
    args = ap.parse_args()
    res_path = f"{args.cell}/experiment_results.json"
    rows = {r["key"]: r for r in json.load(open(res_path))} if os.path.exists(res_path) else {}
    index = []
    for run_dir in sorted(glob.glob(f"{args.cell}/*/{args.condition}/run_*")):
        if "/invalid/" in run_dir or not all(os.path.exists(f"{run_dir}/{n}") for n in
                                            ("events.jsonl", "token_log.json", "compression_events.jsonl")):
            continue
        task, cond, rn = run_dir.split("/")[-3:]
        key = f"{task}__{cond}__r{rn.split('_')[-1]}"
        meta = rows.get(key, {})
        run = load_run(run_dir)
        if not run["events"]:
            print("no select events:", run_dir, file=sys.stderr)
            continue
        info = export_run(run, key, meta, f"{args.out}/{task}__r{rn.split('_')[-1]}")
        index.append(info)
        print(f"{key}: {info['steps']} steps, {info['selections']} selections → {args.out}/{info['dir']}/view.html")
    os.makedirs(args.out, exist_ok=True)
    with open(f"{args.out}/index.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(index[0].keys()) if index else ["key"])
        w.writeheader(); w.writerows(index)
    with open(f"{args.out}/index.html", "w") as f:
        f.write("<!doctype html><meta charset='utf-8'><title>selection views</title><style>body{font-family:system-ui;font-size:13px}"
                "table{border-collapse:collapse}td,th{border:1px solid #ddd;padding:2px 8px}</style>"
                f"<h2>{html.escape(args.cell)}</h2><table><tr><th>run</th><th>resolved</th><th>steps</th><th>selections</th>"
                "<th>messages</th><th>truncated attempts</th><th>not accepted</th><th>files</th></tr>")
        for i in index:
            f.write(f"<tr><td><a href='{i['dir']}/view.html'>{html.escape(i['key'])}</a></td><td>{i['resolved']}</td>"
                    f"<td>{i['steps']}</td><td>{i['selections']}</td><td>{i['messages']}</td><td>{i['truncated_attempts']}</td>"
                    f"<td>{i['not_accepted']}</td><td><a href='{i['dir']}/matrix.csv'>matrix</a> "
                    f"<a href='{i['dir']}/messages.csv'>messages</a> <a href='{i['dir']}/selections.csv'>selections</a> "
                    f"<a href='{i['dir']}/selections.jsonl'>jsonl</a></td></tr>")
        f.write("</table>")
    print(f"index: {args.out}/index.html ({len(index)} runs)")


if __name__ == "__main__":
    main()
