"""Deterministic heuristic baseline for the Scizor / Tyranitar / Dragapult team.

Team: Scizor / Tyranitar / Dragapult (see TEAM_SETS).
Interface: PokemonAgent with decide(observation) -> str, stdlib only, no I/O,
no subprocesses, no import-time side effects. Deterministic (no RNG).

Observation contract (deployment-degraded portal schema): turn,
team_preview, force_switch; my_active name/types/hp_percent/boosts/
condition; foe name/types/hp_percent ONLY; my_team rows; valid_moves with
index/id/name/type/category/base_power/accuracy/type_multiplier/stab;
valid_switches with index/name/types/hp_percent/active/fainted. Hidden foe
fields (status/boosts/item/moves/stats/bench) are NEVER read.

Damage model (proxies, NOT rolls): score = base_power * type_multiplier *
STAB(1.5) * ability/item mods, with small situational terms documented below.
Key details:
- dual-type multiplication is a product over foe types (0 on any immunity);
- Technician (<=60BP, 1.5x) + Metal Coat (Steel, 1.2x) on Bullet Punch;
- Choice Band 1.5x applies to PHYSICAL moves only (never Flamethrower);
- Dragon Darts scored at the adapter-supplied combined power (2x50 = 100);
  the adapter MUST present combined power, this agent never double-counts;
- Phantom Force is selected as a normal move; the engine handles the charge
  turn, whose singleton request mask (no PP/disabled fields, trapped) is
  followed, never inferred from;
- U-turn is damage plus a pivot: used as an offensive pivot when a switch is
  desired, with the same legal bench mapping as hard switches;
- Swords Dance only behind the safe-setup gate, max 2 per stint, never into
  a Fire threat; all transient memory resets on switch / new battle.
"""

# Weights tuned vs pokeduel_agent.py in the Focus Sash mirror (original values in agent_v2.py).
W = {"stab": 1.861,
     "tech": 1.913,
     "metal": 1.421,
     "band": 1.724,
     "eff_exp": 0.511,
     "danger_stab": 1.834,
     "danger_max": 5.92,
     "retreat_hp": 44.965,
     "retreat_margin": 1.644,
     "sd_own_hp": 58.177,
     "sd_max_stage": 3,
     "sd_cap": 1,
     "sd_foe_hp": 81.764,
     "bp_finish_hp": 56.126,
     "bp_finish_mult": 3,
     "bench_hp_base": 0}

PREVIEW_ORDER = "team 312"  # Dragapult leads.

TEAM_SETS = [
    {"name": "Scizor", "ability": "Technician", "item": "Metal Coat",
     "nature": "Jolly", "evs": "252 Atk / 4 SpD / 252 Spe",
     "moves": ["Bullet Punch", "Swords Dance", "U-turn", "Close Combat"]},
    {"name": "Tyranitar", "ability": "Sand Stream", "item": "Assault Vest",
     "nature": "Impish", "evs": "252 HP / 252 Atk / 4 Def",
     "moves": ["Crunch", "Rock Slide", "Ice Punch", "Earthquake"]},
    {"name": "Dragapult", "ability": "Clear Body", "item": "Choice Band",
     "nature": "Hasty", "evs": "252 Atk / 4 SpD / 252 Spe",
     "moves": ["Dragon Darts", "Flamethrower", "U-turn", "Phantom Force"]},
]

