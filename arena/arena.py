"""Plays two agents against each other through the Showdown simulator (server.ts, run with Bun)."""
import json, subprocess, collections
from paths import ROOT, ARENA, load
from teams import OVERNIGHT, YOURS
ONIGHT = load(ROOT / 'baselines' / 'overnight_v2.py', 'onight')
MINE = load(ROOT / 'agent' / 'pokeduel_agent.py', 'mine')
srv = subprocess.Popen(['bun', str(ARENA / 'server.ts')], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                       text=True, bufsize=1, cwd=str(ARENA))
def call(o):
    srv.stdin.write(json.dumps(o) + '\n'); srv.stdin.flush()
    r = json.loads(srv.stdout.readline())
    if 'error' in r: raise RuntimeError(r['error'])
    return r
def game(p1, p2, seed, log=None):
    """p1/p2 = (label, module, team text). Returns (winner label or 'tie', turns, rejected-action counts)."""
    agents = {'p1': p1[1].PokemonAgent(), 'p2': p2[1].PokemonAgent()}
    st = call({'cmd': 'new', 'seed': seed, 'p1team': p1[2], 'p2team': p2[2]})
    bad = collections.Counter()
    while not st['ended']:
        acts = {}
        for sid in ('p1', 'p2'):
            o = st['obs'][sid]
            if o is not None:
                acts[sid] = agents[sid].decide(json.loads(json.dumps(o)))
                if log is not None:
                    log.append((sid, o.get('turn'), (o.get('my_active') or {}).get('name'), (o.get('foe') or {}).get('name'), acts[sid]))
        st = call(dict(cmd='choose', **acts))
        for sid in st.get('bad', {}): bad[(p1 if sid == 'p1' else p2)[0]] += 1
    w = st['winner']
    return (p1[0] if w == 'A' else p2[0] if w == 'B' else 'tie'), st['turn'], bad
