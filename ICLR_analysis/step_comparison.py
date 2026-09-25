"""Agent-call changes on tasks solved by both policies (>=2/3 successes).
Successful attempts only, task means, paired bootstrap B=10,000 seed=210926.
"""
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
try:
    from .limit_rates import limit_inputs, MODELS
    from .plot_style import ORDER, pcol
except ImportError:
    from limit_rates import limit_inputs, MODELS
    from plot_style import ORDER, pcol


def step_inputs(swe,tb):
    _,runs=limit_inputs(swe,tb)
    runs['success']=runs.resolved.astype('string').str.lower().eq('true').fillna(False)
    runs['calls']=pd.to_numeric(runs.step_count,errors='coerce')
    assert runs.loc[runs.success,'calls'].notna().all()
    assert runs.loc[runs.success,'calls'].gt(0).all()
    rng=np.random.default_rng(210926)
    rows=[];paired=[]
    for (bench,model),g in runs.groupby(['benchmark','model'],sort=False):
        solved=g.groupby(['policy','task_name']).success.sum().ge(2).unstack('policy')
        means=g[g.success].groupby(['task_name','policy']).calls.mean().unstack('policy')
        for policy in ORDER:
            tasks=solved.index[solved[policy]&solved.FC]
            if len(tasks)==0:
                rows.append(dict(benchmark=bench,model=model,policy=policy,n_tasks=0,change=np.nan,lo=np.nan,hi=np.nan))
                continue
            v=means.loc[tasks,policy].to_numpy();base=means.loc[tasks,'FC'].to_numpy()
            idx=rng.integers(0,len(tasks),(10000,len(tasks)))
            boot=(v[idx].mean(axis=1)/base[idx].mean(axis=1)-1)*100
            lo,hi=np.percentile(boot,[2.5,97.5])
            rows.append(dict(benchmark=bench,model=model,policy=policy,n_tasks=len(tasks),
                             policy_calls=v.mean(),fc_calls=base.mean(),change=(v.mean()/base.mean()-1)*100,lo=lo,hi=hi))
            paired.extend(dict(benchmark=bench,model=model,policy=policy,task=task,policy_calls=a,fc_calls=b)
                          for task,a,b in zip(tasks,v,base))
    return pd.DataFrame(rows),pd.DataFrame(paired)


def fig_step_comparison(summary):
    fig,axes=plt.subplots(2,3,figsize=(8,6.1),sharex="row",sharey=True)
    low=min(-10,np.floor(summary.lo.min()/25)*25)
    high=max(25,np.ceil(summary.hi.max()/25)*25)
    for row,bench in enumerate(['SWE-bench','Terminal-Bench']):
        subset=summary[summary.benchmark.eq(bench)]
        low=min(-10,np.floor(subset.lo.min()/10)*10)
        high=max(25,np.ceil(subset.hi.max()/10)*10)
        for col,(_,model) in enumerate(MODELS):
            ax=axes[row,col]
            g=summary[summary.benchmark.eq(bench)&summary.model.eq(model)].set_index('policy').loc[ORDER]
            for i,(policy,r) in enumerate(g.iterrows()):
                if r.n_tasks:
                    ax.plot([r.lo,r.hi],[i,i],color=pcol(policy),lw=1.2)
                    ax.plot(r.change,i,'o',color=pcol(policy),ms=4)
                ax.text(1.02,i,str(int(r.n_tasks)),transform=ax.get_yaxis_transform(),va='center',fontsize=7,color='0.4')
            ax.text(1.02,1.015,'n',transform=ax.transAxes,fontsize=7,color='0.4')
            ax.axvline(0,color='0.4',ls='--',lw=.8)
            ax.set_yticks(range(len(ORDER)),ORDER,fontsize=8)
            ax.set_xlim(low,high)
            ax.set_title(model,fontweight='bold',fontsize=10,pad=8)
            ax.grid(axis='x',alpha=.16);ax.set_axisbelow(True)
            ax.spines[['top','right','left']].set_visible(False)
            ax.tick_params(axis='y',length=0)
            if row == 1:
                ax.set_xlabel('Change in agent calls vs. FC (%)',fontsize=8)
    axes[0,0].invert_yaxis()
    fig.subplots_adjust(left=.145,right=.95,top=.88,bottom=.13,hspace=.38,wspace=.25)
    fig.text(.145,.95,'SWE-bench',fontsize=11)
    fig.text(.145,.51,'Terminal-Bench',fontsize=11)
    fig.text(.55,.025,'Left of zero: fewer calls. Right of zero: more calls. Bars: 95% paired task-bootstrap intervals.\n'
             'Successful attempts on tasks solved in ≥2/3 runs by both policies; n = shared tasks.',ha='center',fontsize=7,color='0.25')
    return fig
