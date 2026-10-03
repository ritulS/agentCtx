import json,collections,re,sys
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
def cmds(msgs):
    out=[]
    for m in msgs:
        if m['role']=='assistant':
            mm=re.search(r"```mswea_bash_command\n(.*?)```",str(m['content']),re.S)
            out.append(mm.group(1).strip() if mm else '<NO CMD>')
    return out
print("=== SILENT_CRASH ===")
for r in d:
    if fm(r)!='silent_crash': continue
    p=root/r['instance_id']/'full-context'/f"run_{r['run_num']}"
    t=json.load(open(p/'trajectory.json')); m=t['messages']
    c=cmds(m); last=c[-1] if c else ''
    lastrole=m[-1]['role']
    lastout=str(m[-1]['content'])[:150].replace('\n',' | ') if lastrole=='user' else ''
    # recent repeated commands
    rep=max(collections.Counter(c[-30:]).values()) if c else 0
    log=(p/'agent.log').read_text(errors='ignore')
    errs=[l for l in log.splitlines() if re.search(r'Error|Traceback|Exception|timeout|Timeout',l)]
    print(f"{r['instance_id']:36s} r{r['run_num']} e2e={r['e2e_latency_s']:7.1f} llm={r['llm_latency_s']:7.1f} gap={r['e2e_latency_s']-r['llm_latency_s']:7.1f} calls={r['n_calls']:3d} lastrole={lastrole:9s} maxrep30={rep}")
    print(f"    LAST CMD: {last[:200].replace(chr(10),' | ')}")
    if lastout: print(f"    LAST OUT: {lastout}")
    if errs: print(f"    LOG ERRS({len(errs)}): {errs[-1][:200]}")
print("\n=== LIMITS_EXCEEDED ===")
for r in d:
    if fm(r)!='limits_exceeded': continue
    p=root/r['instance_id']/'full-context'/f"run_{r['run_num']}"
    t=json.load(open(p/'trajectory.json')); m=t['messages']; c=cmds(m)
    cnt=collections.Counter(c[-40:])
    print(f"{r['instance_id']:36s} r{r['run_num']} calls={r['n_calls']} uniq_last40={len(cnt)} exit={r['exit_status']}")
    for k,v in cnt.most_common(3): print(f"    x{v}: {k[:160].replace(chr(10),' | ')}")
    print(f"    LAST OUT: {str(m[-1]['content'])[:200].replace(chr(10),' | ')}")
