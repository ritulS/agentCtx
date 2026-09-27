"""Result-row conventions shared by every benchmark adapter.

Deliberately dependency-free so both the SWE-bench and Harbor sides can import
it without pulling in the other's machinery.
"""

from __future__ import annotations


def run_key(instance_id: str, condition: str, run_num: int) -> str:
    """Identity of one (task, condition, repetition) result row.

    An adapter stamps this onto every row it writes and tests it against the
    existing results to skip already-collected work, so both sides must read
    the format from here; copies drifting apart would silently re-run
    completed batches.
    """
    return f"{instance_id}__{condition}__r{run_num}"
