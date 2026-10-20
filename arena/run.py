from arena import *
import sys, json, collections
import time, random
def match(label, a, b, n):
    rng = random.Random(label); res = collections.Counter(); bad = collections.Counter(); turns = []
    t = time.time()
    for g in range(n):
        seed = [rng.randrange(65536) for _ in range(4)]
        p1, p2 = (a, b) if g % 2 == 0 else (b, a)   # swap sides every game
        w, tn, bd = game(p1, p2, seed); res[w] += 1; bad += bd; turns.append(tn)
    print(f"{label}: yours {res['yours']} - overnight {res['overnight']} (ties {res['tie']+res['TIMEOUT']}) | avg turns {sum(turns)/n:.1f} | rejected actions {dict(bad)} | {time.time()-t:.0f}s", flush=True)
N = int(sys.argv[1])
match('A. each with own team (yours=Sash Ttar, overnight=AV Ttar)', ('yours', MINE, YOURS), ('overnight', ONIGHT, OVERNIGHT), N)
match('B. both use Focus Sash team', ('yours', MINE, YOURS), ('overnight', ONIGHT, YOURS), N)
match('C. both use Assault Vest team', ('yours', MINE, OVERNIGHT), ('overnight', ONIGHT, OVERNIGHT), N)
