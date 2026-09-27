#!/usr/bin/env python3
"""Run every strategy file with its DEFAULTS through the runner.

Usage: python3 tools/test_strategies.py [name-filter ...]
"""
import concurrent.futures as cf, json, os, subprocess, sys, time
UI = os.path.expanduser('~/Project/backtrader-ui')
BT = os.path.expanduser('~/Project/backtrader')
PY = BT + '/env/bin/python'
env = dict(os.environ, BT_ROOT=BT, MPLBACKEND='Agg')
only = sys.argv[1:]
files = sorted(os.path.relpath(os.path.join(d, f), UI) for d, _, fs in os.walk(UI + '/strategies') for f in fs if f.endswith('.py'))
if only: files = [f for f in files if any(o in f for o in only)]
info = json.loads(subprocess.run([PY, 'python/bt_runner.py', 'inspect', *files], cwd=UI, env=env, capture_output=True, text=True).stdout)['results']

def job(f, cls):
    i = info[f]; d = i['defaults']
    feed = d.get('feed', 'orcl-1995-2014.txt')
    if feed.startswith('yahoo:'):
        p = feed.split(':'); fs = {'type': 'yahoo', 'ticker': p[1], 'interval': p[2] if len(p) > 2 else '1d'}
    else:
        fs = {'type': 'file', 'path': BT + '/datas/' + feed}
    c = next(x for x in i['classes'] if x['name'] == cls)
    params = {p['name']: p['default'] for p in c['params']}
    params.update(d.get('params', {}))
    cfg = dict(strategyFile=f, strategyClass=cls, params={k: (json.dumps(v) if isinstance(v, (list, dict)) else v) for k, v in params.items()},
               options={o['name']: o['default'] for o in i['options']}, feed=fs, feedName=os.path.splitext(os.path.basename(feed))[0],
               fromdate=d.get('fromdate'), todate=d.get('todate'), cash=d.get('cash'), commission=d.get('commission'),
               slippage=d.get('slippage'), coc=d.get('coc'), sizer=d.get('sizer'))
    t = time.time()
    p = subprocess.run([PY, 'python/bt_runner.py', 'run'], cwd=UI, env=env, input=json.dumps(cfg), capture_output=True, text=True, timeout=300)
    try:
        r = json.loads(p.stdout)
    except Exception:
        return f, cls, 'CRASH ' + p.stderr[-300:], time.time() - t
    if not r['ok']:
        return f, cls, 'ERR ' + r['error'].strip().splitlines()[-1][:160], time.time() - t
    m = r['metrics']
    return f, cls, 'ok bars=%d trades=%d ret=%.2f%% inds=%d an=%d log=%dB' % (m['bars'], m['trades'], m['totalReturnPct'] or 0, len(r['indicators']), len(r['analyzers']), len(r['log'])), time.time() - t

jobs = []
for f in files:
    i = info[f]
    if not i['ok']:
        print('%-55s IMPORT ERROR %s' % (f, i['error'].strip().splitlines()[-1])); continue
    for c in i['classes']:
        jobs.append((f, c['name']))
with cf.ThreadPoolExecutor(8) as ex:
    for f, cls, res, dt in sorted(ex.map(lambda a: job(*a), jobs)):
        print('%-52s %-24s %5.1fs %s' % (f[11:], cls, dt, res))
