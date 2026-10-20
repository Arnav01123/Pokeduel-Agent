"""Checks the tuned weights in best_w.json: three fresh 200-game matches vs agent/pokeduel_agent.py,
then both weight sets against 600 random roster teams (to see if the tuning overfits)."""
import json, random
import tune_lib as T
import gauntlet as G
from teams import YOURS
best = json.load(open(T.ARENA / 'best_w.json'))['w']
for tag in ('fresh-1', 'fresh-2', 'fresh-3'):
    w, bad = T.match(best, T.seeds(tag, 200))
    print(f'{tag}: tuned overnight {w} - yours {200 - w} | rejected actions {bad}', flush=True)
rng = random.Random(7)
teams = [(G.foe_team(rng), [rng.randrange(65536) for _ in range(4)]) for _ in range(600)]
for lab, wts in (('tuned', best), ('original overnight', T.ORIGINAL_W)):
    T.TUNED.W.clear(); T.TUNED.W.update(wts); wins = 0
    for i, (ft, seed) in enumerate(teams):
        a, b = ((lab, T.TUNED, YOURS), ('foe', G.Greedy, ft)) if i % 2 == 0 else (('foe', G.Greedy, ft), (lab, T.TUNED, YOURS))
        r, _, _ = G.game(a, b, seed); wins += r == lab
    print(f'{lab} (Sash team) vs 600 random roster teams: {wins}/600 = {wins / 6:.1f}%', flush=True)
