import json,pathlib,collections,re,csv
root=pathlib.Path('/home/ak58925/adaptive-context-management/agentCtx')
base=root/'data/r2/swebench/p30s/qwen35b'
out=root/'experiments/r2/audits/r2_p30s_run1_20260929'
out.mkdir(exist_ok=True)
rows=[]; errors=[]; summaries=[]; issues=[]; stats={}
regex=re.compile(r'```mswea_bash_command\s*\n(.*?)\n```',re.S)
for f in sorted(base.glob('*/experiment_results.json')):
 counts=collections.Counter(); finish=collections.Counter(); rejects=collections.Counter()
 results=json.loads(f.read_text())
 for r in results:
  p=f.parent/r['instance_id']/r['condition']/('run_'+str(r['run_num']))
  tok=json.loads((p/'token_log.json').read_text()); traj=json.loads((p/'trajectory.json').read_text()) if (p/'trajectory.json').exists() else {}
  events=[json.loads(s) for s in (p/'events.jsonl').read_text().splitlines()]
  comp=[json.loads(s) for s in (p/'compression_events.jsonl').read_text().splitlines()] if (p/'compression_events.jsonl').exists() else []
  row={k:r.get(k) for k in ['instance_id','condition','run_num','resolved','exit_status','returncode','n_calls','e2e_latency_s']};row['path']=str(p.relative_to(root))
  row.update(format_errors=0,reasoning_fallback=0,length_errors=0,compression_events=len(comp),summary_fallback=tok.get('summary_fallback_events',0),non_diff=bool(r.get('submission','').strip()) and not r['submission'].lstrip().startswith('diff --git'))
  commands=[]
  for e in events:
   m=e['message'];ex=m.get('extra',{});resp=ex.get('response',{});ch=(resp.get('choices') or [{}])[0];raw=ch.get('message') or {};reason=raw.get('reasoning_content') or '';content=raw.get('content') or ''
   if ex.get('interrupt_type')=='FormatError':
    row['format_errors']+=1;fr=ch.get('finish_reason');finish[fr]+=1
    row['length_errors']+=fr=='length'
    errors.append(dict(path=row['path'],step=e['step'],finish=fr,completion=resp.get('usage',{}).get('completion_tokens'),content_len=len(content),reasoning_len=len(reason),reasoning_actions=len(regex.findall(reason)),content_actions=len(regex.findall(content)),content_head=content[:180],reasoning_head=reason[:180]))
   if ex.get('action_source')=='reasoning_content':
    row['reasoning_fallback']+=1
    if not(ch.get('finish_reason')=='stop' and not content.strip() and len(regex.findall(reason))==1 and m['content']==reason):issues.append((row['path'],'fallback invariant'))
   commands += [a['command'] for a in ex.get('actions',[]) if 'command' in a]
  common=collections.Counter(commands).most_common(1)
  row['max_repeat']=common[0][1] if common else 0;row['repeated_command']=common[0][0] if common else '';row['last_command']=commands[-1] if commands else ''
  for c in comp:
   so=c.get('summary_outcome') or {}
   if so:
    rejects.update(so.get('rejections',[]))
    for a in c['added']:
     text=a['message']['content'];body=text.replace('[COMPRESSED HISTORY SUMMARY]','').replace('[END SUMMARY]','').strip()
     summaries.append(dict(path=row['path'],step=c['step'],chars=len(body),text=body,flags=so.get('flags'),latency=c.get('summary_latency_s')))
   if c['tokens_after']>c['budget'] or c['tokens_after']>=c['tokens_before']:issues.append((row['path'],'compression no reduction or over budget',c['step'],c['tokens_before'],c['tokens_after']))
   if c['primitive']!=r['primitive'] or c.get('picked') is not None:issues.append((row['path'],'wrong primitive'))
  records=tok.get('model_call_records',[])
  row['call_records']=len(records);row['calls_error']=sum(x['status']=='error' for x in records)
  row['summary_seconds']=tok.get('summarization_latency_s',0)
  row['max_tokens']=traj.get('info',{}).get('config',{}).get('model',{}).get('model_kwargs',{}).get('max_tokens')
  if len(records)!=r['n_calls']:issues.append((row['path'],'n_calls mismatch',len(records),r['n_calls']))
  for k in ['format_errors','reasoning_fallback','length_errors','compression_events','summary_fallback','non_diff','calls_error']: counts[k]+=row[k]
  counts['runs']+=1;counts['resolved']+=r['resolved'] is True;counts['unscored']+=r['resolved'] is None;counts['calls']+=r['n_calls'];counts['timeout']+=r['returncode']==-1;counts['step_limit']+=r['exit_status']=='LimitsExceeded';counts['summary_seconds']+=row['summary_seconds'];counts['fallback_runs']+=row['summary_fallback']>0
  rows.append(row)
 stats[f.parent.name]=dict(counts)|{'finish_reasons':dict(finish),'summary_rejections':dict(rejects)}
(out/'summary.json').write_text(json.dumps({'stats':stats,'issues':issues},indent=2))
(out/'errors.json').write_text(json.dumps(errors,indent=2))
(out/'summaries.json').write_text(json.dumps(summaries,indent=2))
with (out/'runs.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
print(json.dumps(stats,indent=2));print('ISSUES',issues)
print('TIMEOUTS',json.dumps([r for r in rows if not r['exit_status']],indent=2))
print('NONDIFF',json.dumps([r for r in rows if r['non_diff']],indent=2))
print('TOP REPEATS',json.dumps(sorted(rows,key=lambda r:r['max_repeat'],reverse=True)[:5],indent=2))
print('SHORT SUMMARIES',json.dumps(sorted(summaries,key=lambda s:s['chars'])[:8],indent=2))
print('CONFIG',collections.Counter(r['max_tokens'] for r in rows))
