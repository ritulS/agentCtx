# agentCtx — SWE-bench Evaluation Project

## Goal
Run mini-swe-agent on SWE-bench_Verified tasks using a locally-served vLLM model, then evaluate patches with the SWE-bench harness.

---

## Environment
- **Machine**: UT Austin server, Ubuntu 22.04.5, x86_64
- **Working dir**: `/home/rs67788/Documents/agentCtx`
- **Project venv**: `/home/rs67788/Documents/agentCtx/venv` (Python 3.10, has vllm 0.16.0, mini-swe-agent)
- **SWE-bench venv**: `~/waf_experiment` (has swebench==4.1.0, datasets==4.6.1)
- **GPU**: NVIDIA RTX 4090 (24 GB VRAM)
- **Container runtime**: Podman (user-local, no sudo) via Docker SDK

---

## Model / vLLM Server
- **Model**: `Qwen/Qwen2.5-Coder-7B-Instruct`
- **Endpoint**: `http://localhost:8000/v1`
- **Config**: `mini-swe-agent/config-qwen-vllm.yaml`
- **Start server** (in screen session):
  ```bash
  source /home/rs67788/Documents/agentCtx/venv/bin/activate
  screen -dmS vllm-server bash -c "vllm serve Qwen/Qwen2.5-Coder-7B-Instruct --port 8000 --dtype auto --max-model-len 16384 2>&1 | tee logs/vllm-server.log"
  ```
- **Check server**: `curl -s http://localhost:8000/health`
- **Attach to session**: `screen -r vllm-server`
- **Log**: `logs/vllm-server.log`

---

## Tasks
| Instance ID | Repo | FAIL_TO_PASS | PASS_TO_PASS |
|---|---|---|---|
| `sympy__sympy-20590` | sympy | `test_immutable` | 21 |
| `psf__requests-6028` | requests | 2 tests in `test_utils.py::test_prepend_scheme_if_needed` | 185 |

---

## Running mini-swe-agent
```bash
source /home/rs67788/Documents/agentCtx/venv/bin/activate
cd /home/rs67788/Documents/agentCtx/mini-swe-agent
python -m mini_swe_agent.main --config config-qwen-vllm.yaml --instance_id <instance_id>
```

---

## Running SWE-bench Evaluation
```bash
source ~/waf_experiment/bin/activate
export DOCKER_HOST="unix:///run/user/$(id -u)/podman/podman.sock"
python -m swebench.harness.run_evaluation \
  --predictions_path <predictions.json> \
  --max_workers 1 \
  --instance_ids <instance_id> \
  --run_id <run_id>
```

---

## Key Patches / Known Issues
- **SWE-bench `copy_to_container` bug**: domain UID causes `lchown` EINVAL. Patched in `~/waf_experiment/lib/python3.10/site-packages/swebench/harness/docker_utils.py` to use `base64+exec_run` instead of `put_archive`.
- **Podman socket**: must be running. Auto-started by `~/.bashrc`. Manual: `podman system service --time=0 unix:///run/user/$(id -u)/podman/podman.sock &`
- **Validated**: Gold patch on `sympy__sympy-20590` → RESOLVED (report: `gold.validate-gold.json`)
