# Rework Metric Design

## Motivation

Failing runs in mini-swe-agent exhibit a cascade failure pattern: repeated context
compression events cause the agent to re-read and re-search files it has already
visited, consuming tokens without making progress. We want a metric that quantifies
this redundancy per run, captures how it escalates, and can be computed online during
a run.

---

## Two Observed Failure Patterns

### Pattern 1 — Post-compression re-orientation
After each compression event, the agent immediately re-reads the same files that
were just removed from context. Example from django__django-11292 TR run:

- Event 2 fires at step 34. Steps 35–36 immediately re-read `base.py` and
  `__init__.py` — both already read in window 1.
- By event 4, all 5 post-compression commands are rework (100%).

The agent re-reads to restore the mental model it lost. This is the classic
"forgot after compression" pattern.

### Pattern 2 — Intra-window spinning
The agent runs the same command repeatedly within a single window, without any
intervening compression. Example from django__django-11292 TR, steps 70–77:

```
[70] grep -n "skip.checks" tests/user_commands/tests.py
[71] sed -n '145,175p' tests/user_commands/tests.py
[72] grep -n "skip.checks" tests/user_commands/tests.py   ← same as [70]
[73] grep -n "skip.checks" tests/user_commands/tests.py   ← same
[74] grep -n "skip.checks" tests/user_commands/tests.py   ← same
[75] grep -n "skip.checks" tests/user_commands/tests.py   ← same
[76] grep -n "skip.checks" tests/user_commands/tests.py   ← same
[77] grep -n "skip.checks" tests/user_commands/tests.py   ← same
```

This is not a compression artifact — it happens within a single context window.
The agent is not processing its own outputs. Prior window-level metrics (inter-window
redundancy) missed this entirely.

**Key insight**: both patterns have the same underlying cause — the agent re-issues
a command whose result is already available. A single per-command check captures both.

---

## Algorithm

### Canonicalization

Map each shell command to a `(family, target)` tuple or `NULL`.

**Families:**
| Family  | Commands                          | Target              |
|---------|-----------------------------------|---------------------|
| READ    | cat, sed, head, tail, awk         | normalized file path |
| SEARCH  | grep, find, rg, ag                | normalized path/dir |
| EXECUTE | python script, pytest, bash       | script path         |
| INSTALL | pip install                       | sorted package list |
| WRITE   | redirect >, tee, heredoc          | normalized file path |
| UNSCORE | cd, ls, pwd, python -c, git, ...  | NULL                |

**Path normalization:** strip `/testbed/`, `/workspace/`, `/repo/` prefixes; strip
leading `./`; collapse double slashes.

**Equivalences the canonical key captures:**
- `sed -n '200,250p' base.py` == `cat base.py` == `head -50 base.py`
  → all `('READ', 'django/core/management/base.py')`
- `grep "skip_checks" base.py` == `grep "skip.checks" base.py`
  → both `('SEARCH', 'django/core/management/base.py')`
- `cd /testbed && cat base.py` == `cat /testbed/base.py`
  → both `('READ', 'django/core/management/base.py')`

### Labeling (pseudocode)

```
seen ← {}          # global set, never reset, never window-scoped

for (step, cmd) in commands_in_order:
    c ← canonicalize(cmd)          # (family, target) or NULL

    if c is NULL:
        label ← UNSCORE            # not counted in rework rate
    elif c ∈ seen:
        label ← REWORK
    else:
        label ← FRESH
        seen.add(c)                # add only on first encounter

    record (step, c, label)
```

**No write-reset.** Re-reading a file after editing it still counts as REWORK.
Rationale: the re-read produces no new information because the agent could have
reasoned about the edit it just made. In practice, write-reset adds complexity
without changing the signal meaningfully (writes are rare and the file content
changes only once).

### Derived metrics

```
# 1. Overall rework rate for a run
rework_rate(run) = |{REWORK}| / (|{FRESH}| + |{REWORK}|)

# 2. Per-window escalation curve
# Partition steps by compression event boundaries
window_rework_rate[N] = rework_rate over steps in window N

# 3. Post-compression re-orientation severity
# First K=5 scoreable commands after each event
post_compression_rework[N] = rework_rate over first K scoreable steps after event N
```

---

## Validation on django__django-11292 (TR run_1, 9 compression events)

```
Total steps:       124
FRESH:              15  (12%)
REWORK:             71  (57%)
UNSCORE:            38  (31%)

Overall rework rate (scoreable):  82.6%
```

**Window-by-window escalation:**

