#!/usr/bin/env python3
"""Build conservative observation lineages from stored agent trajectories.

The script has two jobs.

``scan`` measures observations that a later agent action supersedes. It uses
the structured ``trajectory.json`` history when that history is complete. If
compression removed earlier messages, it falls back to the full transcript in
``agent.log`` and marks the source in every output row.

``checkpoints`` selects high-confidence file-version conflicts for the RQ2
pilot. A selected checkpoint contains a file read, a later mutation of that
file, and a later read whose output differs. Checkpoint replay is implemented
in ``replay_coherence_checkpoints.py``.

The rules are deliberately high precision. They do not claim to recover every
mutation made by arbitrary shell or Python programs. Broad rules are recorded
separately so the paper can report strict and broad estimates.

Examples
--------
  python3 scripts/coherence_lineage.py scan \
    --glob 'results/ablations/p100-inf/*/full-context/run_*/trajectory.json' \
    --output results/coherence/fc_inf_lineage.csv \
    --details results/coherence/fc_inf_lineage.json

  python3 scripts/coherence_lineage.py checkpoints \
    --glob 'results/ablations/p100-inf/*/full-context/run_*/trajectory.json' \
    --limit 20 --output results/coherence/rq2_checkpoints.json
"""

from __future__ import annotations

import argparse
import csv
import glob
import hashlib
import json
import re
import shlex
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parent.parent

CODE_BLOCK_RE = re.compile(
    r"```mswea_bash_command[ \t]*\n(?P<command>.*?)```",
    re.DOTALL | re.IGNORECASE,
)
OBSERVATION_RE = re.compile(
    r"<returncode>(?P<returncode>-?\d+)</returncode>\s*"
    r"<output>\n?(?P<output>.*?)\n?</output>",
    re.DOTALL,
)
LOG_TURN_RE = re.compile(
    r"mini-swe-agent \(step\s+(?P<step>\d+),.*?\):.*?"
    r"```mswea_bash_command[ \t]*\n(?P<command>.*?)```.*?"
    r"\nUser:\s*\n<returncode>(?P<returncode>-?\d+)</returncode>\s*"
    r"<output>\n?(?P<output>.*?)\n?</output>",
    re.DOTALL,
)
ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")

PATH_RE = re.compile(
    r"(?<![A-Za-z0-9_])"
    r"(?P<path>(?:/testbed/)?(?:[A-Za-z0-9_.+-]+/)+[A-Za-z0-9_.+@-]+"
    r"|[A-Za-z0-9_.+-]+\.(?:py|pyi|c|cc|cpp|h|hpp|java|js|jsx|ts|tsx|rs|go|rb|"
    r"toml|yaml|yml|json|ini|cfg|txt|rst|md|sh|sql))"
)
PATCH_PATH_RE = re.compile(r"^\*\*\* (?:Update|Add|Delete) File:\s*(.+?)\s*$", re.MULTILINE)
HEREDOC_TARGET_RE = re.compile(
    r"(?:^|[;&|]\s*)(?:cat|tee)(?:\s+-[^\s]+)*\s*(?:>|>>)?\s*"
    r"(?P<path>[^\s;&|]+)\s*<<",
    re.MULTILINE,
)

READ_COMMAND_RE = re.compile(
    r"(?:^|[;&|]\s*)(?:cat|sed\s+-n|head|tail|less|more|nl|awk|git\s+(?:show|diff))\b"
)
SEARCH_COMMAND_RE = re.compile(r"(?:^|[;&|]\s*)(?:rg|grep|find)\b")
TEST_COMMAND_RE = re.compile(
    r"(?:^|\s)(?:pytest|py\.test|tox|nox|ctest|cargo\s+test|go\s+test|"
    r"python(?:3)?\s+-m\s+(?:pytest|unittest)|manage\.py\s+test)\b"
)
MUTATION_COMMAND_RE = re.compile(
    r"(?:"
    r"\bsed\s+-[^\n;&|]*i\b|\bperl\s+-[^\n;&|]*[pi]\b|"
    r"\bapply_patch\b|\bgit\s+apply\b|\bpatch\s+(?:-[^\s]+\s+)*|"
    r"\b(?:cp|mv|rm|touch|mkdir)\b|\btee\b|"
    r"\.write_text\s*\(|\.write_bytes\s*\(|"
    r"open\s*\([^\n)]*,\s*['\"][wax+]"
    r")"
)