TYPE_CHART = {
    "Normal": {"weak": {"Fighting"}, "resist": set(), "immune": {"Ghost"}},
    "Fire": {"weak": {"Water", "Ground", "Rock"},
             "resist": {"Fire", "Grass", "Ice", "Bug", "Steel", "Fairy"}, "immune": set()},
    "Water": {"weak": {"Electric", "Grass"},
              "resist": {"Fire", "Water", "Ice", "Steel"}, "immune": set()},
    "Electric": {"weak": {"Ground"},
                 "resist": {"Electric", "Flying", "Steel"}, "immune": set()},
    "Grass": {"weak": {"Fire", "Ice", "Poison", "Flying", "Bug"},
              "resist": {"Water", "Electric", "Grass", "Ground"}, "immune": set()},
    "Ice": {"weak": {"Fire", "Fighting", "Rock", "Steel"},
            "resist": {"Ice"}, "immune": set()},
    "Fighting": {"weak": {"Flying", "Psychic", "Fairy"},
                 "resist": {"Bug", "Rock", "Dark"}, "immune": set()},
    "Poison": {"weak": {"Ground", "Psychic"},
               "resist": {"Grass", "Fighting", "Poison", "Bug", "Fairy"}, "immune": set()},
    "Ground": {"weak": {"Water", "Grass", "Ice"},
               "resist": {"Poison", "Rock"}, "immune": {"Electric"}},
    "Flying": {"weak": {"Electric", "Ice", "Rock"},
               "resist": {"Grass", "Fighting", "Bug"}, "immune": {"Ground"}},
    "Psychic": {"weak": {"Bug", "Ghost", "Dark"},
                "resist": {"Fighting", "Psychic"}, "immune": set()},
    "Bug": {"weak": {"Fire", "Flying", "Rock"},
            "resist": {"Grass", "Fighting", "Ground"}, "immune": set()},
    "Rock": {"weak": {"Water", "Grass", "Fighting", "Ground", "Steel"},
             "resist": {"Normal", "Fire", "Poison", "Flying"}, "immune": set()},
    "Ghost": {"weak": {"Ghost", "Dark"},
              "resist": {"Poison", "Bug"}, "immune": {"Normal", "Fighting"}},
    "Dragon": {"weak": {"Ice", "Dragon", "Fairy"},
               "resist": {"Fire", "Water", "Electric", "Grass"}, "immune": set()},
    "Dark": {"weak": {"Fighting", "Bug", "Fairy"},
             "resist": {"Ghost", "Dark"}, "immune": {"Psychic"}},
    "Steel": {"weak": {"Fire", "Fighting", "Ground"}, "immune": {"Poison"},
              "resist": {"Normal", "Grass", "Ice", "Flying", "Psychic",
                         "Bug", "Rock", "Dragon", "Steel", "Fairy"}},
    "Fairy": {"weak": {"Poison", "Steel"}, "immune": {"Dragon"},
              "resist": {"Fighting", "Bug", "Dark"}},
}

OWN_TYPES = {"Scizor": ("Bug", "Steel"), "Tyranitar": ("Rock", "Dark"),
             "Dragapult": ("Dragon", "Ghost")}
OWN_ITEM = {"Scizor": "Metal Coat", "Tyranitar": "Assault Vest",
            "Dragapult": "Choice Band"}
OWN_ABILITY = {"Scizor": "Technician", "Tyranitar": "Sand Stream",
               "Dragapult": "Clear Body"}
# (base_power, type, category, priority, setup); Darts power is COMBINED 2x50.
OWN_MOVES = {
    "Scizor": [("bulletpunch", 40, "Steel", "Physical", True, False),
               ("swordsdance", 0, "Normal", "Status", False, True),
               ("uturn", 70, "Bug", "Physical", False, False),
               ("closecombat", 120, "Fighting", "Physical", False, False)],
    "Tyranitar": [("crunch", 80, "Dark", "Physical", False, False),
                  ("rockslide", 75, "Rock", "Physical", False, False),
                  ("icepunch", 75, "Ice", "Physical", False, False),
                  ("earthquake", 100, "Ground", "Physical", False, False)],
    "Dragapult": [("dragondarts", 100, "Dragon", "Physical", False, False),
                  ("flamethrower", 90, "Fire", "Special", False, False),
                  ("uturn", 70, "Bug", "Physical", False, False),
                  ("phantomforce", 90, "Ghost", "Physical", False, False)],
}


def _norm(s):
    # Separator-insensitive: portal may send 'dragon-darts', 'Dragon Darts'
    # or 'dragondarts' for the same move; lock matching must survive that.
    return str(s or "").strip().lower().replace(" ", "").replace("-", "").replace("_", "")


def _cap(s):
    s = _norm(s)
    return s[:1].upper() + s[1:] if s else s


def effectiveness(move_type, foe_types):
    """Correct dual-type product: 0.0 on any immunity, else 0.5/2 per type.

    TYPE_CHART is stored DEFENSIVE (each type's weak/resist/immune describe
    it as a defender -- the legacy offensive reuse of these sets was the
    documented dual-type bug). So for move M vs defender D we consult D's
    entry: M in D.weak -> 2x, M in D.resist -> 0.5x, M in D.immune -> 0.
    """
    m = _norm(move_type)
    mult = 1.0
    for ft in (foe_types or []):
        entry = TYPE_CHART.get(_cap(ft))
        if entry is None:
            continue
        if m in {str(x).lower() for x in entry["immune"]}:
            return 0.0
        if m in {str(x).lower() for x in entry["resist"]}:
            mult *= 0.5
        elif m in {str(x).lower() for x in entry["weak"]}:
            mult *= 2.0
    return mult


