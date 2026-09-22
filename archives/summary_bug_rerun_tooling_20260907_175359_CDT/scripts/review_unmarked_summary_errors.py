"""Review the unmarked summary-condition runs from export_query_errors.py.

Uses recorded agent-call accounting to obtain a conservative lower bound on
summary failures. Response-content evidence is weaker and kept separate.
"""

import argparse
import csv
import json
import re
from collections import Counter
from pathlib import Path


SUMMARY_CUE = re.compile(
    r"(?:summari[sz](?:e|ing|ation)|summary|compress(?:ing|ion)?).{0,100}"
    r"(?:histor(?:y|ies)|conversation|approximately|words|working memory)"
    r"|(?:histor(?:y|ies)|conversation).{0,100}(?:summari[sz](?:e|ing|ation)|summary)"
    r"|(?:summary|summari[sz]e).{0,60}(?:current task objective|files examined|progress made)",
    re.I | re.S,
)
LABELS = {
    "summary_failure_accounting": "Includes summary failures (established by call accounting)",
    "summary_related_response": "Summary-related response detected (inferred from content; rerun candidate)",
    "not_established": "Connection to this summary bug could not be established",
}


def evidence(response):
    match = SUMMARY_CUE.search(response)
    if match:
        return "summary_language", response[max(0, match.start() - 60):match.end() + 160]
    # Summaries sometimes omit both the summary label and marker entirely.
    if all(phrase in response.lower() for phrase in (
        "current task objective", "files examined", "current state",
    )):
        return "summary_sections", response[:650]
    return "", ""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    audit = args.audit_dir.resolve(strict=True)
    output = args.output_dir.resolve()
    source = Path(json.loads((audit / "summary.json").read_text())["source_root"])
    if output.is_relative_to(source) or source.is_relative_to(output):
        parser.error("Output must be separate from the original experiment tree")
    output.mkdir(parents=True, exist_ok=False)
    with (audit / "runs_with_errors.csv").open() as stream:
        candidates = [r for r in csv.DictReader(stream)
                      if "summar" in r["primitive"] and int(r["summary_marker_errors"]) == 0]
    results = []
    counts = Counter()
    groups = Counter()
    for number, row in enumerate(candidates, 1):
        path = Path(row["trajectory"])
        trajectory = json.loads(path.read_text())
        tokens = json.loads(path.with_name("token_log.json").read_text())
        messages = trajectory["messages"]
        errors = [(i, m) for i, m in enumerate(messages)
                  if (m.get("extra") or {}).get("interrupt_type") == "FormatError"]
        # Do not silently apply a previous audit's conclusions to changed logs.
        assert len(errors) == int(row["query_error_events"]), f"Error count changed: {path}"
        assert trajectory["info"]["mini_version"] == "2.2.6", f"Review call accounting for version: {path}"
        assert all(not any(marker in str(m["extra"].get("model_response", ""))
                           for marker in ("[CONTEXT SUMMARY]", "[COMPRESSED HISTORY SUMMARY]"))
                   for _, m in errors), path
        calls = int(trajectory["info"]["model_stats"]["api_calls"])
        recorded_successes = len(tokens.get("step_prompt_tokens", []))
        retained_successes = sum(
            m.get("role") == "assistant" and "response" in (m.get("extra") or {})
            for m in messages
        )
        successes = max(recorded_successes, retained_successes)
        assert 0 <= successes <= calls, f"Inconsistent success/call counters: {path}"
        assert len(tokens.get("step_completion_tokens", [])) == recorded_successes, path
        # Normal queries increment n_calls BEFORE calling the model. Summary
        # queries happen before that increment. A normal failed query consumes
        # at least one of N-S slots. Missing old errors or in-flight/other failed
        # queries can only make this lower bound more conservative.
        normal_failure_slots = calls - successes
        lower_bound = max(0, len(errors) - normal_failure_slots)
        cues = []
        for index, message in errors:
            response = str(message["extra"].get("model_response", ""))
            kind, snippet = evidence(response)
            if kind:
                cues.append({"message_index_0based": index, "kind": kind, "snippet": snippet})
        category = ("summary_failure_accounting" if lower_bound else
                    "summary_related_response" if cues else "not_established")
        reason = (
            f"N={calls}, S>={successes}, F={len(errors)}; normal failure slots <= {normal_failure_slots}; "
            f"summary failures >= {lower_bound}."
        )
        if not lower_bound:
            reason += (" Rejected responses contain summary-request/output language; call origin is not recorded."
                       if cues else " No summary-specific response evidence; normal-agent format failures remain possible.")
        record = {
            **{k: row[k] for k in ("benchmark", "section", "cohort_model_path", "model", "cell",
                                  "task", "condition", "run", "primitive", "budget_tokens", "depth")},
            "classification": category, "classification_ja": LABELS[category],
            "agent_calls_N": calls, "recorded_successes": recorded_successes,
            "retained_successes": retained_successes, "success_lower_bound_S": successes,
            "retained_format_errors_F": len(errors),
            "normal_failure_slots_upper_bound": normal_failure_slots,
            "summary_failure_lower_bound": lower_bound,
            "summary_language_error_count": len(cues),
            "reason": reason,
            "evidence_message_index": cues[0]["message_index_0based"] if cues else errors[0][0],
            "evidence_snippet": cues[0]["snippet"] if cues else str(errors[0][1]["extra"].get("model_response", ""))[:650],
            "all_summary_cues": json.dumps(cues, ensure_ascii=False),
            "original_response_details": str(audit / row["details_file"]),
            "trajectory": str(path),
        }
        results.append(record)
        counts[category] += 1
        groups[(row["benchmark"], row["section"], row["cohort_model_path"], category)] += 1
        if number % 200 == 0:
            print(f"Reviewed {number}/{len(candidates)}", flush=True)

    fields = list(results[0])
    with (output / "review_unmarked.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(results)
    for category in LABELS:
        with (output / f"{category}.txt").open("w") as stream:
            stream.write(LABELS[category] + "\n\n")
            for record in results:
                if record["classification"] != category:
                    continue
                for key, value in record.items():
                    if key != "all_summary_cues":
                        stream.write(f"{key}: {value}\n")
                stream.write("\n" + "=" * 72 + "\n\n")
    with (output / "by_model.csv").open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["benchmark", "section", "cohort_model_path", "classification", "runs"])
        for key, value in sorted(groups.items()):
            writer.writerow([*key, value])
    summary = {"reviewed_runs": len(results), "classifications": dict(counts),
               "additional_rerun_candidates": sum(counts[k] for k in LABELS if k != "not_established")}
    (output / "summary.json").write_text(json.dumps(summary, indent=2))
    (output / "README.txt").write_text(
        f"Additional review of {len(results)} runs without summary markers\n\n"
        + json.dumps(summary, indent=2, ensure_ascii=False)
        + "\n\nClassification method:\n"
        "1. Call accounting: In mini-swe-agent 2.2.6, DefaultAgent.query increments n_calls after summarization and then makes the normal agent query.\n"
        "   N = recorded normal agent calls, S = lower bound on successful calls, F = retained FormatError count.\n"
        "   Normal agent failures cannot exceed N-S, so if F-(N-S)>0, at least that many errors are summary failures.\n"
        "   S is the larger of the step_prompt_tokens count in token_log and the successful response count in the trajectory.\n"
        "   This lower bound remains valid even if compression removed older errors. It does not identify the origin of every individual error.\n"
        "2. Response content: A response is classified as summary-related if it mentions a summary request, summarizes history, or contains multiple summary headings.\n"
        "   Normal agent responses may refer to previous summaries, so these are rerun candidates rather than confirmed summary calls.\n"
        "3. not_established means the evidence above is insufficient. It does not mean normal behavior, no summary impact, or no need to rerun.\n"
        "   Some runs lack complete histories; this classification cannot rule out effects from summaries accepted in command format.\n\n"
        f"Files:\nreview_unmarked.csv: Conditions, classifications, evidence, and original response references for all {len(results)} runs\n"
        "summary_failure_accounting.txt: Runs identified through call accounting\n"
        "summary_related_response.txt: Additional rerun candidates based on response content\n"
        "not_established.txt: Runs whose connection to the summary bug could not be established\n"
        "by_model.csv: Counts by model and main/ablation section\n\n"
        "The original ICLR_results are read only. Error counts are checked against the previous audit, and version and counter consistency are verified.\n"
    )
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
