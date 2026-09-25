"""Summarizer sensitivity on pinned ABL-25; invoked by Iclr_plot_bank.py.

Success uses all attempts. Resource ratios use uncapped runs with >=2
prompt counts, task means, and tasks shared by all three summarizers.
Intervals: 5,000 task bootstrap samples, seed 0; paired for ratios/deltas.
"""
from pathlib import Path
import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
try:
    from .plot_style import pcol
except ImportError:
    from plot_style import pcol

ROOT = Path(__file__).resolve().parents[1]
MODELS = [('qwen35b', 'Self'), ('qwen35b-sum-qwen35-9b', 'Qwen3.5-9B'),
          ('qwen35b-sum-gemma4-12b', 'Gemma-4-12B')]
CELLS = {'d05__b15k__su-full': 'SU', 'di__b15k__trc-su': 'TRC+SU'}


def summarizer_inputs(outcomes):
    d = pd.read_csv(outcomes, low_memory=False)
    tasks = sorted(x['instance_id'] for x in json.loads((ROOT / 'task_lists/ablation_25tasks.json').read_text()))
    parts = []
    for model, label in MODELS:
        track = 'main' if label == 'Self' else 'model_ablation'
        g = d[d.model_key.eq(model) & d.experiment_section.eq(track) &
              d.task_name.isin(tasks) & d.cell.isin(CELLS) & d.run_num.isin([1, 2, 3])].copy()
        assert not g.duplicated(['cell', 'task_name', 'run_num']).any()
        for cell in CELLS:
            c = g[g.cell.eq(cell)]
            assert len(c) == 75 and set(c.task_name) == set(tasks)
            assert c.groupby('task_name').size().eq(3).all()
        g['summarizer'] = label
        parts.append(g)
    d = pd.concat(parts, ignore_index=True)
    d['policy'] = d.cell.map(CELLS)
    verdict = d.resolved.astype('string').str.lower()
    assert (verdict.isna() | verdict.isin(['true', 'false'])).all()
    d['success'] = verdict.eq('true').fillna(False).astype(float)
    d['usage'] = pd.to_numeric(d.total_prompt_tokens) + pd.to_numeric(d.total_completion_tokens)
    d['latency'] = pd.to_numeric(d.latency_e2e_s)
    d['prompt_calls'] = d.step_prompt_tokens.map(lambda x: len(json.loads(x)) if isinstance(x, str) else 0)
    d['eligible'] = d.latency.lt(1500) & d.latency.ge(0) & d.usage.ge(0) & d.prompt_calls.ge(2)
    rng = np.random.default_rng(0)
    rows = []
    for policy in CELLS.values():
        g = d[d.policy.eq(policy)]
        success = g.groupby(['task_name', 'summarizer']).success.mean().unstack().loc[tasks]
        eligible = g[g.eligible]
        common = sorted(set.intersection(*(set(eligible[eligible.summarizer.eq(label)].task_name) for _, label in MODELS)))
        assert common
        ix = rng.integers(0, len(tasks), (5000, len(tasks)))
        jx = rng.integers(0, len(common), (5000, len(common)))
        for _, label in MODELS:
            values = success[label].to_numpy()
            boots = values[ix].mean(axis=1) * 100
            diff = (values - success.Self.to_numpy())[ix].mean(axis=1) * 100
            row = dict(policy=policy, summarizer=label, attempts=75, tasks=25,
                       success=values.mean()*100, success_lo=np.percentile(boots, 2.5),
                       success_hi=np.percentile(boots, 97.5),
                       success_delta=(values-success.Self.to_numpy()).mean()*100,
                       delta_lo=np.percentile(diff,2.5), delta_hi=np.percentile(diff,97.5),
                       resource_tasks=len(common), eligible_runs=int((eligible.summarizer.eq(label)&eligible.task_name.isin(common)).sum()))
            for metric in ['usage', 'latency']:
                means = eligible.groupby(['task_name', 'summarizer'])[metric].mean().unstack().loc[common]
                v, base = means[label].to_numpy(), means.Self.to_numpy()
                ratios = v[jx].mean(axis=1)/base[jx].mean(axis=1)
                row[metric] = v.mean()/base.mean()
                row[metric+'_lo'],row[metric+'_hi'] = np.percentile(ratios,[2.5,97.5])
                row[metric+'_absolute'] = v.mean()
            rows.append(row)
    audit_cols=['policy','summarizer','task_name','run_num','source_file','success','usage','latency','prompt_calls','eligible']
    return pd.DataFrame(rows), d[audit_cols]


def fig_summarizer_ablation(summary):
    fig, axes = plt.subplots(1, 3, figsize=(7.0, 2.65))
    labels = [label for _, label in MODELS]
    for ax, metric, title, ylabel in zip(axes, ['success','usage','latency'],
            ['(a) Task success','(b) Token consumption','(c) End-to-end latency'],
            ['Resolve rate (%)','Tokens / self','Latency / self']):
        for policy, offset, marker in [('SU',-.1,'o'),('TRC+SU',.1,'s')]:
            g=summary[summary.policy.eq(policy)].set_index('summarizer').loc[labels]
            v=g[metric].to_numpy()
            ax.errorbar(np.arange(3)+offset,v,yerr=np.vstack([v-g[metric+'_lo'],g[metric+'_hi']-v]),
                        fmt=marker, color=pcol(policy), capsize=3, markersize=4, label=policy)
        ax.set_xticks(range(3),['Self','Qwen3.5\n9B','Gemma-4\n12B'])
        ax.set_xlim(-.4,2.4)
        ax.set_ylabel(ylabel)
        ax.set_title(title)
        ax.spines[['top','right']].set_visible(False)
        ax.grid(axis='y',alpha=.18)
        if metric=='success': ax.set_ylim(0,100)
        else: ax.axhline(1,color='0.5',ls='--',lw=.8)
    axes[0].legend(frameon=False,loc='upper left',ncol=2,handletextpad=.3,columnspacing=.7)
    fig.subplots_adjust(left=.075,right=.99,bottom=.23,top=.88,wspace=.48)
    return fig
