from arena import *
import sys, json, collections
from paths import ARENA
import random, time
SETS = json.load(open(ARENA / 'ps/data/random-battles/gen9/sets.json'))
SETS.setdefault('togekiss', {'sets':[{'movepool':['Dazzling Gleam','Air Slash','Aura Sphere','Flamethrower','Nasty Plot','Roost'],'abilities':['Serene Grace']}]})
SETS.setdefault('alakazam', {'sets':[{'movepool':['Psychic','Shadow Ball','Focus Blast','Dazzling Gleam','Nasty Plot'],'abilities':['Magic Guard']}]})
SETS.setdefault('ferrothorn', {'sets':[{'movepool':['Power Whip','Gyro Ball','Leech Seed','Stealth Rock','Knock Off'],'abilities':['Iron Barbs']}]})
ROSTER = ["Garchomp","Dragonite","Tyranitar","Metagross","Salamence","Hydreigon","Dragapult","Volcarona","Lucario","Scizor","Gengar","Gyarados","Charizard","Blastoise","Venusaur","Arcanine","Excadrill","Togekiss","Snorlax","Alakazam","Lapras","Corviknight","Ferrothorn","Greninja"]
ITEMS = ["Leftovers", "Life Orb", "Choice Band", "Choice Specs", "Focus Sash", "Sitrus Berry"]
def foe_team(rng):
    out = []
    for sp in rng.sample(ROSTER, 3):
        key = sp.lower(); s = rng.choice(SETS[key]['sets'])
        moves = rng.sample(s['movepool'], min(4, len(s['movepool'])))
        out.append(f"{sp} @ {rng.choice(ITEMS)}\nAbility: {s['abilities'][0]}\nEVs: 84 HP / 84 Atk / 84 Def / 84 SpA / 84 SpD / 84 Spe\n- " + "\n- ".join(moves) + "\n")
    return "\n".join(out)
class Greedy:   # simple opponent: strongest move by power x type x STAB, best-typed switch-in
    class PokemonAgent:
        def decide(self, o):
            if o.get('team_preview'): return 'team 123'
            ms = o.get('valid_moves') or []
            if ms and not o.get('force_switch'):
                b = max(ms, key=lambda m: (m['base_power'] or 0) * m['type_multiplier'] * (1.5 if m['stab'] else 1))
                return f"move {b['index']}"
            sw = o.get('valid_switches') or []
            return f"switch {sw[0]['index']}" if sw else 'move 1'
if __name__ == '__main__':
    N = int(sys.argv[1]); rng = random.Random(7)
    teams = [(foe_team(rng), [rng.randrange(65536) for _ in range(4)]) for _ in range(N)]
    for lab, mod, team in (('yours', MINE, YOURS), ('overnight', ONIGHT, OVERNIGHT)):
        w = bad = 0; err = 0
        for i, (ft, seed) in enumerate(teams):
            try:
                a, b = ((lab, mod, team), ('foe', Greedy, ft)) if i % 2 == 0 else (('foe', Greedy, ft), (lab, mod, team))
                r, tn, bd = game(a, b, seed); w += r == lab; bad += bd[lab]
            except Exception as e: err += 1
        print(f"{lab} vs {N} random roster teams (greedy pilot): won {w}/{N-err} = {100*w/(N-err):.1f}% | rejected actions {bad} | team-build errors {err}", flush=True)
