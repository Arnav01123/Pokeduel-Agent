"""Helpers for tuning the overnight bot's weights against agent/pokeduel_agent.py (Focus Sash mirror)."""
import json, subprocess, random
from paths import ROOT, ARENA, load
from teams import YOURS
MINE = load(ROOT / 'agent' / 'pokeduel_agent.py', 'mine')
TUNED = load(ROOT / 'baselines' / 'overnight_v2_tuned.py', 'tuned')
# The overnight bot's original values (agent_v2); overnight_v2_tuned.py ships with the tuned ones.
ORIGINAL_W = {"stab": 1.5, "tech": 1.5, "metal": 1.2, "band": 1.5, "eff_exp": 1.0,
              "danger_stab": 1.5, "danger_max": 3.0, "retreat_hp": 35, "retreat_margin": 1.2,
              "sd_own_hp": 50, "sd_max_stage": 4, "sd_cap": 2, "sd_foe_hp": 35,
              "bp_finish_hp": 20, "bp_finish_mult": 1.3, "bench_hp_base": 0.5}
DEFAULT_W = ORIGINAL_W
_srv = None
def call(o):
    global _srv
    if _srv is None:
        _srv = subprocess.Popen(['bun', str(ARENA / 'server.ts')], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                text=True, bufsize=1, cwd=str(ARENA))
    _srv.stdin.write(json.dumps(o) + '\n'); _srv.stdin.flush()
    r = json.loads(_srv.stdout.readline())
    if 'error' in r: raise RuntimeError(r['error'])
    return r
def game(tuned_p1, seed):
    agents = {'p1': (TUNED if tuned_p1 else MINE).PokemonAgent(), 'p2': (MINE if tuned_p1 else TUNED).PokemonAgent()}
    st = call({'cmd': 'new', 'seed': seed, 'p1team': YOURS, 'p2team': YOURS})
    bad = 0
    while not st['ended']:
        acts = {s: agents[s].decide(json.loads(json.dumps(st['obs'][s]))) for s in ('p1', 'p2') if st['obs'][s] is not None}
        st = call(dict(cmd='choose', **acts)); bad += len(st.get('bad', {}))
    return st['winner'] == ('A' if tuned_p1 else 'B'), bad
def seeds(tag, n):
    r = random.Random(tag); return [[r.randrange(65536) for _ in range(4)] for _ in range(n)]
def match(w, seedlist):
    """Tuned bot's wins over the seed list, swapping sides every game."""
    TUNED.W.clear(); TUNED.W.update(w)
    wins = bad = 0
    for i, s in enumerate(seedlist):
        ok, b = game(i % 2 == 0, s); wins += ok; bad += b
    return wins, bad
def eval_job(args):
    w, tag, n = args
    return match(w, seeds(tag, n))
