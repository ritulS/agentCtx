"""Export recorded query format errors without modifying experiment data."""

import argparse
import csv
import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path


RUN_FIELDS = [
    "benchmark", "section", "cohort_model_path", "model", "cell", "task",
    "condition", "run", "primitive", "budget_tokens", "depth",
    "metadata_source", "exit_status", "agent_calls_recorded",
    "compression_events", "summarization_prompt_tokens", "query_error_events",
    "summary_marker_errors", "unique_error_groups", "details_file", "trajectory",
]
EVENT_FIELDS = [
    "details_file", "error_group", "message_index_0based", "interrupt_type",
    "n_actions", "summary_marker", "timestamp", "trajectory",
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    source = args.source_root.resolve(strict=True)
    output = args.output_dir.resolve()
    if output.is_relative_to(source) or source.is_relative_to(output):
        parser.error("Output must be separate from the source tree")
    output.mkdir(parents=True, exist_ok=False)
    (output / "details").mkdir()
    warnings = []
    metadata_cache = {}

    def read_json(path):
        try:
            return json.loads(path.read_text())
        except (OSError, ValueError) as exc:
            warnings.append(f"{path}: {exc}")
            return {}

    def run_metadata(path):
        for parent in path.parents:
            if parent == source:
                break
            info_path = parent / "run_info.json"
            if info_path.exists():
                if info_path not in metadata_cache:
                    metadata_cache[info_path] = read_json(info_path)
                return parent, metadata_cache[info_path]
        return None, {}

    paths = sorted(source.rglob("trajectory.json"))
    totals = Counter()
    cell_counts = {}
    with (
        (output / "runs_with_errors.csv").open("w", newline="") as runs_file,
        (output / "error_events.csv").open("w", newline="") as events_file,
        (output / "runs_with_errors.txt").open("w") as text_file,
    ):
        runs_writer = csv.DictWriter(runs_file, fieldnames=RUN_FIELDS)
        events_writer = csv.DictWriter(events_file, fieldnames=EVENT_FIELDS)
        runs_writer.writeheader()
        events_writer.writeheader()
        text_file.write("Recorded query errors: one entry per affected run\n\n")
        for number, path in enumerate(paths, 1):
            data = read_json(path)
            if not isinstance(data.get("messages"), list):
                warnings.append(f"{path}: missing messages list")
                continue
            totals["trajectories_read"] += 1
            parent, run_info = run_metadata(path)
            if parent is None:
                warnings.append(f"{path}: no run_info.json; using path fallback")
                parent = path.parents[3]
            exit_path = path.with_name("exit_info.json")
            exit_info = read_json(exit_path) if exit_path.exists() else {}
            token_path = path.with_name("token_log.json")
            tokens = read_json(token_path) if token_path.exists() else {}
            rel = path.relative_to(source)
            info = data.get("info", {})
            model = info.get("config", {}).get("model", {}).get("model_name", run_info.get("model", ""))
            cell_match = re.match(r"d(\d+)__", parent.name)
            depth = exit_info.get("compression_ratio", "")
            metadata_source = "exit_info.json"
            if depth == "" and cell_match:
                digits = cell_match[1]
                depth = str(int(digits) / 10 ** (len(digits) - 1))
                metadata_source += "; depth from cell name"
            budget = exit_info.get("token_budget", run_info.get("budget_tokens", ""))
            primitive = exit_info.get("primitive", "")
            if depth == "" or budget == "" or primitive == "":
                warnings.append(f"{path}: incomplete compression metadata")
            row = {
                "benchmark": rel.parts[0], "section": rel.parts[1],
                "cohort_model_path": str(parent.parent.relative_to(source / rel.parts[0] / rel.parts[1])),
                "model": model, "cell": parent.name,
                "task": str(path.parents[2].relative_to(parent)),
                "condition": path.parents[1].name, "run": path.parent.name,
                "primitive": primitive, "budget_tokens": budget, "depth": depth,
                "metadata_source": metadata_source,
                "exit_status": info.get("exit_status") or exit_info.get("exit_status", ""),
                "agent_calls_recorded": info.get("model_stats", {}).get("api_calls", ""),
                "compression_events": tokens.get("compression_events", ""),
                "summarization_prompt_tokens": tokens.get("summarization_prompt_tokens", ""),
                "trajectory": str(path),
            }
            key = tuple(row[k] for k in (
                "benchmark", "section", "cohort_model_path", "cell", "model",
                "primitive", "budget_tokens", "depth",
            ))
            count = cell_counts.setdefault(key, Counter())
            count["runs_scanned"] += 1
            groups = {}
            occurrences = []
            for index, message in enumerate(data["messages"]):
                extra = message.get("extra") or {}
                if extra.get("interrupt_type") != "FormatError" and "model_response" not in extra:
                    continue
                response = extra.get("model_response", "")
                if not isinstance(response, str):
                    response = json.dumps(response, ensure_ascii=False)
                marker = "[CONTEXT SUMMARY]" in response or "[COMPRESSED HISTORY SUMMARY]" in response
                group_key = (extra.get("interrupt_type", ""), message.get("content", ""), response, extra.get("n_actions"))
                if group_key not in groups:
                    groups[group_key] = {"id": len(groups) + 1, "indices": [], "marker": marker}
                group = groups[group_key]
                group["indices"].append(index)
                occurrences.append({
                    "error_group": group["id"], "message_index_0based": index,
                    "interrupt_type": extra.get("interrupt_type", ""),
                    "n_actions": extra.get("n_actions", ""),
                    "summary_marker": marker, "timestamp": extra.get("timestamp", ""),
                    "trajectory": str(path),
                })
            if occurrences:
                totals["runs_with_query_errors"] += 1
                total_markers = sum(event["summary_marker"] for event in occurrences)
                totals["query_error_events"] += len(occurrences)
                totals["summary_marker_errors"] += total_markers
                totals["runs_with_summary_marker_errors"] += bool(total_markers)
                count["runs_with_query_errors"] += 1
                count["runs_with_summary_marker_errors"] += bool(total_markers)
                count["query_error_events"] += len(occurrences)
                count["summary_marker_errors"] += total_markers
                details_name = f"details/{totals['runs_with_query_errors']:05d}.txt"
                row.update(query_error_events=len(occurrences), summary_marker_errors=total_markers,
                           unique_error_groups=len(groups), details_file=details_name)
                runs_writer.writerow(row)
                header = "\n".join(f"{key}: {value}" for key, value in row.items())
                text_file.write(header + "\n\n")
                for occurrence in occurrences:
                    events_writer.writerow({"details_file": details_name, **occurrence})
                with (output / details_name).open("w") as detail:
                    detail.write(header + "\n\n")
                    for (kind, error, response, n_actions), group in groups.items():
                        detail.write(f"{'=' * 72}\nERROR GROUP {group['id']}\n")
                        detail.write(f"message_indices_0based: {group['indices']}\n")
                        detail.write(f"occurrences: {len(group['indices'])}\ninterrupt_type: {kind}\nn_actions: {n_actions}\n")
                        detail.write(f"summary_marker: {group['marker']}\n\nERROR MESSAGE:\n{error}\n\n")
                        detail.write(f"REJECTED MODEL RESPONSE (verbatim):\n{response}\n\n")
            if number % 250 == 0:
                print(f"Scanned {number}/{len(paths)}; affected runs={totals['runs_with_query_errors']}; errors={totals['query_error_events']}", flush=True)

    group_fields = ["benchmark", "section", "cohort_model_path", "cell", "model", "primitive", "budget_tokens", "depth"]
    count_fields = ["runs_scanned", "runs_with_query_errors", "runs_with_summary_marker_errors", "query_error_events", "summary_marker_errors"]
    with (output / "condition_summary.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=group_fields + count_fields)
        writer.writeheader()
        for key, count in sorted(cell_counts.items(), key=lambda item: tuple(map(str, item[0]))):
            writer.writerow(dict(zip(group_fields, key)) | {k: count[k] for k in count_fields})
    (output / "scan_warnings.txt").write_text("\n".join(warnings) + "\n")
    report = {
        "source_root": str(source), "generated_at": datetime.now().astimezone().isoformat(),
        "trajectory_paths_found": len(paths), **totals, "warnings": len(warnings),
    }
    (output / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))
    (output / "README.txt").write_text(
        "Recorded query errors (source data is read only)\n\n"
        + json.dumps(report, ensure_ascii=False, indent=2)
        + "\n\nFiles:\n"
        "- runs_with_errors.txt: Conditions, error counts, and links to full response files for each run\n"
        "- runs_with_errors.csv: The same index in CSV format\n"
        "- error_events.csv: One row per recorded error, with the zero-based message index in the trajectory\n"
        "- details/*.txt: Error reasons and full rejected model responses. Identical errors are grouped within each run, with all occurrence positions listed\n"
        "- condition_summary.csv: Scan and error counts per condition, including conditions with zero errors\n"
        "- scan_warnings.txt: Read failures and missing metadata\n\n"
        "Interpretation and limitations:\n"
        "- Extracts messages with FormatError or extra.model_response. This is not a comprehensive list of API errors or experiment failures.\n"
        "- summary_marker=True means the rejected response contains [CONTEXT SUMMARY] or [COMPRESSED HISTORY SUMMARY].\n"
        "  Summaries may lack markers, so False does not mean the error is unrelated to summarization. Markers alone cannot establish the call origin.\n"
        "- Full inputs to the summary API are not directly recorded in the trajectory. Do not treat full responses as input queries.\n"
        "- Each error event represents one saved error message, not an exact query count including API retries.\n"
        "- depth is the configured compression_ratio, not a measured compression ratio. di is the depth-invariant cell name; runtime settings take precedence from exit_info.json.\n"
        "- budget=999999999 is effectively unlimited.\n"
        "- compression_events / summarization_prompt_tokens reflect completed operations recorded in the logs and may exclude failed summary calls.\n"
        "- Logs updated during execution reflect their contents at read time. Source files may be missing or incomplete.\n"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
    print(f"Output: {output}", flush=True)


if __name__ == "__main__":
    main()