def text_content(value: object) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts = []
        for block in value:
            if isinstance(block, dict):
                parts.append(str(block.get("text", "")))
            else:
                parts.append(str(block))
        return "\n".join(parts)
    return "" if value is None else str(value)


def normalize_output(value: str) -> str:
    value = ANSI_RE.sub("", value).replace("\r\n", "\n").replace("\r", "\n")
    return "\n".join(line.rstrip() for line in value.strip().splitlines())


def output_hash(value: str) -> str:
    return hashlib.sha256(normalize_output(value).encode("utf-8")).hexdigest()


def normalize_path(value: str) -> str | None:
    value = value.strip().strip("'\"`:,()[]{}")
    value = value.removeprefix("/testbed/").removeprefix("./")
    if not value or value.startswith("-") or "://" in value:
        return None
    if value in {"/dev/null", "dev/null"}:
        return None
    return value


def command_paths(command: str) -> set[str]:
    paths = {m.group("path") for m in PATH_RE.finditer(command)}
    paths.update(PATCH_PATH_RE.findall(command))
    normalized = {normalize_path(path) for path in paths}
    return {path for path in normalized if path}


def _shell_tokens(command: str) -> list[str]:
    try:
        return shlex.split(command, comments=False, posix=True)
    except ValueError:
        return command.split()


def mutation_paths(command: str, candidates: set[str]) -> tuple[set[str], bool]:
    """Return directly mutated paths and whether the mutation scope is broad."""
    heredoc = HEREDOC_TARGET_RE.search(command)
    if heredoc:
        target = normalize_path(heredoc.group("path"))
        # A heredoc mutates its redirection target. Paths mentioned inside a
        # generated script are effects only when that script later executes.
        return ({target} if target else set()), target is None

    specific_mutation = bool(MUTATION_COMMAND_RE.search(command))

    direct = set(PATCH_PATH_RE.findall(command))
    direct = {path for path in (normalize_path(p) for p in direct) if path}

    # Redirections and common file commands give reliable direct targets.
    redirect_re = re.compile(r"(?:\d*>>|(?<![0-9<>])>(?![>&]))\s*([^\s;&|]+)")
    for raw in redirect_re.findall(command):
        if path := normalize_path(raw):
            if Path(path).suffix or "/" in path:
                direct.add(path)

    tokens = _shell_tokens(command)
    for index, token in enumerate(tokens):
        base = Path(token).name
        if base in {"touch", "rm", "mv", "cp", "tee"}:
            for raw in tokens[index + 1 :]:
                if raw in {"&&", "||", ";", "|"}:
                    break
                if path := normalize_path(raw):
                    if path in candidates or Path(path).suffix or "/" in path:
                        direct.add(path)

    # For sed/perl in-place edits, all path-like arguments are plausible targets.
    if re.search(r"\bsed\s+-[^\n;&|]*i\b|\bperl\s+-[^\n;&|]*[pi]\b", command):
        direct.update(path for path in candidates if Path(path).suffix)

    # Embedded Python write calls often expose the target as a nearby string.
    if re.search(r"\.write_(?:text|bytes)\s*\(|open\s*\(", command):
        direct.update(path for path in candidates if Path(path).suffix or "/" in path)

    direct = {normalize_path(path) for path in direct}
    direct = {path for path in direct if path}

    is_mutation = specific_mutation or bool(direct)
    # An observed mutation with no precise target invalidates repository-wide
    # state only under the broad sensitivity rule.
    return direct, is_mutation and not bool(direct)