def score_move(mon_name, move, mult):
    """Damage proxy for one candidate move. move: dict with type/category/
    base_power. STAB from own sheet types; item/ability mods for this team."""
    try:
        bp = float(move.get("base_power", 0))
    except (TypeError, ValueError):
        bp = 0.0
    if bp <= 0:
        return 0.0
    mtype = _cap(move.get("type", ""))
    score = bp * float(mult if mult else 1.0) ** W["eff_exp"]
    if mtype in OWN_TYPES.get(mon_name, ()):
        score *= W["stab"]
    if mon_name == "Scizor":
        if bp <= 60:
            score *= W["tech"]  # Technician
        if mtype == "Steel":
            score *= W["metal"]  # Metal Coat
    if mon_name == "Dragapult" and str(move.get("category", "")).lower() == "physical":
        score *= W["band"]  # Choice Band boosts PHYSICAL only, never Flamethrower
    return score


def _num(x, d=0.0):
    try:
        return float(x)
    except (TypeError, ValueError):
        return d


# Native L100 max HP for the portal's DEFAULT builds (foes use defaults;
# verified against portal switch lines: 357/325/297/352/400 exact).
FOE_MAXHP = {"Garchomp": 357, "Dragonite": 323, "Tyranitar": 404,
    "Metagross": 364, "Salamence": 331, "Hydreigon": 325, "Dragapult": 317,
    "Volcarona": 311, "Lucario": 281, "Scizor": 344, "Gengar": 261,
    "Gyarados": 331, "Charizard": 297, "Blastoise": 362, "Venusaur": 364,
    "Arcanine": 384, "Excadrill": 361, "Togekiss": 374, "Snorlax": 524,
    "Alakazam": 252, "Lapras": 464, "Corviknight": 400, "Ferrothorn": 352,
    "Greninja": 286}
# Our exact native max HP (portal-verified for Scizor/Dragapult via switch
# lines; Tyranitar pending a portal appearance).
OWN_MAXHP = {"Scizor": 281, "Tyranitar": 404, "Dragapult": 317}


def hp_percent(entry, name, foe_max=None):
    """Scale-robust HP 0-100. Prefers condition 'cur/max' (exact on every
    surface); else treats hp_percent > 100 as RAW HP over the known max
    (portal behaviorally sends raw values, e.g. foe 49 not 12); else uses
    the value as percent; else the default. Native percent input is
    unaffected (<=100 passes through, condition agrees)."""
    if isinstance(entry, dict):
        cond = entry.get("condition", "")
        m = None
        try:
            m = str(cond).strip().split("/")
        except Exception:
            m = None
        if m and len(m) == 2:
            try:
                cur, mx = float(m[0]), float(m[1])
                if mx > 0:
                    return min(max(cur / mx * 100.0, 0.0), 100.0)
            except (TypeError, ValueError):
                pass
        v = _num(entry.get("hp_percent", None), None)
        if v is None:
            v = 100.0
        mx = foe_max or OWN_MAXHP.get(name, None)
        if v > 100.0 and mx:
            return min(max(v / float(mx) * 100.0, 0.0), 100.0)
        return min(max(v, 0.0), 100.0)
    return 100.0


def detect_scale(entry, name):
    """Per-battle HP scale detection from the anchored active field.

    my_active carries BOTH condition 'cur/max' and hp_percent. If hp_percent
    matches 100*cur/max it is percent-scale; if it matches cur it is raw HP.
    Returns 'raw', 'percent', or None (undetectable -> schema default).
    The battle-sticky scale then disambiguates foe/bench values <= 100,
    which are otherwise identical in both scales (e.g. raw 49 vs 49%)."""
    if not isinstance(entry, dict):
        return None
    try:
        parts = str(entry.get("condition", "")).strip().split("/")
        if len(parts) != 2:
            return None
        cur, mx = float(parts[0]), float(parts[1])
        if mx <= 0:
            return None
    except (TypeError, ValueError):
        return None
    v = _num(entry.get("hp_percent", None), None)
    if v is None:
        return None
    pct = cur / mx * 100.0
    # Raw first: at tiny values both hypotheses are within absolute tolerance
    # (hp 1 of 317: |1-0.3| < 1), and only the raw match is exact there.
    if abs(v - cur) <= max(1.0, cur * 0.02):
        return "raw"
    if abs(v - pct) <= max(1.0, pct * 0.02):
        return "percent"
    return None


def scale_hp(v, mx, scale):
    """Convert a foe/bench HP number to 0-100 using the detected scale."""
    try:
        v = float(v)
    except (TypeError, ValueError):
        return 100.0
    if scale == "raw" and mx:
        return min(max(v / float(mx) * 100.0, 0.0), 100.0)
    return min(max(v, 0.0), 100.0)


