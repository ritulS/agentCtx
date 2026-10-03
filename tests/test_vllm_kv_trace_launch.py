"""KV ownership tracing is on by default in the vLLM serving launchers
(scripts/lib/vllm_kv_trace.sh, scripts/serving/start_vllm_*.sh).

Run with: uvx --with pyyaml pytest tests/test_vllm_kv_trace_launch.py
"""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
HELPER = ROOT / "scripts/lib/vllm_kv_trace.sh"
SERVING = ROOT / "scripts/serving"
SERVER_LOG = "vllm_qwen35_a3b_20261003_120000.log"


def _helper(log_root: Path, **env) -> list[str]:
    """Source the helper as a launcher does; return KV_TRACE_ARGS, the trace dir
    and the status line, one per line."""
    script = (f'WS={ROOT}; LOG_ROOT={log_root}; source {HELPER}; '
              f'kv_trace_args "{log_root}/servers/{SERVER_LOG}"; '
              'echo "${KV_TRACE_ARGS[*]}"; echo "${AGENTCTX_KV_TRACE_DIR:-}"; kv_trace_status')
    base = {k: v for k, v in os.environ.items()
            if k not in ("AGENTCTX_KV_TRACE", "AGENTCTX_KV_TRACE_DIR")}
    out = subprocess.run(["bash", "-c", script], env={**base, **env},
                         capture_output=True, text=True, check=True)
    return out.stdout.splitlines()


class KvTraceDefaultTests(unittest.TestCase):
    def test_on_by_default_next_to_the_server_log(self):
        with tempfile.TemporaryDirectory() as tmp:
            args, trace_dir, status = _helper(Path(tmp))
            expected = Path(tmp) / "kv-cache" / "vllm_qwen35_a3b_20261003_120000"
            self.assertEqual(args, "--scheduler-cls agentctx.vllm_kv_trace.TracingScheduler")
            self.assertEqual(trace_dir, str(expected))
            self.assertTrue(expected.is_dir())
            self.assertEqual(status, f"KV ownership trace: {expected}")

    def test_explicit_dir_wins(self):
        with tempfile.TemporaryDirectory() as tmp:
            args, trace_dir, _ = _helper(Path(tmp), AGENTCTX_KV_TRACE_DIR=f"{tmp}/mine")
            self.assertIn("--scheduler-cls", args)
            self.assertEqual(trace_dir, f"{tmp}/mine")
            self.assertFalse((Path(tmp) / "kv-cache").exists())

    def test_opt_out(self):
        with tempfile.TemporaryDirectory() as tmp:
            args, trace_dir, status = _helper(Path(tmp), AGENTCTX_KV_TRACE="0",
                                              AGENTCTX_KV_TRACE_DIR=f"{tmp}/mine")
            self.assertEqual((args, trace_dir), ("", ""))
            self.assertIn("OFF", status)
            self.assertFalse(Path(tmp, "mine").exists())

    def test_every_launcher_sets_the_args_before_starting_vllm(self):
        for path in sorted(SERVING.glob("start_vllm_*.sh")):
            text = path.read_text()
            if "vllm.entrypoints" not in text:   # wrappers that exec another launcher
                continue
            with self.subTest(launcher=path.name):
                setup = text.index('kv_trace_args "$LOG_FILE"')
                self.assertLess(text.index('LOG_FILE="$(server_log'), setup)
                self.assertLess(setup, text.index('"${KV_TRACE_ARGS[@]}"'))
                self.assertIn("kv_trace_status", text)


if __name__ == "__main__":
    unittest.main()
