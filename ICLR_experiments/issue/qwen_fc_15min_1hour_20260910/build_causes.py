import json,re,csv,collections,glob,sys,datetime as dt
from pathlib import Path
SP=Path(sys.argv[1]); tasks=set((SP/'tasks55.txt').read_text().split())
root=Path('ICLR_experiments/swebench/main/qwen35b/di__binf__fc')
d=[r for r in json.load(open(root/'experiment_results.json')) if r['instance_id'] in tasks]
prov={p['key']:p['source'] for p in json.load(open(root/'ICLR_CELL_MANIFEST.json'))['provenance']}
FALSE_NEG={'django__django-13012__full-context__r2','scikit-learn__scikit-learn-10908__full-context__r1','scikit-learn__scikit-learn-11578__full-context__r2','scikit-learn__scikit-learn-12682__full-context__r1','scikit-learn__scikit-learn-15100__full-context__r2','scikit-learn__scikit-learn-26323__full-context__r2','sympy__sympy-24443__full-context__r2'}
INFRA={'scikit-learn__scikit-learn-14710__full-context__r1','scikit-learn__scikit-learn-14710__full-context__r3'}
NOEVID={'django__django-13012__full-context__r1','scikit-learn__scikit-learn-15100__full-context__r1','sympy__sympy-24443__full-context__r1','sympy__sympy-13798__full-context__r2'}
NOREPORT_UNRES={'scikit-learn__scikit-learn-14087__full-context__r1','scikit-learn__scikit-learn-25747__full-context__r1','scikit-learn__scikit-learn-12973__full-context__r1','scikit-learn__scikit-learn-12973__full-context__r2','scikit-learn__scikit-learn-13124__full-context__r2','sympy__sympy-13647__full-context__r1','sympy__sympy-13798__full-context__r1'}
MISMATCH={'django__django-11734__full-context__r2','sympy__sympy-12419__full-context__r1'}
diag={}
if (SP/'diagnoses.tsv').exists():
    for line in (SP/'diagnoses.tsv').read_text().splitlines():
        p=line.split('\t'); 
        if len(p)>=4: diag[p[0]]=(p[1],p[2],p[3])
def cmds(msgs):
    out=[]
    for m in msgs:
        if m['role']=='assistant':
            mm=re.search(r"```mswea_bash_command\n(.*?)```",str(m['content']),re.S); out.append(mm.group(1).strip() if mm else '')
    return out
rows=[]
for r in sorted(d,key=lambda r:(r['instance_id'],r['run_num'])):
    key=r['key']; p=root/r['instance_id']/'full-context'/f"run_{r['run_num']}"
    t=json.load(open(p/'trajectory.json')); m=t['messages']
    ts=[x['extra']['timestamp'] for x in m if (x.get('extra') or {}).get('timestamp')]
    dur=ts[-1]-ts[0]; fmt=sum('Expected exactly 1 action, found 0' in str(x['content']) for x in m if x['role']=='user')
    c=cmds(m); rep=max(collections.Counter(c[-40:]).values()) if c else 0
    batch=r['timestamp'][:10]
    row=dict(task=r['instance_id'],run=r['run_num'],batch_date=batch,steps=r['n_calls'],e2e_s=r['e2e_latency_s'],llm_s=r['llm_latency_s'],format_errors=fmt,final_prompt_tokens=(r['step_prompt_tokens'] or [0])[-1])
    if r['resolved'] is True:
        row.update(outcome='resolved',cause='resolved',detail='')
    elif (r['exit_status'] or '').startswith('Limits'):
        row.update(outcome='limits_exceeded',cause='step_limit_loop' if rep>=20 else 'step_limit_wandering',detail=f'most repeated cmd in last 40 steps x{rep}: {collections.Counter(c[-40:]).most_common(1)[0][0][:90]}' if rep>=20 else f'{len(set(c[-40:]))} distinct cmds in last 40 steps, never submitted')
    elif not r['patch_generated']:
        hang=r['e2e_latency_s']-dur
        det=f'killed at 1500s after {r["n_calls"]} steps; last recorded step at {dur:.0f}s' + (f'; final LLM call in flight for ~{hang:.0f}s' if hang>120 else '')
        if key in MISMATCH: det+='; PROVENANCE MISMATCH: trajectory.json is from a 2026-04-16 rerun that Submitted a patch (never evaluated)'
        row.update(outcome='silent_crash',cause='harness_timeout_1500s'+('_inflight_hang' if hang>120 else ''),detail=det)
    else:
        if not r['submission'].lstrip().startswith('diff --git'):
            row.update(outcome='submitted_unresolved',cause='submission_not_a_diff',detail='final command printed a code excerpt (cat|grep/sed) instead of git diff; SWE-bench: "Only garbage was found in the patch input"')
        elif key in FALSE_NEG:
            row.update(outcome='submitted_unresolved',cause='eval_false_negative',detail='canonical eval errored/missing, but byte-identical patch is recorded resolved=True in other eval dirs -> needs result sync / re-eval')
        elif key in INFRA:
            row.update(outcome='submitted_unresolved',cause='eval_infra_error',detail='docker "container name already in use" -> never evaluated; needs re-eval')
        elif key in NOEVID:
            row.update(outcome='submitted_unresolved',cause='eval_evidence_missing',detail='no report/aggregate for this patch anywhere; resolved=False unverified; needs re-eval')
        else:
            dg=diag.get(key,('wrong_fix','',''))
            row.update(outcome='submitted_unresolved',cause='wrong_fix:'+dg[0],detail=(dg[2] or '')+('' if key not in NOREPORT_UNRES else ' [detailed report missing; aggregate says unresolved]'))
            row['failing_test']=dg[1]
    rows.append(row)
cols=['task','run','batch_date','outcome','cause','failing_test','detail','steps','e2e_s','llm_s','format_errors','final_prompt_tokens']
with open(SP/'fc_15min_1hour_causes.csv','w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=cols); w.writeheader(); [w.writerow({k:row.get(k,'') for k in cols}) for row in rows]
print(collections.Counter(r['cause'].split(':')[0] for r in rows))
print(collections.Counter(r['cause'] for r in rows if r['cause'].startswith('wrong_fix')))