def resolve_generated_script_mutations(events: list[Event]) -> None:
    """Attach precise effects when a generated Python or shell script runs."""
    generated: dict[str, set[str]] = {}
    for event in events:
        heredoc = HEREDOC_TARGET_RE.search(event.command)
        if heredoc:
            script = normalize_path(heredoc.group("path"))
            if script:
                body_candidates = command_paths(event.command)
                effects, _ = mutation_paths_without_heredoc(event.command, body_candidates)
                effects.discard(script)
                if effects:
                    generated[script] = effects
                    invocation = re.compile(
                        rf"\b(?:python3?|bash|sh)\s+/?{re.escape(script.lstrip('/'))}\b"
                    )
                    if invocation.search(event.command):
                        event.mutation_paths = sorted(set(event.mutation_paths) | effects)
                        event.paths = sorted(set(event.paths) | effects)
            continue

        tokens = _shell_tokens(event.command)
        invoked = set()
        for index, token in enumerate(tokens[:-1]):
            if Path(token).name in {"python", "python3", "bash", "sh"}:
                if script := normalize_path(tokens[index + 1]):
                    invoked.add(script)
        effects = set().union(*(generated.get(script, set()) for script in invoked)) if invoked else set()
        if effects:
            event.mutation_paths = sorted(set(event.mutation_paths) | effects)
            event.paths = sorted(set(event.paths) | effects)
            event.is_mutation = True
            event.broad_mutation = False


def mutation_paths_without_heredoc(command: str, candidates: set[str]) -> tuple[set[str], bool]:
    """Apply mutation parsing to generated script text without heredoc guards."""
    match = HEREDOC_TARGET_RE.search(command)
    if not match:
        return mutation_paths(command, candidates)
    guarded = command[: match.start()] + command[match.end() :]
    return mutation_paths(guarded, candidates)


@dataclass
class Event:
    step: int
    command: str
    output: str
    returncode: int
    assistant_message_index: int | None = None
    observation_message_index: int | None = None
    paths: list[str] = field(default_factory=list)
    read_paths: list[str] = field(default_factory=list)
    search_paths: list[str] = field(default_factory=list)
    mutation_paths: list[str] = field(default_factory=list)
    is_read: bool = False
    is_search: bool = False
    is_test: bool = False
    is_mutation: bool = False
    broad_mutation: bool = False
    invalidated_at_strict: int | None = None
    invalidated_at_broad: int | None = None

    @property
    def observation_chars(self) -> int:
        return len(normalize_output(self.output))

    @property
    def output_sha256(self) -> str:
        return output_hash(self.output)

    @property
    def is_state_observation(self) -> bool:
        return self.is_read or self.is_search or self.is_test


@dataclass
class RunHistory:
    trajectory: Path
    task: str
    condition: str
    run: str
    api_calls: int
    event_source: str
    history_complete: bool
    events: list[Event]
    image: str = ""
    cwd: str = "/testbed"


def classify_event(event: Event) -> None:
    command = event.command
    paths = command_paths(command)
    event.paths = sorted(paths)
    mutated, broad = mutation_paths(command, paths)
    event.mutation_paths = sorted(mutated)
    event.is_mutation = bool(mutated) or broad
    event.broad_mutation = broad
    event.is_search = bool(SEARCH_COMMAND_RE.search(command)) and not event.is_mutation
    event.is_read = bool(READ_COMMAND_RE.search(command)) and not event.is_search and not event.is_mutation
    event.is_test = bool(TEST_COMMAND_RE.search(command))
    event.read_paths = sorted(paths) if event.is_read else []
    event.search_paths = sorted(paths) if event.is_search else []


def events_from_messages(messages: list[dict]) -> list[Event]:
    events: list[Event] = []
    pending: tuple[int, int, str] | None = None
    for message_index, message in enumerate(messages):
        role = message.get("role")
        content = text_content(message.get("content"))
        if role == "assistant":
            matches = list(CODE_BLOCK_RE.finditer(content))
            pending = None
            if matches:
                pending = (len(events) + 1, message_index, matches[-1].group("command").strip())
        elif role == "user" and pending:
            match = OBSERVATION_RE.search(content)
            if not match:
                continue
            step, assistant_index, command = pending
            event = Event(
                step=step,
                command=command,
                output=match.group("output"),
                returncode=int(match.group("returncode")),
                assistant_message_index=assistant_index,
                observation_message_index=message_index,
            )
            classify_event(event)
            events.append(event)
            pending = None
    resolve_generated_script_mutations(events)
    return events


