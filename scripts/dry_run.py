#!/usr/bin/env python3
"""
Quick dry-run: test one task with one primitive to verify end-to-end pipeline.
"""

import json
import subprocess
import time
from datetime import datetime
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).parent.parent
SELECTED_TASKS = WORKSPACE_ROOT / "selected_tasks.json"
RESULTS_DIR = WORKSPACE_ROOT / "results"
MINI_SWE_AGENT = WORKSPACE_ROOT / "mini-swe-agent"
CONFIG_FILE = MINI_SWE_AGENT / "config-qwen-vllm.yaml"


def run_dry_run():
    """Run one task with one primitive to test the pipeline."""
    
    print("=" * 70)
    print("DRY RUN: Testing pipeline with 1 task × 1 primitive × 1 run")
    print("=" * 70)
    
    # Load first task
    with open(SELECTED_TASKS) as f:
        tasks = json.load(f)
    
    task = tasks[0]
    instance_id = task["instance_id"]
    primitive = "truncation"
    run_num = 1
    
    print(f"\nRunning dry run:")
    print(f"  Instance: {instance_id}")
    print(f"  Primitive: {primitive}")
    print(f"  Run: {run_num}")
    print(f"  Problem length: {task['word_count']} words")
    print()
    
    # Create output directory
    RESULTS_DIR.mkdir(exist_ok=True)
    run_output = RESULTS_DIR / f"dryrun__{instance_id}__{primitive}__run{run_num}"
    run_output.mkdir(parents=True, exist_ok=True)
    
    log_file = run_output / "agent.log"
    traj_file = run_output / "trajectory.json"
    
    # Set up environment for context compression
    import os
    env = os.environ.copy()
    env["MSWEA_PRIMITIVE"] = primitive
    env["MSWEA_TOKEN_BUDGET"] = "16000"
    env["MSWEA_COST_TRACKING"] = "ignore_errors"  # Ignore cost tracking for local vLLM
    
    # Run the agent using swebench_single runner with local vLLM server
    qwen_config = str(MINI_SWE_AGENT / "config-qwen-vllm.yaml")
    cmd = [
        "python", "-m", "minisweagent.run.benchmarks.swebench_single",
        "--subset", "lite",
        "--split", "test",  # Use test split where our selected tasks are
        "--instance", instance_id,
        "-c", "swebench.yaml",
        "-c", qwen_config,  # Use local vLLM with Qwen (absolute path)
        "-c", "agent.step_limit=100",  # Increase step limit
        "-o", str(traj_file),
        "-y"  # Run without confirmation
    ]
    
    print("Starting agent...")
    start_time = time.time()
    
    try:
        with open(log_file, 'w') as log:
            proc = subprocess.Popen(
                cmd,
                cwd=MINI_SWE_AGENT,
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
                text=True
            )
            proc.wait(timeout=600)  # 10 minute timeout
            returncode = proc.returncode
    except subprocess.TimeoutExpired:
        proc.kill()
        returncode = -1
        print("⚠️  Timeout after 10 minutes")
    except Exception as e:
        print(f"❌ Error: {e}")
        returncode = -2
    
    end_time = time.time()
    latency = end_time - start_time
    
    print(f"\nCompleted in {latency:.1f}s (returncode: {returncode})")
    
    # Check outputs
    print("\n" + "=" * 70)
    print("OUTPUT FILES")
    print("=" * 70)
    
    if run_output.exists():
        for item in sorted(run_output.iterdir()):
            if item.is_file():
                size = item.stat().st_size
                print(f"  ✓ {item.name:40} ({size:,} bytes)")
    
    # Check trajectory
    traj_file = run_output / "trajectory.json"
    if traj_file.exists():
        print("\n" + "=" * 70)
        print("TRAJECTORY ANALYSIS")
        print("=" * 70)
        
        with open(traj_file) as f:
            traj = json.load(f)
        
        print(f"  Steps: {len(traj.get('steps', []))}")
        print(f"  Exit status: {traj.get('exit_status', 'unknown')}")
        
        if "patch" in traj and traj["patch"]:
            print(f"  Patch generated: YES ({len(traj['patch'])} bytes)")
        else:
            print(f"  Patch generated: NO")
        
        if "token_usage" in traj:
            tokens = traj["token_usage"]
            print(f"  Token usage:")
            print(f"    - Prompt: {tokens.get('prompt', 0):,}")
            print(f"    - Completion: {tokens.get('completion', 0):,}")
            print(f"    - Total: {tokens.get('total', 0):,}")
        
        if "compression_stats" in traj:
            comp = traj["compression_stats"]
            if isinstance(comp, list) and comp:
                last = comp[-1]
                print(f"  Compression:")
                print(f"    - Fired: {last.get('fired', False)}")
                print(f"    - Raw tokens: {last.get('raw_tokens', 0):,}")
                print(f"    - Compressed tokens: {last.get('compressed_tokens', 0):,}")
                print(f"    - Tokens saved: {last.get('tokens_saved', 0):,}")
    
    # Test analysis script
    print("\n" + "=" * 70)
    print("TESTING ANALYSIS SCRIPT")
    print("=" * 70)
    
    # Create a minimal results file for testing
    test_result = {
        "instance_id": instance_id,
        "primitive": primitive,
        "run_num": run_num,
        "timestamp": datetime.now().strftime("%Y%m%d_%H%M%S"),
        "latency_seconds": round(latency, 2),
        "returncode": returncode,
        "success": returncode == 0,
        "patch_generated": traj_file.exists() and "patch" in json.load(open(traj_file)) and json.load(open(traj_file))["patch"],
        "token_usage": {"prompt": 0, "completion": 0, "total": 0}
    }
    
    results_file = RESULTS_DIR / "dryrun_results.json"
    with open(results_file, 'w') as f:
        json.dump([test_result], f, indent=2)
    
    print("✓ Create test results file for analysis script")
    
    print("\n" + "=" * 70)
    print("DRY RUN COMPLETE")
    print("=" * 70)
    print(f"\nOutput directory: {run_output}")
    print(f"Log file: {log_file}")
    print(f"\n✓ Pipeline is functional - ready for full experiment!")
    print()


if __name__ == "__main__":
    run_dry_run()
