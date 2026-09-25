"""Main-setting termination rates, without resource/log availability filtering.

Time category reproduces the main resource exclusion rule. TB fallback is
shown separately because cancellation/missing status does not prove timeout.
Step-only excludes attempts already classified as time-capped/inferred.
"""
from pathlib import Path
import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
try:
    from .plot_style import ORDER
except ImportError:
    from plot_style import ORDER
ROOT=Path(__file__).resolve().parents[1]
POLICIES=['FC']+ORDER
NAMES=dict(zip(['fc','tr','trc','su-full','su-partial','ss','ss-partial','trc-su','trc-ss','otrc-tr','otrc-su-partial','otrc-ss-partial','otrc'],['FC','TR','TRC','SU','SU-p','SS','SS-p','TRC+SU','TRC+SS','OTRC+TR','OTRC+SU-p','OTRC+SS-p','OTRC']))
MODELS=[('qwen35b','Qwen'),('devstral24b','Devstral'),('glm47flash','GLM')]

def limit_inputs(swe,tb):
    parts=[]
    for benchmark,path,thresholds,taskfile,n in [
        ('SWE-bench',swe,[15000,21000,13000],'p100_all_100_tasks.json',100),
        ('Terminal-Bench',tb,[3000,4000,3000],'tbench_p40.json',40)]:
        tasks=json.loads((ROOT/'task_lists'/taskfile).read_text())
        if isinstance(tasks,dict):
            tasks=tasks.get('tasks',tasks.get('task_ids',tasks))
        tasks={x['instance_id'] if isinstance(x,dict) else x for x in tasks}
        assert len(tasks)==n
        d=pd.read_csv(path,low_memory=False)
        for (model,label),threshold in zip(MODELS,thresholds):
            g=d[d.experiment_section.eq('main')&d.model_key.eq(model)&d.task_name.isin(tasks)&d.run_num.isin([1,2,3])].copy()
            g['policy']=g.cell.str.split('__').str[-1].map(NAMES)
            g=g[g.token_budget.eq(threshold)|g.policy.isin(['FC','OTRC'])].copy()
            assert set(g.policy)==set(POLICIES)
            assert not g.duplicated(['policy','task_name','run_num']).any()
            assert g.groupby('policy').size().eq(n*3).all()
            assert g.groupby(['policy','task_name']).size().eq(3).all()
            if benchmark=='SWE-bench':
                g['time']=pd.to_numeric(g.latency_e2e_s).ge(1500)
                g['inferred']=False
                step_limit=125
            else:
                g['time']=g.harbor_exception.eq('AgentTimeoutError')
                g['inferred']=g.harbor_exception.isna()&(g.exit_status.isna()|g.exit_status.eq('CancelledError'))
                step_limit=100
            step=g.exit_status.eq('LimitsExceeded')
            assert pd.to_numeric(g.loc[step,'step_count']).eq(step_limit).all()
            g['step_recorded']=step
            g['step']=step&~(g.time|g.inferred)
            g['submitted_failed']=g.exit_status.eq('Submitted') & g.resolved.astype('string').str.lower().eq('false').fillna(False) & ~(g.time|g.inferred|g.step)
            g['benchmark']=benchmark;g['model']=label
            parts.append(g)
    runs=pd.concat(parts,ignore_index=True)
    runs['success']=runs.resolved.astype('string').str.lower().eq('true').fillna(False)
    runs['outcome']=np.select([runs.success, runs.time|runs.inferred, runs.step,
                               runs.submitted_failed],
                              ['resolved','timeout','step_limit','submitted_failure'],default='other')
    kinds=['resolved','timeout','step_limit','submitted_failure','other']
    groups=['benchmark','model','policy']
    counts=runs.groupby(groups+['outcome']).size().unstack(fill_value=0).reindex(columns=kinds,fill_value=0)
    summary=counts.reset_index()
    summary['attempts']=summary[kinds].sum(axis=1)
    for kind in kinds: summary[kind+'_pct']=100*summary[kind]/summary.attempts
    assert np.allclose(summary[[k+'_pct' for k in kinds]].sum(axis=1),100)
    # Keep resource-exclusion rates separate: successful runs can also be capped.
    audit=runs.assign(resource_excluded=runs.time|runs.inferred)
    extra=audit.groupby(groups).agg(resource_excluded_count=('resource_excluded','sum'),
                                   successful_excluded_count=('success',lambda v: int((v & audit.loc[v.index,'resource_excluded']).sum())),
                                   inferred_count=('inferred','sum')).reset_index()
    summary=summary.merge(extra,on=groups,validate='one_to_one')
    return summary,audit[['benchmark','model','policy','task_name','run_num','source_file','exit_status','step_count','latency_e2e_s','time','inferred','step_recorded','resolved','outcome','resource_excluded']]

def fig_limit_rates(summary):
    """Directly labeled, exhaustive outcome stacked bars on a shared scale."""
    fig,axes=plt.subplots(2,3,figsize=(8.0,6.3),sharex=True,sharey=True)
    categories=[('resolved','Resolved','#39836b'),('timeout','Unresolved: time limit*','#d97932'),
                ('step_limit','Unresolved: step limit','#397eaf'),
                ('submitted_failure','Submitted, failed evaluation','#99618b'),('other','Other / missing outcome','#c5c5c5')]
    for row,benchmark in enumerate(['SWE-bench','Terminal-Bench']):
        for col,(_,model) in enumerate(MODELS):
            ax=axes[row,col]
            g=summary[summary.benchmark.eq(benchmark)&summary.model.eq(model)].set_index('policy').loc[POLICIES]
            y=np.arange(len(g));left=np.zeros(len(g))
            for key,label,color in categories:
                values=g[key+'_pct'].to_numpy()
                ax.barh(y,values,left=left,height=.73,color=color)
                for i,v in enumerate(values):
                    if v>=9 or key=='resolved':
                        ax.text(left[i]+v/2,i,f'{v:.0f}',ha='center',va='center',fontsize=6.5,
                                color='0.2' if key=='other' else 'white')
                left+=values
            ax.set_title(model,fontsize=10,fontweight='bold',pad=8)
            ax.set_yticks(y,POLICIES,fontsize=8)
            ax.set_xlim(0,100);ax.set_xticks([0,25,50,75,100])
            ax.tick_params(axis='y',length=0)
            ax.grid(axis='x',alpha=.16);ax.set_axisbelow(True)
            ax.spines[['top','right','left']].set_visible(False)
            if row==1:ax.set_xlabel('Share of all attempts (%)',fontsize=8)
    axes[0,0].invert_yaxis()
    fig.subplots_adjust(left=.145,right=.98,top=.86,bottom=.13,hspace=.31,wspace=.18)
    fig.text(.145,.92,'SWE-bench · 300 attempts per policy and model',fontsize=10)
    fig.text(.145,.50,'Terminal-Bench · 120 attempts per policy and model',fontsize=10)
    fig.legend(handles=[Patch(facecolor=color,label=label) for _,label,color in categories],
               loc='upper center',bbox_to_anchor=(.55,1.005),ncol=3,frameon=False,fontsize=7.5)
    fig.text(.55,.025,'Each bar sums to 100%. Successful verdicts take priority over exit status.\n'
             '* Includes inferred Terminal-Bench timeouts. Segment labels are percentages.',
             ha='center',fontsize=7,color='0.25')
    return fig
