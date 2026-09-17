"""Summarizer-provenance columns in aggregate_benchmark_results.py.

Run with: venv/bin/python -m unittest discover -s analysis -p "test_*.py" -v
"""

import contextlib
import csv
import io
import json
import tempfile
import unittest
from pathlib import Path

import aggregate_benchmark_results as agg


class SummarizerProvenanceTest(unittest.TestCase):
    def test_model_ablation_rows_carry_summarizer_and_join_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_root = root / "swebench"

            def write_cell(section, model_dir, n_tasks, run_info=None):
                cell = source_root / section / model_dir / "d05__b15k__su-full"
                cell.mkdir(parents=True)
                rows = [dict(instance_id=f"task{i}", condition="summarization",
                             budget=15000, compression_ratio=0.5, run_num=1,
                             n_calls=3, total_tokens=10, resolved=False)
                        for i in range(n_tasks)]
                (cell / "experiment_results.json").write_text(json.dumps(rows))
                if run_info is not None:
                    (cell / "run_info.json").write_text(json.dumps(run_info))

            write_cell("main", "qwen35b", 2)   # archived copy: no run_info.json
            write_cell("model_ablation", "qwen35b-sum-qwen35-9b", 2, run_info={
                "model": "hosted_vllm/Qwen/Qwen3.5-35B-A3B",
                "summary_model": "hosted_vllm/Qwen/Qwen3.5-9B",
                "summarization_model": {"source": "override",
                                        "model_name": "hosted_vllm/Qwen/Qwen3.5-9B"},
            })
            write_cell("model_ablation", "qwen35b-sum-qwen35-9b-smoke", 1)

            output = root / "out.csv"
            with contextlib.redirect_stdout(io.StringIO()):
                agg._RUN_INFO_CACHE.clear()
                agg.build("swebench", source_root, output)
            with output.open() as stream:
                rows = list(csv.DictReader(stream))

            self.assertEqual(len(rows), 4)   # the -smoke cell is skipped
            by_section = {}
            for row in rows:
                by_section.setdefault(row["experiment_section"], []).append(row)
            self.assertEqual(sorted(by_section), ["main", "model_ablation"])

            main = by_section["main"][0]
            self.assertEqual((main["model_key"], main["agent_model_key"]), ("qwen35b", "qwen35b"))
            self.assertEqual((main["summarizer_model"], main["summarizer_source"]),
                             ("", "agent_model"))

            abl = by_section["model_ablation"][0]
            self.assertEqual(abl["model_key"], "qwen35b-sum-qwen35-9b")
            self.assertEqual(abl["agent_model_key"], "qwen35b")   # joins with main/qwen35b
            self.assertEqual((abl["summarizer_model"], abl["summarizer_source"]),
                             ("hosted_vllm/Qwen/Qwen3.5-9B", "override"))
            self.assertEqual(abl["primitive"], "su-full")

    def test_run_record_beats_stale_run_info(self):
        # run_info.json is rewritten by every launch into the cell (e.g. a later
        # --eval-only pass without --summary-config); the per-run record made
        # at generation time must win.  Runs without a record fall back to it.
        with tempfile.TemporaryDirectory() as tmp:
            source_root = Path(tmp) / "swebench"
            cell = source_root / "model_ablation" / "qwen35b-sum-qwen35-9b" / "d05__b15k__su-full"
            cell.mkdir(parents=True)
            override = {"source": "override", "model_name": "hosted_vllm/Qwen/Qwen3.5-9B"}
            rows = [
                dict(instance_id="task0", condition="summarization", budget=15000,
                     compression_ratio=0.5, run_num=1, summarization_model=override),
                dict(instance_id="task1", condition="summarization", budget=15000,
                     compression_ratio=0.5, run_num=1),                       # no record
                dict(instance_id="task2", condition="summarization", budget=15000,
                     compression_ratio=0.5, run_num=1, summarization_model=None),
            ]
            (cell / "experiment_results.json").write_text(json.dumps(rows))
            (cell / "run_info.json").write_text(json.dumps(
                {"summarization_model": {"source": "agent_model"}}))   # stale
            output = Path(tmp) / "out.csv"
            with contextlib.redirect_stdout(io.StringIO()):
                agg._RUN_INFO_CACHE.clear()
                agg.build("swebench", source_root, output)
            with output.open() as stream:
                got = {r["task_name"]: (r["summarizer_model"], r["summarizer_source"])
                       for r in csv.DictReader(stream)}
            self.assertEqual(got["task0"], ("hosted_vllm/Qwen/Qwen3.5-9B", "override"))
            self.assertEqual(got["task1"], ("", "agent_model"))
            self.assertEqual(got["task2"], ("", "agent_model"))


if __name__ == "__main__":
    unittest.main()
