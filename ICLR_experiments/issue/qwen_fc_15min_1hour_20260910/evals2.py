import json,re,sys,collections,glob,os
from pathlib import Path
os.environ['HF_DATASETS_OFFLINE']='1'; os.environ['HF_HUB_OFFLINE']='1'
SP=Path(sys.argv[1]); tasks=set((SP/'tasks55.txt').read_text().split())
root=Path('ICLR_experiments/swebench/main/qwen35b/di__binf__fc')
d=[r for r in json.load(open(root/'experiment_results.json')) if r['instance_id'] in tasks]
prov={p['key']:p['source'] for p in json.load(open(root/'ICLR_CELL_MANIFEST.json'))['provenance']}
srcs={'p100-inf':[('data/swebench/ablations/p100-inf/eval','qwen35-a3b')],
      'qwen3.5-35B-A3B_15k_Fullrun':[('data/swebench/source_runs/qwen3.5-35B-A3B_15k_Fullrun/eval','qwen3.5-35B-A3B_15k_Fullrun'),('data/swebench/ablations/qwen3.5-35B-A3B_15k_Fullrun/eval','qwen3.5-35B-A3B_15k_Fullrun')]}
gold={}
try:
    from datasets import load_dataset
    ds=load_dataset('princeton-nlp/SWE-bench_Verified',split='test')
    for row in ds:
        if row['instance_id'] in tasks: gold[row['instance_id']]=sorted(set(re.findall(r'^diff --git a/(\S+)',row['patch'],re.M)))
    print('gold loaded for',len(gold))
except Exception as e: print('gold load failed:',e)
cat=collections.Counter(); rows=[]
for r in d:
    if r['resolved'] is not False or r['exit_status']!='Submitted' or not r['patch_generated']: continue
    key=r['key']; src=prov[key]; inst=r['instance_id']
    files=sorted(set(re.findall(r'^diff --git a/(\S+)',r['submission'],re.M)))
    is_diff=r['submission'].lstrip().startswith('diff --git')
    rep=None;top=None;ril=''
    for ed,tag in srcs[src]:
        p=Path(ed)/'logs/run_evaluation'/key/tag/inst/'report.json'
        if p.exists() and rep is None:
            rep=json.load(open(p))[inst]
            l=p.with_name('run_instance.log')
            if l.exists():
                txt=l.read_text(errors='ignore')
                m=re.search(r'(Patch Apply Failed|patch does not apply|error: .{0,100}|malformed patch.{0,80})',txt); ril=m.group(0) if m else ''
        t=Path(ed)/f'{tag}.{key}.json'
        if t.exists() and top is None:
            j=json.load(open(t)); top='resolved' if j.get('resolved_ids') else 'error' if j.get('error_ids') else 'unresolved' if j.get('unresolved_ids') else 'empty' if j.get('empty_patch_ids') else '?'
    g=gold.get(inst,[]); nontest=[f for f in files if not re.search(r'(^|/)tests?(/|_)|test_',f)]
    overlap='n/a' if not g else ('same' if set(nontest)==set(g) else 'superset' if set(g)<=set(nontest) else 'partial' if set(g)&set(nontest) else 'DIFFERENT')
    if not is_diff: c='not_a_diff'
    elif rep is None: c='no_report('+(top or 'no-top')+')'
    elif not rep.get('patch_successfully_applied'): c='patch_apply_failed'
    else:
        ts=rep['tests_status']; f2p=ts['FAIL_TO_PASS']; p2p=ts['PASS_TO_PASS']
        fs,ff,pf=len(f2p['success']),len(f2p['failure']),len(p2p['failure'])
        c='f2p_all_fail' if fs==0 else 'f2p_partial' if ff>0 else 'regression_only' if pf>0 else 'REPORT_SAYS_RESOLVED'
        c+=f' [F2P {fs}/{fs+ff}, P2P fail {pf}]'
    cat[c.split(' ')[0]]+=1
    print(f"{key:48s} top={str(top):10s} {c:40s} gold_overlap={overlap:9s} agent={nontest} gold={g}{' +TESTFILES' if len(files)>len(nontest) else ''}{('  RIL: '+ril) if ril else ''}")
print(cat)
