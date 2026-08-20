from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from coherence_lineage import (  # noqa: E402
    RunHistory,
    annotate_invalidations,
    checkpoint_candidates,
    events_from_messages,
)


def assistant(command: str) -> dict:
    return {
        "role": "assistant",
        "content": f"THOUGHT\n```mswea_bash_command\n{command}\n```",
    }


def observation(output: str = "", returncode: int = 0) -> dict:
    return {
        "role": "user",
        "content": f"<returncode>{returncode}</returncode>\n<output>\n{output}\n</output>",
    }


class CoherenceLineageTest(unittest.TestCase):
    def test_read_mutate_reread_builds_strict_lineage(self) -> None:
        messages = [
            assistant("cat pkg/module.py"),
            observation("old value"),
            assistant("sed -i 's/old/new/' pkg/module.py"),
            observation(),
            assistant("cat pkg/module.py"),
            observation("new value"),
        ]
        history = RunHistory(
            trajectory=ROOT / "fake" / "task" / "full-context" / "run_1" / "trajectory.json",
            task="task",
            condition="full-context",
            run="run_1",
            api_calls=4,
            event_source="trajectory",
            history_complete=True,
            events=events_from_messages(messages),
            image="image",
        )

        annotate_invalidations(history)
        first, mutation, current = history.events
        self.assertEqual(first.read_paths, ["pkg/module.py"])
        self.assertEqual(mutation.mutation_paths, ["pkg/module.py"])
        self.assertEqual(first.invalidated_at_strict, 2)
        self.assertIsNone(current.invalidated_at_strict)

        candidates = checkpoint_candidates(history)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["stale_step"], 1)
        self.assertEqual(candidates[0]["mutation_step"], 2)
        self.assertEqual(candidates[0]["current_step"], 3)

    def test_stderr_redirection_does_not_create_mutation(self) -> None:
        messages = [
            assistant('grep -rn "needle" pkg/ 2>/dev/null | head -20'),
            observation("pkg/module.py:4:needle"),
        ]
        event = events_from_messages(messages)[0]
        self.assertTrue(event.is_search)
        self.assertFalse(event.is_mutation)
        self.assertFalse(event.broad_mutation)

    def test_test_result_is_superseded_by_any_recognized_edit(self) -> None:
        messages = [
            assistant("python3 -m pytest tests/test_module.py -q"),
            observation("1 failed"),
            assistant("touch pkg/marker.py"),
            observation(),
        ]
        history = RunHistory(
            trajectory=Path("unused"),
            task="task",
            condition="full-context",
            run="run_1",
            api_calls=3,
            event_source="trajectory",
            history_complete=True,
            events=events_from_messages(messages),
        )
        annotate_invalidations(history)
        self.assertTrue(history.events[0].is_test)
        self.assertEqual(history.events[0].invalidated_at_strict, 2)

    def test_markdown_code_is_not_parsed_as_an_executed_command(self) -> None:
        messages = [
            {
                "role": "assistant",
                "content": (
                    "Example only\n```python\nopen('wrong.py', 'w')\n```\n"
                    "```mswea_bash_command\ncat right.py\n```"
                ),
            },
            observation("right"),
        ]
        events = events_from_messages(messages)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].command, "cat right.py")

    def test_executed_generated_script_mutates_its_target(self) -> None:
        command = """cat > /tmp/edit.py << 'EOF'
from pathlib import Path
Path('/testbed/pkg/module.py').write_text('new')
EOF
python /tmp/edit.py"""
        event = events_from_messages([assistant(command), observation()])[0]
        self.assertIn("pkg/module.py", event.mutation_paths)
        self.assertIn("tmp/edit.py", event.mutation_paths)


if __name__ == "__main__":
    unittest.main()