def events_from_log(path: Path) -> list[Event]:
    if not path.exists():
        return []
    text = ANSI_RE.sub("", path.read_text(errors="replace"))
    events = []
    for match in LOG_TURN_RE.finditer(text):
        event = Event(
            step=int(match.group("step")),
            command=match.group("command").strip(),
            output=match.group("output"),
            returncode=int(match.group("returncode")),
        )
        classify_event(event)
        events.append(event)
    resolve_generated_script_mutations(events)
    return events


def _path_parts(path: Path) -> tuple[str, str, str]:
    # .../<task>/<condition>/run_N/trajectory.json
    return path.parents[2].name, path.parents[1].name, path.parent.name


def load_history(path: Path) -> RunHistory:
    data = json.loads(path.read_text())
    task, condition, run = _path_parts(path)
    messages = data.get("messages", [])
    api_calls = int(data.get("info", {}).get("model_stats", {}).get("api_calls", 0) or 0)
    structured = events_from_messages(messages)
    log_events = events_from_log(path.with_name("agent.log"))

    expected = max(0, api_calls - 1)  # final API call can be an exit message
    # Full-context runs never rewrite or drop messages. API-call counts can
    # exceed executed events because malformed model responses are retried, so
    # they are not a valid completeness check for these trajectories.
    structured_complete = condition == "full-context"
    if structured_complete or len(structured) >= len(log_events):
        events = structured
        source = "trajectory"
    else:
        events = log_events
        source = "agent_log"
    if source == "agent_log":
        complete = max((event.step for event in events), default=0) >= expected
    else:
        complete = structured_complete

    env = data.get("info", {}).get("config", {}).get("environment", {})
    return RunHistory(
        trajectory=path,
        task=task,
        condition=condition,
        run=run,
        api_calls=api_calls,
        event_source=source,
        history_complete=complete,
        events=events,
        image=str(env.get("image", "")),
        cwd=str(env.get("cwd", "/testbed")),
    )


def paths_overlap(left: Iterable[str], right: Iterable[str]) -> bool:
    left_set = set(left)
    right_set = set(right)
    if left_set & right_set:
        return True
    for a in left_set:
        for b in right_set:
            if a.startswith(b.rstrip("/") + "/") or b.startswith(a.rstrip("/") + "/"):
                return True
    return False


def annotate_invalidations(history: RunHistory) -> None:
    events = history.events
    for index, event in enumerate(events):
        if not event.is_state_observation:
            continue
        for later in events[index + 1 :]:
            if not later.is_mutation:
                continue

            strict_match = False
            if event.is_test:
                # Tests are repository-state observations. Any recognized
                # mutation supersedes them under the strict rule.
                strict_match = True
            elif event.is_read:
                strict_match = paths_overlap(event.read_paths, later.mutation_paths)
            elif event.is_search:
                strict_match = paths_overlap(event.search_paths, later.mutation_paths)

            if strict_match and event.invalidated_at_strict is None:
                event.invalidated_at_strict = later.step

            broad_match = strict_match or later.broad_mutation
            if event.is_search and later.is_mutation and not event.search_paths:
                broad_match = True
            if broad_match and event.invalidated_at_broad is None:
                event.invalidated_at_broad = later.step