class PokemonAgent:
    def __init__(self):
        self._active = None      # normalized active name: stint key
        self._sd = 0             # Swords Dances this stint
        self._locked = None      # Choice-locked move id this stint
        self._vol_switch = False  # voluntary switch/pivot used last decide
        self._scale = None       # detected HP scale: 'raw' | 'percent' | None
        self.fallbacks = 0       # generic fallback count (audit, not wins)

    def _reset_stint(self, active):
        self._active = active
        self._sd = 0
        self._locked = None
        self._vol_switch = False

    # -- observation accessors (allowed keys only) -------------------------
    @staticmethod
    def _moves(obs):
        m = obs.get("valid_moves")
        return m if isinstance(m, list) else []

    @staticmethod
    def _switches(obs):
        s = obs.get("valid_switches")
        return s if isinstance(s, list) else []

    @staticmethod
    def _enabled(moves):
        """Moves not marked disabled. Absence of flags = flat mask (no info)."""
        if not any(isinstance(m, dict) and "disabled" in m for m in moves):
            return None  # flat mask: unknown, caller uses lock memory
        return [m for m in moves
                if isinstance(m, dict) and not m.get("disabled")]

    def _bench_score(self, name, foe_types, hp):
        best = 0.0
        for _mid, bp, mtype, cat, _pri, setup in OWN_MOVES.get(name, []):
            if setup or bp <= 0:
                continue
            s = score_move(name, {"type": mtype, "category": cat,
                                  "base_power": bp},
                           effectiveness(mtype, foe_types))
            if s > best:
                best = s
        return best * (W["bench_hp_base"] + (1 - W["bench_hp_base"]) * min(max(hp / 100.0, 0.0), 1.0))

    def decide(self, observation):
        try:
            return self._decide(observation if isinstance(observation, dict) else {})
        except Exception:
            self.fallbacks += 1
            return self._last_resort(observation)

    def _last_resort(self, obs):
        try:
            if isinstance(obs, dict) and obs.get("team_preview"):
                return PREVIEW_ORDER
            for m in self._moves(obs):
                if isinstance(m, dict) and "index" in m:
                    return "move %s" % m["index"]
            for s in self._switches(obs):
                if isinstance(s, dict) and "index" in s:
                    return "switch %s" % s["index"]
        except Exception:
            pass
        return "move 1"

    def _decide(self, obs):
        if obs.get("team_preview"):
            self._reset_stint(None)
            self._scale = None  # new battle: re-detect HP scale from anchor
            return PREVIEW_ORDER
        me = obs.get("my_active") or {}
        foe = obs.get("foe") or {}
        mon = _cap(me.get("name", ""))
        mon_key = _norm(me.get("name", ""))
        if mon_key != (self._active or ""):
            self._reset_stint(mon_key)
        foe_types = [str(t) for t in (foe.get("types") or []) if t]
        det = detect_scale(me, mon)
        if det is not None:
            self._scale = det  # sticky per battle, refreshed every turn
        foe_max = FOE_MAXHP.get(_cap(foe.get("name", "")))
        foe_hp = scale_hp((foe.get("hp_percent", 100)
                           if isinstance(foe, dict) else 100),
                          foe_max, self._scale)
        own_hp = hp_percent(me, mon)
        try:
            atk_stage = int((me.get("boosts") or {}).get("atk", 0))
        except (TypeError, ValueError, AttributeError):
            atk_stage = 0
        my_types = [str(t) for t in (me.get("types") or []) if t] or list(OWN_TYPES.get(mon, ()))
        moves = [m for m in self._moves(obs) if isinstance(m, dict)]
        switches = [s for s in self._switches(obs) if isinstance(s, dict)]

        force = bool(obs.get("force_switch")) or not moves
        if force:
            self._vol_switch = False
            pick = self._pick_bench(switches, foe_types)
            if pick is not None:
                return pick
            self.fallbacks += 1
            return self._last_resort(obs)

        enabled = self._enabled(moves)
        # Choice-lock memory: conservative repeat on flat masks only.
        if enabled is None:
            if self._locked:
                for m in moves:
                    if _norm(m.get("id")) == self._locked or                        _norm(m.get("name")) == self._locked:
                        try:
                            return "move %s" % m["index"]
                        except KeyError:
                            pass
            pool = moves
        else:
            pool = enabled
            if not pool:
                self.fallbacks += 1
                pick = self._pick_bench(switches, foe_types)
                return pick if pick is not None else self._last_resort(obs)

        # Threat read: best assumed-STAB foe type multiplier vs my types.
        danger = 0.0
        for ft in foe_types:
            danger = max(danger, effectiveness(ft, my_types))
        danger *= W["danger_stab"]  # assumed STAB on the foe's best type

        # Best attack in the legal pool (adapter-supplied multipliers used
        # when present; recomputed from observed types otherwise).
        scored = []
        for m in pool:
            try:
                idx = m["index"]
            except KeyError:
                continue
            # Never trust adapter-supplied multipliers blindly: recompute from
            # the observed foe types. Identical when the supplier
            # is correct; immune when it is not. Fall back to supplied only
            # when foe types are absent.
            if foe_types:
                mult = effectiveness(m.get("type", ""), foe_types)
            else:
                try:
                    mult = float(m.get("type_multiplier", 1.0))
                except (TypeError, ValueError):
                    mult = 1.0
            s = score_move(mon, m, mult)
            if _norm(m.get("id")) == "bulletpunch" and foe_hp <= W["bp_finish_hp"]:
                s *= W["bp_finish_mult"]  # priority finisher
            scored.append((s, str(idx), m))
        if not scored:
            self.fallbacks += 1
            return self._last_resort(obs)
        scored.sort(key=lambda r: (-r[0], r[1]))
        best_score, best_idx, best_move = scored[0]

        # Voluntary switch / U-turn pivot desire.
        def _bhp(s):
            return scale_hp((s.get("hp_percent", 0) if isinstance(s, dict) else 0),
                            OWN_MAXHP.get(_cap(s.get("name", ""))), self._scale)
        bench = [(self._bench_score(_cap(s.get("name", "")), foe_types,
                                   _bhp(s)), s)
                 for s in switches]
        bench = [(b, s) for b, s in bench if b > 0]
        bench.sort(key=lambda r: -r[0])
        want_out = (own_hp <= W["retreat_hp"] and bench
                    and bench[0][0] > best_score * W["retreat_margin"]
                    and not self._vol_switch)
        if want_out:
            for _s, _i, m in scored:
                if _norm(m.get("id")) == "uturn" or _norm(m.get("name")) == "uturn":
                    self._vol_switch = True
                    self._locked = _norm(m.get("id")) or _norm(m.get("name"))
                    return "move %s" % m["index"]
            self._vol_switch = True
            try:
                return "switch %s" % bench[0][1]["index"]
            except (KeyError, TypeError, IndexError):
                self.fallbacks += 1
                return self._last_resort(obs)

        # Swords Dance behind the safe-setup gate (Scizor only; Tyranitar is
        # Assault Vest, Dragapult is Choice Band: neither can setup).
        for _s, _i, m in scored:
            mid = _norm(m.get("id")) or _norm(m.get("name"))
            if mid == "swordsdance" and mon == "Scizor":
                if (own_hp >= W["sd_own_hp"] and danger < W["danger_max"] and atk_stage < W["sd_max_stage"]
                        and self._sd < W["sd_cap"] and foe_hp > W["sd_foe_hp"]):
                    self._sd += 1
                    self._vol_switch = False
                    return "move %s" % m["index"]
                break

        self._vol_switch = False
        ret = "move %s" % best_move["index"]
        # Remember Choice lock for ANY Dragapult move (Choice locks the selected
        # move regardless of category -- locking only physical moves let a
        # special opener (Flamethrower) desync the memory and propose a
        # disabled move next turn).
        if mon == "Dragapult":
            self._locked = _norm(best_move.get("id")) or _norm(best_move.get("name"))
        # Legality guard: never return an action outside the supplied mask.
        legal = set("move %s" % m["index"] for m in moves if "index" in m)
        legal.update("switch %s" % s["index"] for s in switches if "index" in s)
        if ret not in legal:
            self.fallbacks += 1
            return self._last_resort(obs)
        return ret

    def _pick_bench(self, switches, foe_types):
        best, pick = -1.0, None
        for s in switches:
            try:
                idx = s["index"]
            except KeyError:
                continue
            name = _cap(s.get("name", ""))
            if not name:
                continue
            # Truthiness (not =="true"): adapter sends bools, but never trust
            # a fainted mon onto the field on a truthy 1/"yes" either.
            if s.get("fainted"):
                continue
            bhp = scale_hp((s.get("hp_percent", 0) if isinstance(s, dict) else 0),
                             OWN_MAXHP.get(name), self._scale)
            if bhp <= 0:
                continue
            sc = self._bench_score(name, foe_types, bhp)
            if sc > best:
                best, pick = sc, "switch %s" % idx
        return pick
