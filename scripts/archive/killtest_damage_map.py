#!/usr/bin/env python3
"""Kill test, output 1 — the damage map.

Measures post-deletion KV-cache deviation as a function of distance from the
cut, per layer, on real TRC compression events. This is measurement only:
no healing, no splicing, no repair. See exp_plans/KILL_TEST_ONEPAGER.md and
exp_plans/HEALING_V1.md ("What the kill test must now answer", output 1).

Phases
------
extract  Replay full-context (no-compression) trajectories from p100-inf,
         fire the real budget trigger (memory.count_tokens > budget), apply
         the real primitive (memory.tool_result_clear at depth 0.5), and
         save (pre_edit_messages, post_edit_messages, edit metadata) events.
extract  needs no GPU.

measure  For each event: tokenize pre/post contexts per-message (Qwen chat
         format), prefill both with a HF model, de-rotate cached keys to the
         position-free basis, and record per-layer per-token relative
         deviation of K and V on retained tokens, plus each token's distance
         from the nearest preceding cut.

         Basis note: comparing keys de-rotated to position 0 is exactly
         equivalent to comparing (delta-re-rotated naive keys) vs (exact
         keys) at the new positions — RoPE rotations are orthonormal, so
         the L2 difference is identical. This lets the map skip splice code.

plot     Aggregate events into the damage map: deviation vs distance bins,
         per layer. The map picks healing mode S vs mode D (HEALING_V1.md).

Usage
-----
  python scripts/killtest_damage_map.py extract --budget 15000
  python scripts/killtest_damage_map.py measure --model Qwen/Qwen2.5-Coder-7B-Instruct --device cuda
  python scripts/killtest_damage_map.py plot
"""

import argparse
import glob
import json
import math
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

RESULTS_DIR = REPO / "results" / "killtest"

# ── extract ────────────────────────────────────────────────────────────────────


def phase_extract(args):
    import memory

    traj_glob = str(REPO / "results/ablations/p100-inf/*/full-context/run_*/trajectory.json")
    paths = sorted(glob.glob(traj_glob))
    if args.max_tasks:
        # one event per trajectory; cap by trajectory count
        paths = paths[: args.max_tasks]
    print(f"[extract] {len(paths)} full-context trajectories, budget={args.budget}")

    events = []
    for p in paths:
        try:
            d = json.load(open(p))
        except Exception as e:
            print(f"  skip {p}: {e}")
            continue
        msgs = d["messages"]
        task = Path(p).parents[2].name
        run = Path(p).parent.name

        # Replay the harness trigger: before each model call (messages end
        # with a user turn), compression fires iff count > budget.
        event = None
        for L in range(memory.N_PROTECTED + 1, len(msgs) + 1):
            if msgs[L - 1].get("role") != "user":
                continue
            pre = msgs[:L]
            current = memory.count_tokens(pre)
            if current <= args.budget:
                continue
            target = max(1, int(current * args.depth))
            post, saved, fallback = memory.tool_result_clear(
                [dict(m) for m in pre], target
            )
            cleared = [
                i
                for i in range(len(post))
                if post[i].get("content") != pre[i].get("content")
            ] if len(post) == len(pre) else None  # None => fallback dropped msgs
            event = {
                "task": task,
                "run": run,
                "source": p,
                "budget": args.budget,
                "depth": args.depth,
                "fire_step": (L - memory.N_PROTECTED) // 2,
                "tokens_pre": current,
                "tokens_post": memory.count_tokens(post),
                "tokens_saved": saved,
                "used_fallback": fallback,
                "cleared_msg_indices": cleared,
                "pre_messages": pre,
                "post_messages": post,
            }
            break
        if event is None:
            continue
        events.append(event)
        fb = " FALLBACK" if event["used_fallback"] else ""
        nspans = len(event["cleared_msg_indices"] or [])
        print(
            f"  {task}/{run}: fired step {event['fire_step']}, "
            f"{event['tokens_pre']} -> {event['tokens_post']} tok, "
            f"{nspans} spans cleared{fb}"
        )

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out = RESULTS_DIR / f"events_b{args.budget}_d{int(args.depth*100):03d}.json"
    json.dump(events, open(out, "w"))
    n_fb = sum(1 for e in events if e["used_fallback"])
    print(f"[extract] {len(events)} events -> {out} ({n_fb} used truncate fallback)")