def summarize_history(history: RunHistory) -> dict:
    annotate_invalidations(history)
    observations = [event for event in history.events if event.is_state_observation]
    n_steps = max((event.step for event in history.events), default=0)

    def aggregate(rule: str) -> tuple[int, int, int, int, float]:
        invalidated = []
        stale_char_turns = 0
        total_char_turns = 0
        for event in observations:
            invalidated_at = getattr(event, f"invalidated_at_{rule}")
            total_char_turns += event.observation_chars * max(0, n_steps - event.step)
            if invalidated_at is not None:
                invalidated.append(event)
                stale_char_turns += event.observation_chars * max(0, n_steps - invalidated_at)
        ratio = stale_char_turns / total_char_turns if total_char_turns else 0.0
        return len(invalidated), sum(e.observation_chars for e in invalidated), stale_char_turns, total_char_turns, ratio

    strict = aggregate("strict")
    broad = aggregate("broad")
    return {
        "trajectory": str(history.trajectory.relative_to(ROOT)),
        "task": history.task,
        "condition": history.condition,
        "run": history.run,
        "api_calls": history.api_calls,
        "parsed_events": len(history.events),
        "event_source": history.event_source,
        "history_complete": history.history_complete,
        "state_observations": len(observations),
        "observation_chars": sum(event.observation_chars for event in observations),
        "reads": sum(event.is_read for event in history.events),
        "searches": sum(event.is_search for event in history.events),
        "tests": sum(event.is_test for event in history.events),
        "mutations": sum(event.is_mutation for event in history.events),
        "precise_mutations": sum(event.is_mutation and bool(event.mutation_paths) for event in history.events),
        "broad_mutations": sum(event.broad_mutation for event in history.events),
        "strict_superseded_observations": strict[0],
        "strict_superseded_chars": strict[1],
        "strict_stale_char_turns": strict[2],
        "strict_observation_char_turns": strict[3],
        "strict_stale_exposure_ratio": strict[4],
        "broad_superseded_observations": broad[0],
        "broad_superseded_chars": broad[1],
        "broad_stale_char_turns": broad[2],
        "broad_observation_char_turns": broad[3],
        "broad_stale_exposure_ratio": broad[4],
    }


def expand_paths(patterns: list[str], tasks_file: str | None = None) -> list[Path]:
    found = []
    for pattern in patterns:
        candidate = Path(pattern)
        if candidate.is_absolute() and candidate.exists():
            found.append(candidate)
            continue
        found.extend(Path(path) for path in glob.glob(str(ROOT / pattern), recursive=True))
    paths = sorted({path.resolve() for path in found if path.name == "trajectory.json"})
    if tasks_file:
        task_path = Path(tasks_file)
        if not task_path.is_absolute():
            task_path = ROOT / task_path
        task_data = json.loads(task_path.read_text())
        allowed = {
            item["instance_id"] if isinstance(item, dict) else str(item)
            for item in task_data
        }
        paths = [path for path in paths if path.parents[2].name in allowed]
    # Multiple storage trees can contain the same task/run. Keep one physical
    # trajectory for each logical run when a cohort combines those trees.
    deduplicated = {}
    for path in paths:
        task, condition, run = _path_parts(path)
        deduplicated.setdefault((task, condition, run), path)
    return list(deduplicated.values())


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("")
        return
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def checkpoint_candidates(history: RunHistory) -> list[dict]:
    if history.event_source != "trajectory" or not history.history_complete:
        return []
    annotate_invalidations(history)
    candidates = []
    for stale in history.events:
        if not stale.is_read or stale.invalidated_at_strict is None or not stale.read_paths:
            continue
        for current in history.events:
            if current.step <= stale.invalidated_at_strict or not current.is_read:
                continue
            shared = sorted(set(stale.read_paths) & set(current.read_paths))
            if not shared or stale.output_sha256 == current.output_sha256:
                continue
            mutation = next(
                event
                for event in history.events
                if event.step == stale.invalidated_at_strict
            )
            candidates.append(
                {
                    "checkpoint_id": f"{history.task}__{history.run}__s{current.step}",
                    "task": history.task,
                    "condition": history.condition,
                    "run": history.run,
                    "trajectory": str(history.trajectory.relative_to(ROOT)),
                    "image": history.image,
                    "cwd": history.cwd,
                    "resource_paths": shared,
                    "stale_step": stale.step,
                    "mutation_step": mutation.step,
                    "current_step": current.step,
                    "checkpoint_message_index": current.observation_message_index,
                    "stale_command": stale.command,
                    "mutation_command": mutation.command,
                    "current_command": current.command,
                    "stale_output_sha256": stale.output_sha256,
                    "current_output_sha256": current.output_sha256,
                    "stale_output_chars": stale.observation_chars,
                    "current_output_chars": current.observation_chars,
                    "selection_score": min(stale.observation_chars, current.observation_chars),
                }
            )
            break
    return candidates