| Window | Steps | Scoreable | Rework | Rate   |
|--------|-------|-----------|--------|--------|
| W0     |  10   |     9     |    4   | 44.4%  |
| W1     |  21   |    12     |    7   | 58.3%  |
| W2     |   3   |     2     |    0   |  0.0%  |
| W3     |  19   |    12     |   10   | 83.3%  |
| W4     |  19   |    17     |   17   | 100%   |
| W5     |  20   |    18     |   18   | 100%   |
| W6     |  15   |     5     |    5   | 100%   |
| W7     |   3   |     1     |    1   | 100%   |
| W8     |   4   |     3     |    3   | 100%   |

**Post-compression re-orientation (K=5):**

| Event | Step | Rework/K | Rate   |
|-------|------|----------|--------|
|   1   |  12  |   2/5    | 40.0%  |
|   2   |  34  |   3/5    | 60.0%  |
|   3   |  38  |   4/5    | 80.0%  |
|   4   |  58  |   5/5    | 100%   |
|   5   |  78  |   5/5    | 100%   |
|   6   |  99  |   5/5    | 100%   |
|   7   | 115  |   5/5    | 100%   |
|   8   | 119  |   5/5    | 100%   |
|   9   | 124  |   1/1    | 100%   |

**Observations:**
- W0 = 44% rework before any compression fires — spinning is intrinsic to model
  behavior, not purely a compression artifact.
- The agent exhausts all novel exploration in ~15 commands (by step ~20). Every
  subsequent step revisits the same small orbit of files.
- Once post-compression rework hits 100% (event 4), the run never recovers.
  Window sizes collapse: W7=3 cmds, W8=4 cmds — compression fires faster than
  the agent can do new work.
- W2 = 0% is real: agent briefly explored two new files after event 2, which
  caused event 3 to fire immediately (large file reads consume tokens fast).
  Brief genuine exploration does not break the cascade.

---

## Online Applications

### Application 1 — Early stopping signal

The `seen` set grows in real time with zero overhead. After each step you know
whether it was REWORK or FRESH.

**Stopping criterion:**
```
abort if:
    recent_rework_rate(last 10 scoreable commands) >= 0.95
    AND at least 1 compression event has fired
```

The "AND compression fired" guard prevents aborting runs doing normal early
exploration (W0 = 44% is high but acceptable; the run hasn't hit a cascade yet).

**Token savings on django-11292:** criterion triggers at end of event 4 (step ~60).
Run continues for 64 more steps across 5 more compression events — all 100% rework,
zero progress. Early stopping saves ~50% of total token spend with zero change in
outcome (run was unrecoverable).

**To evaluate across tasks:** for each run, record (a) the step where criterion
first triggers, (b) remaining tokens past that point, (c) whether the run ever
submitted after that step. This gives precision/recall for the stopping signal.

### Application 2 — Compression-time injection

**Root cause:** compression removes recent READ/SEARCH results; agent re-reads to
restore context. If you know what the agent is about to re-read, you can inject
that information as part of the compression step rather than waiting for re-reads.

**Mechanism:** when compression fires, scan `seen` for tuples with rework count ≥ 2.
Append a context note to the surviving messages summarizing their key findings:

```
[Compression note: the following were already established — do not re-read]
- django/core/management/base.py: --skip-checks argument added at line 288
- tests/user_commands/tests.py: relevant test cases at lines 155–180
```

The note content is extracted from the actual tool results before they are dropped.

**Advantage over action log pilot:** the action log requires behavioral compliance
from the agent (agent must write to `.done.txt` after every command). Compression
injection happens at the harness level — guaranteed to survive compression because
it is injected into the surviving context as part of the compression step itself.

**Tradeoff:** requires modifying the compression logic to (a) parse tool results
before dropping them and (b) generate the summary note. More engineering effort.
Suitable for the intervention section / future work.

### Composing both

The two methods compose naturally:
- Use **compression injection** when rework rate is moderate (50–80%) — the agent
  may still recover with better context.
- Use **early stopping** as a safety net when rework rate hits ~100% — the run is
  unrecoverable and further tokens are wasted.

---

## Open questions

- Does the pattern generalize across tasks and repos? Need per-task rework curves
  for all 10 inspection tasks.
- What is the rework rate distribution for *submitted* runs vs. *failed* runs?
  If submitted runs have low rework rate, the metric is a strong failure predictor.
- What is the right K for post-compression re-orientation? K=5 is arbitrary; could
  sweep K=3,5,10 to find the most discriminative window.
- Intra-window spinning (Pattern 2) vs. cross-window rework (Pattern 1): do they
  have different implications? Pattern 2 may indicate a model inference issue
  (not reading own outputs) while Pattern 1 is clearly compression-driven.
