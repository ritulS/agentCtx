"""Explicit experiment selections, immutable snapshots, and resume checks."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

from agentctx.compression.adaptive import CompressionConfig, CompressionSchedule

ADAPTIVE_ENV = ('MSWEA_ADAPTIVE_POLICY', 'MSWEA_ADAPTIVE_SCHEDULE', 'MSWEA_ADAPTIVE_MANIFEST')


def digest(value: dict) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     allow_nan=False).encode()).hexdigest()


def policy_source(reference: str) -> Path:
    module, separator, name = reference.partition(':')
    if not separator or not module or not name:
        raise ValueError('adaptive policy must be module:function')
    spec = importlib.util.find_spec(module)
    if spec is None or not spec.origin or not spec.origin.endswith('.py'):
        raise ValueError(f'adaptive policy must have a readable Python source module: {module}')
    return Path(spec.origin).resolve()


def build_selection(*, schedule=None, policy=None, initial=None) -> dict:
    if bool(schedule) == bool(policy):
        raise ValueError('Specify exactly one adaptive schedule or policy')
    spec = {'schema': 1, 'decision_unit': 'query_v1'}
    if schedule:
        if initial:
            raise ValueError('--adaptive-initial-config is only used with --adaptive-policy')
        source = Path(schedule).resolve()
        configs = CompressionSchedule.from_json(source).configs
        spec.update(kind='schedule', configs=[c.to_dict() for c in configs])
        selection = {'source_path': str(source)}
    else:
        if not initial:
            raise ValueError('--adaptive-policy requires --adaptive-initial-config')
        config = CompressionConfig(**json.loads(Path(initial).read_text()))
        source = policy_source(policy)
        source_text = source.read_text(encoding='utf-8')
        spec.update(kind='policy', policy=policy, initial=config.to_dict(),
                    source_sha256=hashlib.sha256(source_text.encode()).hexdigest())
        selection = {'source_path': str(source), 'initial_path': str(Path(initial).resolve()),
                     'policy_source': source_text}
    selection.update(spec=spec, sha256=digest(spec))
    return selection


def selection_metadata(selection: dict) -> dict:
    return {key: value for key, value in selection.items() if key != 'policy_source'}


def load_selection(path) -> dict:
    selection = json.loads(Path(path).read_text(encoding='utf-8'))
    if digest(selection['spec']) != selection['sha256']:
        raise ValueError('Adaptive manifest content does not match its SHA-256')
    if selection['spec'].get('kind') == 'policy':
        if hashlib.sha256(selection.get('policy_source', '').encode()).hexdigest() != selection['spec']['source_sha256']:
            raise ValueError('Adaptive policy snapshot does not match its SHA-256')
    if selection['spec'].get('decision_unit') != 'query_v1':
        raise ValueError('Unsupported adaptive decision semantics')
    return selection


def snapshot_selection(selection: dict, results_dir: Path) -> Path:
    """Exclusive creation prevents replacing an existing snapshot on resume."""
    path = results_dir / '_adaptive' / (selection['sha256'] + '.json')
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open('x', encoding='utf-8') as stream:
            json.dump(selection, stream, indent=2, allow_nan=False)
    except FileExistsError:
        previous = load_selection(path)
        if previous['spec'] != selection['spec'] or previous.get('policy_source') != selection.get('policy_source'):
            raise ValueError(f'Adaptive snapshot mismatch: {path}')
    return path.resolve()


def condition_environment(env: dict, condition: dict, results_dir: Path) -> dict:
    """Ambient adaptive options never affect a fixed condition or baseline."""
    env = dict(env)
    for key in ADAPTIVE_ENV:
        env.pop(key, None)
    selection = condition.get('adaptive')
    if selection is not None:
        if condition['condition'] != 'adaptive':
            raise ValueError('Adaptive settings require the dedicated adaptive condition')
        path = snapshot_selection(selection, results_dir)
        env['MSWEA_ADAPTIVE_MANIFEST'] = str(path)
    return env


def validate_resume(conditions: list[dict], rows: list[dict]) -> None:
    """Reject changed/missing settings before a key can skip a prior run."""
    expected = {c['condition']: c.get('adaptive') for c in conditions}
    for row in rows:
        name = row.get('condition')
        if name not in expected:
            continue
        selected, previous = expected[name], row.get('adaptive')
        if selected is None and previous is None:
            continue
        if (selected is None or previous is None
                or selected['sha256'] != previous.get('sha256')
                or selected['spec'] != previous.get('spec')):
            raise ValueError(f'Adaptive settings differ from saved results for {name}; use a new output directory')


def prepare_run(conditions: list[dict], rows: list[dict], results_dir: Path) -> None:
    validate_resume(conditions, rows)
    manifest_path = results_dir / 'adaptive_conditions.json'
    selected = {c['condition']: selection_metadata(c['adaptive'])
                for c in conditions if c.get('adaptive') is not None}
    previous = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    for condition in conditions:
        name = condition['condition']
        if name in previous:
            if name not in selected or previous[name]['sha256'] != selected[name]['sha256']:
                raise ValueError(f'Adaptive settings differ from the saved launch for {name}; use a new output directory')
    if selected:
        results_dir.mkdir(parents=True, exist_ok=True)
        for condition in conditions:
            if condition.get('adaptive'):
                snapshot_selection(condition['adaptive'], results_dir)
        if not previous:
            with manifest_path.open('x') as stream:
                json.dump(selected, stream, indent=2)
