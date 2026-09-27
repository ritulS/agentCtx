import collections as C
import csv, datetime as D, hashlib, importlib.util, json, re, sys
from pathlib import Path

ROOT = Path('/home/ak58925/agentCtx')
OUT = ROOT / 'ICLR_experiments/issue/devstral_summary_20260910'
OUT.mkdir(parents=True, exist_ok=True)
CELLS = ['d05__b21k__su-full','d05__b21k__su-partial','d05__b21k__ss','d05__b21k__ss-partial','di__b21k__trc-su','di__b21k__trc-ss']
BASE = ROOT / 'ICLR_experiments/swebench/main/devstral24b'
ARCHIVES = [ROOT/'archives'/x for x in ['swebench_summary_marker_error_20260907_192635_CDT','swebench_summary_bug_remaining_20260908_162042_CDT']]
spec = importlib.util.spec_from_file_location('attrib',ROOT/'archives/summary_bug_rerun_tooling_20260907_175359_CDT/scripts/attribute_agentlog.py')
attrib = importlib.util.module_from_spec(spec); spec.loader.exec_module(attrib)
def read(p): return json.loads(p.read_text())
def digest(v): return hashlib.sha256(json.dumps(v,sort_keys=True).encode()).hexdigest()
def write_csv(name, rows):
    if not rows: return
    fields=list(dict.fromkeys(k for r in rows for k in r))
    with (OUT/name).open('w') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
def interval(r):
    end=D.datetime.fromisoformat(r['timestamp']);return end-D.timedelta(seconds=r['e2e_latency_s']),end
def peak(rs):
    events=[]
    for r in rs:
        b,e=interval(r)
        if (e-b).total_seconds()>2: events.extend([(b+D.timedelta(seconds=1),1),(e,-1)])
    n=m=0
    for _,v in sorted(events):n+=v;m=max(m,n)
    return m
def normalized_config(t):
    c=json.loads(json.dumps(t['info']['config']))
    c.get('agent',{}).pop('output_path',None)
    c.get('environment',{}).pop('image',None)
    return c

before_hash={c:hashlib.sha256((BASE/c/'experiment_results.json').read_bytes()).hexdigest() for c in CELLS}
prior={}
with (ROOT/'archives/summary-bug-audit-20260907_185802_CDT/agentlog-swebench-allconditions/agentlog_attribution.csv').open() as f:
    for r in csv.DictReader(f):
        if r['section']=='main' and r['cohort_model_path']=='devstral24b' and r['cell'] in CELLS:
            prior[(r['cell'],r['task'],r['condition'],r['run'])]=r
rows=[]; summaries=[]; configs={}; source_stats=[]; old_sets={}; new_sets={}; windows={}
for cell in CELLS:
    current=read(BASE/cell/'experiment_results.json');old={}
    for arc in ARCHIVES:
        p=arc/'before/ICLR_experiments/swebench/main/devstral24b'/cell/'experiment_results.json'
        if p.exists():
            for r in read(p):old.setdefault(r['key'],r)
    for r in current:
        if r['timestamp']<'2026-09-09':old.setdefault(r['key'],r)
    old_sets[cell]=list(old.values());new_sets[cell]=[r for r in current if r['timestamp']>='2026-09-09']
    for phase, rs in [('original_all',old_sets[cell]),('rerun',new_sets[cell])]:
        spans=[interval(r) for r in rs]
        windows[(cell,phase)]=(min(b for b,e in spans),max(e for b,e in spans))
    for r in current:
        phase='rerun' if r['timestamp']>='2026-09-09' else 'retained'
        run=f"run_{r['run_num']}";folder=BASE/cell/r['instance_id']/r['condition']/run
        row={'cell':cell,'key':r['key'],'phase':phase,'timestamp':r['timestamp'],'run_dir':str(folder.relative_to(ROOT)),
             'compression_events':r.get('compression_events'),'summary_prompt_tokens':r.get('summarization_prompt_tokens'),'e2e_s':r.get('e2e_latency_s'),'llm_s':r.get('llm_latency_s')}
        issues=[];tok=read(folder/'token_log.json');traj=read(folder/'trajectory.json'); info=traj['info']
        for name in ['token_log.json','trajectory.json','agent.log']:
            p=folder/name; st=p.stat();source_stats.append((str(p),st.st_size,st.st_mtime_ns))
        mapping={'total_prompt_tokens':'total_prompt_tokens','total_completion_tokens':'total_completion_tokens','total_tokens':'total_tokens','llm_latency_s':'total_latency_s','mean_latency_s':'mean_latency_s','step_prompt_tokens':'step_prompt_tokens','step_completion_tokens':'step_completion_tokens','compression_events':'compression_events','summarization_prompt_tokens':'summarization_prompt_tokens','summarization_latency_s':'summarization_latency_s'}
        for a,b in mapping.items():
            if r.get(a)!=tok.get(b):issues.append('index_token:'+a)
        if r.get('n_calls')!=info.get('model_stats',{}).get('api_calls'):issues.append('index_trajectory:n_calls')
        if (r.get('exit_status') or '')!=(info.get('exit_status') or ''):issues.append('index_trajectory:exit_status')
        if sum(tok['step_prompt_tokens'])+tok.get('summarization_prompt_tokens',0)!=tok['total_prompt_tokens']:issues.append('prompt_accounting')
        if abs(sum(tok['step_latency_s'])-tok['total_latency_s'])>0.001*(len(tok['step_latency_s'])+1):issues.append('latency_accounting')
        cfg=normalized_config(traj);h=digest(cfg);configs[h]=cfg;row['config_hash']=h;row['mini_version']=info.get('mini_version')
        row['summary_latency_s']=tok.get('summarization_latency_s',0)
        parsed=attrib.parse_agent_log(folder/'agent.log')
        row.update(attrib.attribute(parsed,info.get('model_stats',{}).get('api_calls'),len(tok['step_prompt_tokens']),set(tok.get('compression_event_steps',[])),info.get('exit_status') or ''))
        row['banners']=parsed['banners'];row['log_time_delta_s']=(folder/'agent.log').stat().st_mtime-(folder/'trajectory.json').stat().st_mtime
        row['source_status']='exact';row['log_time_ok']=abs(row['log_time_delta_s'])<=attrib.LOG_TIME_WINDOW_S
        row['log_verdict']=attrib.verdict_for(row)
        row['null_bytes']=(folder/'agent.log').read_bytes().count(b'\0')
        if row['null_bytes']:issues.append('null_bytes_in_log')
        oldr=old.get(r['key']);row['original_timestamp']=oldr.get('timestamp') if oldr else ''
        row['original_record_unchanged']=False
        if phase=='retained' and oldr:
            # Per-step completion arrays were backfilled after the original execution.
            row['original_record_unchanged']=all(v==r.get(k) for k,v in oldr.items() if k!='step_completion_tokens')
            if not row['original_record_unchanged']:issues.append('retained_record_changed')
        prev=prior.get((cell,r['instance_id'],r['condition'],run),{})
        row['prior_log_verdict']=prev.get('verdict','');row['prior_rerun_reason']=prev.get('prior_rerun_reason','')
        row['issues']=';'.join(issues);rows.append(row)
    subset=[r for r in rows if r['cell']==cell]
    summary={'cell':cell,'current_n':len(current),'unique_keys':len({r['key'] for r in current}),'original_n':len(old),
             'retained_n':sum(r['phase']=='retained' for r in subset),'rerun_n':len(new_sets[cell]),
             'retained_summary_used':sum(r['phase']=='retained' and r['summary_prompt_tokens']>0 for r in subset),
             'retained_compressions':sum(r['phase']=='retained' and r['compression_events']>0 for r in subset),
             'original_peak':peak(old_sets[cell]),'rerun_peak':peak(new_sets[cell]),
             'issues_n':sum(bool(r['issues']) for r in subset),'log_verdicts':dict(C.Counter(r['log_verdict'] for r in subset)),
             'config_hashes':dict(C.Counter(r['config_hash'] for r in subset))}
    for phase in ['original_all','rerun']:
        b,e=windows[(cell,phase)];summary[phase+'_start']=str(b);summary[phase+'_end']=str(e)
    summaries.append(summary);print(json.dumps(summary),flush=True)

