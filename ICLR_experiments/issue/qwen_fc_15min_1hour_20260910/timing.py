import json,collections,re,sys,statistics as st
from pathlib import Path
SP=Path(sys.argv[1]); tasks=set((SP/'tasks55.txt').read_text().split())
root=Path('ICLR_experiments/swebench/main/qwen35b/di__binf__fc')
d=[r for r in json.load(open(root/'experiment_results.json')) if r['instance_id'] in tasks]
def fm(r):
    if r['resolved'] is True: return 'resolved'
    s=r['exit_status'] or ''
    if s.startswith('LimitsExceeded'): return 'limits_exceeded'
    if r['patch_generated'] and s=='Submitted': return 'submitted_unresolved'
    if not r['patch_generated']: return 'silent_crash'
    return 'other'
agg=collections.defaultdict(list)
print(f"{'task':36s} run mode                 dur   llm_s  tool_s maxtool nsteps fmt_err len_stop think_leak")
for r in d:
    p=root/r['instance_id']/'full-context'/f"run_{r['run_num']}"
    t=json.load(open(p/'trajectory.json')); m=t['messages']
    ts=[];llm=[];tool=[];fmt=0;lenstop=0;think=0;prev=None
    for x in m:
        ex=x.get('extra') or {}
        if x['role']=='assistant':
            resp=ex.get('response') or {}
            fr=(resp.get('choices') or [{}])[0].get('finish_reason')
            if fr=='length': lenstop+=1
            if '</think>' in str(x['content']): think+=1
            if ex.get('timestamp'):
                if prev is not None: llm.append(ex['timestamp']-prev)
                prev=ex['timestamp']; ts.append(prev)
        elif x['role']=='user':
            if 'Expected exactly 1 action, found 0' in str(x['content']): fmt+=1
            if ex.get('timestamp'):
                if prev is not None: tool.append(ex['timestamp']-prev)
                prev=ex['timestamp']; ts.append(prev)
    dur=(ts[-1]-ts[0]) if len(ts)>1 else 0
    mode=fm(r)
    agg[mode].append((dur,sum(llm),sum(tool),fmt,lenstop,think,len(llm)))
    if mode in('silent_crash','limits_exceeded'):
        print(f"{r['instance_id']:36s} r{r['run_num']} {mode:20s} {dur:6.0f} {sum(llm):7.0f} {sum(tool):7.0f} {max(tool) if tool else 0:7.0f} {len(llm):5d} {fmt:6d} {lenstop:7d} {think:6d}")
print()
for mode,v in agg.items():
    n=len(v)
    print(f"{mode:22s} n={n:3d} mean_dur={st.mean(x[0] for x in v):6.0f} mean_llm={st.mean(x[1] for x in v):6.0f} mean_tool={st.mean(x[2] for x in v):6.0f} mean_steps={st.mean(x[6] for x in v):5.1f} s/step_llm={sum(x[1] for x in v)/max(1,sum(x[6] for x in v)):5.1f} s/step_tool={sum(x[2] for x in v)/max(1,sum(x[6] for x in v)):5.1f} fmt_err_runs={sum(1 for x in v if x[3]>0)} fmt_err_total={sum(x[3] for x in v)} len_stop_total={sum(x[4] for x in v)} think_leak_total={sum(x[5] for x in v)}")