# ── measure ────────────────────────────────────────────────────────────────────

CHUNK_TMPL = "<|im_start|>{role}\n{content}<|im_end|>\n"
GEN_PROMPT = "<|im_start|>assistant\n"


def _tokenize_messages(tok, messages):
    """Per-message token chunks in Qwen chat format. Returns (ids, spans)."""
    ids, spans = [], []
    for m in messages:
        content = m.get("content") or ""
        if isinstance(content, list):
            content = " ".join(
                str(b.get("text", "")) for b in content if isinstance(b, dict)
            )
        chunk = tok.encode(
            CHUNK_TMPL.format(role=m["role"], content=content),
            add_special_tokens=False,
        )
        spans.append((len(ids), len(ids) + len(chunk)))
        ids.extend(chunk)
    tail = tok.encode(GEN_PROMPT, add_special_tokens=False)
    spans.append((len(ids), len(ids) + len(tail)))
    ids.extend(tail)
    return ids, spans


def _get_layer_kv(cache, n_layers):
    """Return [(K, V)] per layer from a HF cache object, across versions."""
    if hasattr(cache, "key_cache"):
        return [(cache.key_cache[i], cache.value_cache[i]) for i in range(n_layers)]
    if hasattr(cache, "layers"):
        return [(cache.layers[i].keys, cache.layers[i].values) for i in range(n_layers)]
    return [(cache[i][0], cache[i][1]) for i in range(n_layers)]


def _derotate(K, torch, inv_freq):
    """Rotate cached post-RoPE keys back to position 0 (position-free basis).

    K: (1, kv_heads, T, head_dim). Standard neox-style RoPE (Qwen/Llama).
    """
    T = K.shape[2]
    pos = torch.arange(T, device=K.device, dtype=torch.float32)
    angles = torch.outer(pos, inv_freq.to(K.device).float())  # (T, hd/2)
    cos = torch.cat([angles.cos(), angles.cos()], dim=-1)[None, None]  # (1,1,T,hd)
    sin = torch.cat([angles.sin(), angles.sin()], dim=-1)[None, None]
    Kf = K.float()
    half = Kf.shape[-1] // 2
    rot = torch.cat([-Kf[..., half:], Kf[..., :half]], dim=-1)  # rotate_half
    return Kf * cos - rot * sin  # R(-theta) applied to post-RoPE keys


