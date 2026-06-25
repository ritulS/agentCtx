"""Seed split-by-group depth dirs from existing depth-30 / depth-70 (30 ABL @ 20k).

For each src in (depth-30, depth-70):
  - Read results/ablations/<src>/experiment_results.json
  - For each row, route by condition into one of:
      p100-depth30-singles-20000  (truncation, summarization, summarization-partial,
                                   structured-summarize, structured-summarize-partial)
      p100-depth30-trc-20000      (tool-result-clear, trc-su, trc-ss)
      p100-depth70-singles-20000  (same conditions as singles above)
      p100-depth70-trc-20000      (same as trc above)
  - Append the row to the target's experiment_results.json (idempotent: skip if key present)
  - Copy the matching <task>/<condition>/run_<n>/ trajectory dir over

Use --dry-run to preview without writing.
"""
import argparse, json, shutil, sys
from pathlib import Path

ROOT = Path("/home/rs67788/projects/agentCtx")

SINGLES = {"truncation","summarization","summarization-partial",
           "structured-summarize","structured-summarize-partial"}
TRC     = {"tool-result-clear","trc-su","trc-ss"}

def group_for(cond):
    if cond in SINGLES: return "singles"
    if cond in TRC:     return "trc"
    return None  # otrc-* not present in depth-30/70 sources

def target_dir(depth_tag, group, budget=20000):
    return ROOT / "results/ablations" / f"p100-{depth_tag}-{group}-{budget}"

def load_or_init(p):
    if p.exists(): return json.loads(p.read_text())
    return []

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    sources = [("depth-30", "depth30"), ("depth-70", "depth70")]
    summary = {}
    for src, depth_tag in sources:
        src_path = ROOT / "results/ablations" / src / "experiment_results.json"
        rows = json.loads(src_path.read_text())
        # Group rows by destination
        targets = {}
        skipped_otrc = 0
        for r in rows:
            cond = r.get("condition")
            grp = group_for(cond)
            if grp is None:
                skipped_otrc += 1
                continue
            tdir = target_dir(depth_tag, grp)
            targets.setdefault(tdir, []).append(r)

        # Write per target
        for tdir, src_rows in targets.items():
            rj = tdir / "experiment_results.json"
            if not args.dry_run:
                tdir.mkdir(parents=True, exist_ok=True)
            existing = load_or_init(rj)
            existing_keys = {r.get("key") for r in existing}
            new_rows = [r for r in src_rows if r.get("key") not in existing_keys]

            # Copy trajectory dirs
            copied = 0
            for r in new_rows:
                iid = r.get("instance_id")
                cond = r.get("condition")
                rn = r.get("run_num")
                src_run = ROOT / "results/ablations" / src / iid / cond / f"run_{rn}"
                dst_run = tdir / iid / cond / f"run_{rn}"
                if src_run.exists():
                    if not args.dry_run:
                        dst_run.parent.mkdir(parents=True, exist_ok=True)
                        if not dst_run.exists():
                            shutil.copytree(src_run, dst_run)
                    copied += 1

            # Update experiment_results.json
            if not args.dry_run:
                merged = existing + new_rows
                rj.write_text(json.dumps(merged, indent=2))

            summary[tdir.name] = (len(src_rows), len(new_rows), copied)

        if skipped_otrc:
            summary[f"{src} otrc-skipped"] = skipped_otrc

    print(("=== DRY RUN ===" if args.dry_run else "=== SEED COMPLETE ==="))
    for k, v in summary.items():
        if isinstance(v, tuple):
            n_src, n_new, n_copied = v
            print(f"  {k}: src={n_src} new_rows_added={n_new} trajectory_dirs_copied={n_copied}")
        else:
            print(f"  {k}: {v}")

if __name__ == "__main__":
    main()