# Read one combined launcher log, never count its tee copies as separate executions.
launches=[];active=None
header=re.compile(r'^\[(.*?)\] --- (main|ablation)/devstral24b/(\S+) \|')
completion=re.compile(r'\[\s*\d+/\d+\]\s+(\S+)\s+r(\d+)\s*\|\s*(\S+)')
for line_no,line in enumerate((ROOT/'logs/followup_agent_models_devstral.log').read_text(errors='replace').splitlines(),1):
    m=header.match(line)
    if m:
        when=D.datetime.strptime(m[1].replace(' CDT',''),'%a %b %d %I:%M:%S %p %Y')
        active={'section':m[2],'cell':m[3],'started':str(when),'line':line_no,'remaining':[],'keys':[]};launches.append(active)
    if active:
        m=re.match(r'Agent runs: (\d+) total \((\d+) done, (\d+) remaining\)',line)
        if m:active['remaining'].append(int(m[3]))
        m=completion.search(line)
        if m:active['keys'].append(f'{m[3]}__{m[1]}__r{m[2]}')
launch_rows=[]
for launch in launches:
    if launch['section']!='main' or launch['cell'] not in CELLS or launch['started']<'2026-08-31':continue
    c=C.Counter(launch.pop('keys')); launch['completion_count']=sum(c.values());launch['duplicate_keys']=sum(v>1 for v in c.values());launch_rows.append(launch)

# Per-cell server metrics during the rerun generation window, including idle samples.
metrics=C.defaultdict(list)
pat=re.compile(r'INFO (\d\d-\d\d) (\d\d:\d\d:\d\d).*Running: (\d+) reqs, Waiting: (\d+) reqs, GPU KV cache usage: ([\d.]+)%, Prefix cache hit rate: ([\d.]+)%')
for line in (ROOT/'logs/vllm_devstral.log').read_text(errors='replace').splitlines():
    m=pat.search(line)
    if not m:continue
    t=D.datetime.fromisoformat('2026-'+m[1]+'T'+m[2]);v=list(map(float,m.groups()[2:]))
    for cell in CELLS:
        b,e=windows[(cell,'rerun')]
        if b<=t<=e:metrics[cell].append(v)
metric_rows=[]
for cell,values in metrics.items():
    active=[v for v in values if v[0]>0]
    metric_rows.append({'cell':cell,'samples':len(values),'max_running':max(v[0] for v in values),'max_waiting':max(v[1] for v in values),'max_kv_percent':max(v[2] for v in values),'active_hit_rate_min':min(v[3] for v in active),'active_hit_rate_max':max(v[3] for v in active)})
stable=all((Path(p).stat().st_size,Path(p).stat().st_mtime_ns)==(size,mtime) for p,size,mtime in source_stats)
stable &= all(hashlib.sha256((BASE/c/'experiment_results.json').read_bytes()).hexdigest()==h for c,h in before_hash.items())
write_csv('runs.csv',rows);write_csv('launches.csv',launch_rows);write_csv('server_metrics.csv',metric_rows)
(OUT/'summary.json').write_text(json.dumps({'cells':summaries,'configs':configs,'server_metrics':metric_rows,'sources_stable':stable},indent=2))
print('source stability',stable,'output',OUT)