def phase_measure(args):
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    events_file = args.events or sorted(glob.glob(str(RESULTS_DIR / "events_*.json")))[-1]
    events = json.load(open(events_file))
    if args.skip_fallback:
        events = [e for e in events if not e["used_fallback"]]
    if args.max_events:
        events = events[: args.max_events]
    print(f"[measure] {len(events)} events from {events_file}")
    print(f"[measure] model={args.model} device={args.device}")

    dtype = torch.float16 if args.device == "cuda" else torch.float32
    tok = AutoTokenizer.from_pretrained(args.model)
    model = AutoModelForCausalLM.from_pretrained(args.model, torch_dtype=dtype)
    model = model.to(args.device)
    model.eval()
    cfg = model.config
    n_layers = cfg.num_hidden_layers
    head_dim = getattr(cfg, "head_dim", cfg.hidden_size // cfg.num_attention_heads)
    inv_freq = 1.0 / (
        cfg.rope_theta
        ** (torch.arange(0, head_dim, 2, dtype=torch.float32) / head_dim)
    )

    model_tag = args.model.split("/")[-1].lower().replace("-instruct", "")
    out_dir = RESULTS_DIR / f"deviation_{model_tag}"
    out_dir.mkdir(parents=True, exist_ok=True)

    @torch.no_grad()
    def prefill_kv(ids):
        input_ids = torch.tensor([ids], device=model.device)
        out = model(input_ids, use_cache=True)
        kv = _get_layer_kv(out.past_key_values, n_layers)
        return [(k.cpu(), v.cpu()) for k, v in kv]

    import numpy as np

    for ei, ev in enumerate(events):
        name = f"{ev['task']}_{ev['run']}_b{ev['budget']}"
        out_path = out_dir / f"{name}.npz"
        if out_path.exists() and not args.overwrite:
            print(f"  [{ei+1}/{len(events)}] {name}: exists, skip")
            continue
        pre_ids, pre_spans = _tokenize_messages(tok, ev["pre_messages"])
        post_ids, post_spans = _tokenize_messages(tok, ev["post_messages"])
        if len(pre_ids) > args.max_tokens or ev["cleared_msg_indices"] is None:
            print(f"  [{ei+1}/{len(events)}] {name}: skip (len/fallback)")
            continue

        cleared = set(ev["cleared_msg_indices"])
        # Alignment map: retained (unchanged) messages have identical chunks.
        pairs, edit_ends, dists, control = [], [], [], []
        for mi in range(len(ev["post_messages"])):
            ps, pe = post_spans[mi]
            qs, qe = pre_spans[mi]
            if mi in cleared:
                edit_ends.append(pe)  # stub span end, post coords
                continue
            assert (pe - ps) == (qe - qs), f"span mismatch msg {mi}"
            for off in range(pe - ps):
                pairs.append((qs + off, ps + off))
        # generation-prompt tail is retained too
        ps, pe = post_spans[-1]
        qs, qe = pre_spans[-1]
        for off in range(pe - ps):
            pairs.append((qs + off, ps + off))

        for _, p in pairs:
            prev_ends = [e for e in edit_ends if e <= p]
            dists.append(p - prev_ends[-1] if prev_ends else -1)

        pre_kv = prefill_kv(pre_ids)
        post_kv = prefill_kv(post_ids)

        pre_idx = torch.tensor([a for a, _ in pairs])
        post_idx = torch.tensor([b for _, b in pairs])
        devk = np.zeros((n_layers, len(pairs)), dtype=np.float32)
        devv = np.zeros((n_layers, len(pairs)), dtype=np.float32)
        for l in range(n_layers):
            k_pre0 = _derotate(pre_kv[l][0], torch, inv_freq)[0, :, pre_idx]
            k_post0 = _derotate(post_kv[l][0], torch, inv_freq)[0, :, post_idx]
            v_pre = pre_kv[l][1].float()[0, :, pre_idx]
            v_post = post_kv[l][1].float()[0, :, post_idx]
            # (kv_heads, T, hd) -> per-token rel L2 over heads*dim
            dk = (k_pre0 - k_post0).norm(dim=(0, 2)) / (k_post0.norm(dim=(0, 2)) + 1e-6)
            dv = (v_pre - v_post).norm(dim=(0, 2)) / (v_post.norm(dim=(0, 2)) + 1e-6)
            devk[l] = dk.numpy()
            devv[l] = dv.numpy()
        np.savez_compressed(
            out_path,
            devk=devk,
            devv=devv,
            dist=np.array(dists, dtype=np.int32),
            meta=json.dumps(
                {k: ev[k] for k in ("task", "run", "budget", "depth", "fire_step",
                                    "tokens_pre", "tokens_post")}
            ),
        )
        after = np.array(dists) >= 0
        print(
            f"  [{ei+1}/{len(events)}] {name}: {len(pre_ids)}->{len(post_ids)} tok, "
            f"{len(pairs)} retained ({int(after.sum())} after cut), "
            f"after-cut medK(last)={float(np.median(devk[-1][after])):.4f}, "
            f"ctrl medK(last)={float(np.median(devk[-1][~after])):.2e}"
        )


# ── plot ───────────────────────────────────────────────────────────────────────

DIST_BINS = [1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1024, 2048, 4096, 8192]


def phase_plot(args):
    import numpy as np
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    dev_dirs = sorted(glob.glob(str(RESULTS_DIR / "deviation_*")))
    dev_dir = args.dev_dir or (dev_dirs[-1] if dev_dirs else "")
    files = sorted(glob.glob(str(Path(dev_dir) / "*.npz")))
    print(f"[plot] {len(files)} event files from {dev_dir}")
    if not files:
        sys.exit("no deviation files; run measure first")

    all_k, all_v, all_d = [], [], []
    for f in files:
        z = np.load(f, allow_pickle=True)
        all_k.append(z["devk"])
        all_v.append(z["devv"])
        all_d.append(z["dist"])
    n_layers = all_k[0].shape[0]
    K = np.concatenate(all_k, axis=1)
    V = np.concatenate(all_v, axis=1)
    D = np.concatenate(all_d)

    bins = DIST_BINS
    heat = np.full((n_layers, len(bins)), np.nan)
    for bi, b in enumerate(bins):
        lo = bins[bi - 1] if bi else 0
        m = (D > lo) & (D <= b)
        if m.sum() < 20:
            continue
        heat[:, bi] = np.median(K[:, m], axis=1)
    ctrl = D == -1
    ctrl_k = np.median(K[:, ctrl], axis=1) if ctrl.sum() else None

    fig, axes = plt.subplots(1, 2, figsize=(13, 4.5))
    im = axes[0].imshow(heat, aspect="auto", origin="lower", cmap="viridis")
    axes[0].set_xticks(range(len(bins)))
    axes[0].set_xticklabels(bins, rotation=45, fontsize=7)
    axes[0].set_xlabel("distance from cut (tokens, bin upper edge)")
    axes[0].set_ylabel("layer")
    axes[0].set_title("median rel. K deviation (position-free basis)")
    fig.colorbar(im, ax=axes[0])

    sel = [0, n_layers // 2, n_layers - 1]
    centers = [math.sqrt((bins[i - 1] if i else 0.5) * b) for i, b in enumerate(bins)]
    for l in sel:
        axes[1].plot(centers, heat[l], marker="o", ms=3, label=f"K layer {l}")
    vline = np.full(len(bins), np.nan)
    for bi, b in enumerate(bins):
        lo = bins[bi - 1] if bi else 0
        m = (D > lo) & (D <= b)
        if m.sum() >= 20:
            vline[bi] = np.median(V[n_layers // 2, m])
    axes[1].plot(centers, vline, "k--", label=f"V layer {n_layers//2}")
    if ctrl_k is not None:
        axes[1].axhline(
            float(np.median(ctrl_k)), color="gray", lw=0.8, ls=":",
            label="control (before first cut)",
        )
    axes[1].set_xscale("log")
    axes[1].set_yscale("log")
    axes[1].set_xlabel("distance from cut (tokens)")
    axes[1].set_ylabel("median rel. deviation")
    axes[1].legend(fontsize=8)
    axes[1].set_title(f"damage map — {len(files)} events, {D.size} tokens")

    figdir = RESULTS_DIR / "figs"
    figdir.mkdir(parents=True, exist_ok=True)
    tag = args.fig_tag or Path(dev_dir).name.replace("deviation_", "")
    out = figdir / f"damage_map_{tag}.png"
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    print(f"[plot] -> {out}")
    if ctrl_k is not None:
        print(f"[plot] control median K dev (should be ~0): {float(np.median(ctrl_k)):.5f}")


# ── main ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="phase", required=True)

    ax = sub.add_parser("extract")
    ax.add_argument("--budget", type=int, default=15000)
    ax.add_argument("--depth", type=float, default=0.5)
    ax.add_argument("--max-tasks", type=int, default=0)

    am = sub.add_parser("measure")
    am.add_argument("--events", default="")
    am.add_argument("--model", default="Qwen/Qwen2.5-Coder-7B-Instruct")
    am.add_argument("--device", default="cuda")
    am.add_argument("--max-events", type=int, default=0)
    am.add_argument("--max-tokens", type=int, default=32768)
    am.add_argument("--skip-fallback", action="store_true", default=True)
    am.add_argument("--overwrite", action="store_true")

    apl = sub.add_parser("plot")
    apl.add_argument("--dev-dir", default="")
    apl.add_argument("--fig-tag", default="")

    args = ap.parse_args()
    {"extract": phase_extract, "measure": phase_measure, "plot": phase_plot}[args.phase](args)
