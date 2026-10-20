import random, json, time, sys
from multiprocessing import Pool
import tune_lib as T
SPACE = {"stab": (1, 2), "tech": (1, 2), "metal": (1, 1.5), "band": (1, 2), "eff_exp": (0.5, 2.5),
         "danger_stab": (1, 2), "danger_max": (1.5, 6), "retreat_hp": (0, 60), "retreat_margin": (0.8, 2),
         "sd_own_hp": (30, 101), "sd_max_stage": (0, 6), "sd_cap": (0, 3), "sd_foe_hp": (0, 100),
         "bp_finish_hp": (0, 60), "bp_finish_mult": (1, 3), "bench_hp_base": (0, 1)}
INTS = {"sd_max_stage", "sd_cap"}
def rand_w(r):
    return {k: (r.randint(int(a), int(b)) if k in INTS else round(r.uniform(a, b), 3)) for k, (a, b) in SPACE.items()}
def perturb(w, r, scale):
    n = dict(w)
    for k in r.sample(list(SPACE), 3):
        a, b = SPACE[k]
        if k in INTS: n[k] = min(int(b), max(int(a), n[k] + r.choice([-1, 1])))
        else: n[k] = round(min(b, max(a, n[k] + r.gauss(0, scale * (b - a)))), 3)
    return n
if __name__ == '__main__':
    r = random.Random(1); t0 = time.time(); NT = 200
    cands = [dict(T.DEFAULT_W)] + [rand_w(r) for _ in range(int(sys.argv[1]))]
    with Pool(2) as p:
        res = p.map(T.eval_job, [(w, 'train', NT) for w in cands])
        scored = sorted(zip([x[0] for x in res], range(len(cands))), reverse=True)
        print(f'stage1 {len(cands)} configs in {time.time()-t0:.0f}s; default={res[0][0]}/{NT}; best={[s for s,_ in scored[:8]]}', flush=True)
        pool = [cands[i] for _, i in scored[:6]]
        # local search around the best ones
        for rnd in range(int(sys.argv[2])):
            kids = [perturb(w, r, 0.15) for w in pool for _ in range(4)]
            kres = p.map(T.eval_job, [(w, 'train', NT) for w in kids])
            pres = p.map(T.eval_job, [(w, 'train', NT) for w in pool])
            allc = sorted(zip([x[0] for x in pres + kres], range(len(pool + kids))), reverse=True)
            both = pool + kids; pool = [both[i] for _, i in allc[:6]]
            print(f'round {rnd}: best {allc[0][0]}/{NT} ({time.time()-t0:.0f}s)', flush=True)
        # re-check top 6 on a bigger held-out set to avoid lucky picks
        chk = p.map(T.eval_job, [(w, 'select', 600) for w in pool])
        best = max(range(len(pool)), key=lambda i: chk[i][0])
        print('select-set scores /600:', [c[0] for c in chk], flush=True)
        json.dump({'w': pool[best], 'select': chk[best][0]}, open(T.ARENA / 'best_w.json', 'w'), indent=1)
        print(json.dumps(pool[best]), flush=True)
