import csv,json,collections as C,shutil
from pathlib import Path
R=Path('/home/ak58925/agentCtx');O=R/'ICLR_experiments/issue/devstral_rule_otrc_20260910';S=json.load(open(O/'summary.json'));rows=list(csv.DictReader(open(O/'evaluation_checks.csv')))
classified=[];targets=[];counts=C.Counter()
for r in rows:
 b=R/'ICLR_experiments/swebench/main/devstral24b'/r['cell'];key=r['key'];entry=next(x for x in json.load(open(b/'experiment_results.json')) if x['key']==key)
 log=b/'eval/logs/run_evaluation'/key/'devstral-2'/entry['instance_id']/'run_instance.log'
 action='keep';reason='fresh_report_matching_patch'
 if r['report_exists']=='False':
  logtext=log.read_text(errors='replace') if log.exists() else ''
  if r['patch_matches']=='True' and 'Patch Apply Failed' in logtext:reason='current_patch_apply_failure'
  elif 'invalid state' in logtext and '409' in logtext:action='evaluate_only';reason='evaluation_container_image_conflict'
  elif not r['resolved']:action='evaluate_only';reason='evaluation_timeout'
  else:action='evaluate_only';reason='evaluation_report_missing'
 elif r['patch_matches']=='False':action='evaluate_only';reason='stale_report_different_patch'
 elif r['report_after_attempt']=='False':reason='old_report_identical_patch_optional_refresh'
 row={**r,'task':entry['instance_id'],'run_num':entry['run_num'],'action':action,'reason':reason,'result_file':str((b/'experiment_results.json').relative_to(R)),'prediction_file':str((b/'preds'/f'preds_{key}.json').relative_to(R)),'evaluation_log_dir':str(log.parent.relative_to(R))}
 classified.append(row);counts[(r['cell'],reason)]+=1
 if action=='evaluate_only':targets.append(row)
for name,rs in [('evaluation_classification.csv',classified),('reevaluation_candidates.csv',targets)]:
 with (O/name).open('w') as f:w=csv.DictWriter(f,fieldnames=list(rs[0]));w.writeheader();w.writerows(rs)

print('targets',len(targets),'by cell',dict(C.Counter(r['cell'] for r in targets)))
print('classifications',dict(C.Counter(r['reason'] for r in classified)))