def command_scan(args: argparse.Namespace) -> None:
    paths = expand_paths(args.glob, args.tasks_file)
    print(f"[scan] {len(paths)} trajectories")
    rows = []
    details = []
    for index, path in enumerate(paths, 1):
        try:
            history = load_history(path)
            row = summarize_history(history)
            rows.append(row)
            if args.details:
                details.append(
                    {
                        "summary": row,
                        "events": [asdict(event) for event in history.events],
                    }
                )
        except Exception as exc:
            print(f"  skip {path}: {exc}")
            continue
        if index % 100 == 0 or index == len(paths):
            print(f"  [{index}/{len(paths)}]")

    output = Path(args.output)
    if not output.is_absolute():
        output = ROOT / output
    write_csv(output, rows)
    if args.details:
        details_path = Path(args.details)
        if not details_path.is_absolute():
            details_path = ROOT / details_path
        details_path.parent.mkdir(parents=True, exist_ok=True)
        details_path.write_text(json.dumps(details, indent=2))

    complete = sum(bool(row["history_complete"]) for row in rows)
    from_log = sum(row["event_source"] == "agent_log" for row in rows)
    strict_num = sum(int(row["strict_stale_char_turns"]) for row in rows)
    strict_den = sum(int(row["strict_observation_char_turns"]) for row in rows)
    print(f"[scan] wrote {len(rows)} rows to {output}")
    print(f"[scan] complete={complete}/{len(rows)}, agent_log_fallback={from_log}")
    if strict_den:
        print(f"[scan] pooled strict stale exposure={strict_num / strict_den:.4f}")


def command_checkpoints(args: argparse.Namespace) -> None:
    paths = expand_paths(args.glob, args.tasks_file)
    all_candidates = []
    for path in paths:
        try:
            all_candidates.extend(checkpoint_candidates(load_history(path)))
        except Exception as exc:
            print(f"  skip {path}: {exc}")

    # Prefer informative pairs, but keep at most one checkpoint per task.
    all_candidates.sort(key=lambda item: item["selection_score"], reverse=True)
    selected = []
    seen_tasks = set()
    for candidate in all_candidates:
        if candidate["task"] in seen_tasks:
            continue
        selected.append(candidate)
        seen_tasks.add(candidate["task"])
        if len(selected) >= args.limit:
            break

    output = Path(args.output)
    if not output.is_absolute():
        output = ROOT / output
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "selection": "one high-confidence file read-mutate-reread pair per task",
        "candidate_count": len(all_candidates),
        "selected_count": len(selected),
        "checkpoints": selected,
    }
    output.write_text(json.dumps(payload, indent=2))
    print(f"[checkpoints] {len(all_candidates)} candidates, {len(selected)} selected -> {output}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan = subparsers.add_parser("scan", help="Measure conservative observation lineages")
    scan.add_argument("--glob", action="append", required=True, help="Trajectory glob relative to repo root")
    scan.add_argument("--tasks-file", help="Optional task-list JSON used to filter matched trajectories")
    scan.add_argument("--output", required=True, help="Output CSV path")
    scan.add_argument("--details", help="Optional event-level JSON path")
    scan.set_defaults(func=command_scan)

    checkpoints = subparsers.add_parser("checkpoints", help="Select RQ2 file-version checkpoints")
    checkpoints.add_argument("--glob", action="append", required=True, help="Trajectory glob relative to repo root")
    checkpoints.add_argument("--tasks-file", help="Optional task-list JSON used to filter matched trajectories")
    checkpoints.add_argument("--limit", type=int, default=20)
    checkpoints.add_argument("--output", required=True, help="Output checkpoint manifest")
    checkpoints.set_defaults(func=command_checkpoints)
    return parser


if __name__ == "__main__":
    cli_args = build_parser().parse_args()
    cli_args.func(cli_args)
