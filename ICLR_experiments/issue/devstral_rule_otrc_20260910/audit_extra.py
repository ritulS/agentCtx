import collections as C, csv, datetime as D, hashlib,json,re
from pathlib import Path
R=Path('/home/ak58925/agentCtx'); O=R/'ICLR_experiments/issue/devstral_rule_otrc_20260910'; B=R/'ICLR_experiments/swebench/main/devstral24b'; S=json.load(open(O/'summary.json'));cells=[s['cell'] for s in S['cells']]
A=[R/'archives'/x for x in ['swebench_summary_marker_error_20260907_192635_CDT','swebench_summary_bug_remaining_20260908_162042_CDT']]
def norm(t):
 c=t['info']['config'];c.get('agent',{}).pop('output_path',None);c.get('environment',{}).pop('image',None);return c
extra={'old_config_checked':0,'old_config_missing':[],'old_config_mismatch':[],'environment_image_mismatch':[],'coverage_issues':[],'eval_mismatch':[],'eval_missing_for_patch':[],'resolved_null':[],'runtime_params_mismatch':[]}
expected={r['instance_id'] for r in json.load(open(R/'task_lists/p100_all_100_tasks.json'))}
for cell in cells:
 rs=json.load(open(B/cell/'experiment_results.json'))
 if {(r['instance_id'],r['run_num']) for r in rs}!={(t,n) for t in expected for n in [1,2,3]}:extra['coverage_issues'].append(cell)
 evals={p.name.split('.',1)[1][:-5]:p for p in (B/cell/'eval').glob('*.json')}
 for r in rs:
  rel=Path('ICLR_experiments/swebench/main/devstral24b')/cell/r['instance_id']/r['condition']/f"run_{r['run_num']}"/'trajectory.json'
  t=json.load(open(R/rel));original=R/rel
  if r['timestamp']>='2026-09-09':original=next((a/rel for a in A if (a/rel).exists()),None)
  if original is None:extra['old_config_missing'].append((cell,r['key']))
  else:
   old=json.load(open(original));extra['old_config_checked']+=1
   if old['info']['config']['environment']['image']!=t['info']['config']['environment']['image']:extra['environment_image_mismatch'].append((cell,r['key']))
   if norm(old)!=norm(t):extra['old_config_mismatch'].append((cell,r['key']))
  if r.get('budget')!=(999999999 if 'binf' in cell else 21000) or r.get('compression_ratio')!=0.5:extra['runtime_params_mismatch'].append((cell,r['key']))
  ep=evals.get(r['key'])
  if r.get('resolved') is None:extra['resolved_null'].append((cell,r['key']))
  if ep:
   e=json.load(open(ep));resolved=r['instance_id'] in e.get('resolved_ids',[])
   if r.get('resolved')!=resolved:extra['eval_mismatch'].append((cell,r['key']))
  elif r.get('patch_generated'):extra['eval_missing_for_patch'].append((cell,r['key']))
 print(cell,'done',flush=True)
# Overlaps against available current and pre-archive Devstral records, deduplicated by timestamp.
all_records={}
for tree in [R]+[a/'before' for a in A]:
 for p in (tree/'ICLR_experiments/swebench').glob('*/devstral24b/*/experiment_results.json'):
  section=p.parts[-4];cell=p.parts[-2]
  for r in json.load(open(p)):
   if not r.get('timestamp') or not r.get('e2e_latency_s'):continue
   if r['timestamp']<'2026-08-31' or r['timestamp']>='2026-09-11':continue
   e=D.datetime.fromisoformat(r['timestamp']);b=e-D.timedelta(seconds=r['e2e_latency_s'])
   all_records[(section,cell,r['key'],r['timestamp'])]=(b,e)
extra['other_cell_overlaps']=[]
for s in S['cells']:
 for phase in ['original_all','rerun']:
  if phase+'_start' not in s: continue
  b=D.datetime.fromisoformat(s[phase+'_start']);e=D.datetime.fromisoformat(s[phase+'_end']);over=C.Counter()
  for (sect,cell,key,stamp),(rb,re_) in all_records.items():
   if sect=='main' and cell==s['cell']:continue
   if (min(e,re_)-max(b,rb)).total_seconds()>1:over[(sect,cell)]+=1
  if over:extra['other_cell_overlaps'].append({'cell':s['cell'],'phase':phase,'overlaps':{str(k):v for k,v in over.items()}})
# Maximum total running + waiting server requests; extrema of columns alone are not simultaneous.
metrics={s['cell']:[] for s in S['cells']}
pat=re.compile(r'INFO (\d\d-\d\d) (\d\d:\d\d:\d\d).*Running: (\d+) reqs, Waiting: (\d+) reqs')
for l in (R/'logs/vllm_devstral.log').read_text(errors='replace').splitlines():
 m=pat.search(l)
 if m:
  t=D.datetime.fromisoformat('2026-'+m[1]+'T'+m[2])
  for s in S['cells']:
   if 'rerun_start' not in s: continue
   if D.datetime.fromisoformat(s['rerun_start'])<=t<=D.datetime.fromisoformat(s['rerun_end']):metrics[s['cell']].append(int(m[3])+int(m[4]))
extra['max_running_plus_waiting']={c:max(v) for c,v in metrics.items() if v}
(O/'extra_checks.json').write_text(json.dumps(extra,indent=2));print({k:len(v) if isinstance(v,list) else v for k,v in extra.items()})
