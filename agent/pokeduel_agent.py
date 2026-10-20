"""
PokéDuel 3v3 agent: Dragapult (lead) / Scizor / Tyranitar
Uses only the Python standard library.

Sets: Choice Band Dragapult, Metal Coat Scizor, Focus Sash Tyranitar
(set items on the portal; the bot can't change them)

Safety:   HP scale normalised, Choice lock remembered, decide() never
          crashes and only returns legal actions.
Done:     team preview, Dragapult logic, Choice Band lock, Scizor logic,
          Tyranitar logic, sand chip preference on switch-ins, matchup-aware switching
Pending:  more Tyranitar exceptions
"""

DRAGAPULT = "Dragapult"
SCIZOR = "Scizor"
TYRANITAR = "Tyranitar"

# Scizor U-turns out of these. The follow-up switch prefers Dragapult,
# then Tyranitar, and never Scizor (so Dragapult U-turning back can't loop).
# Possible Focus Sash: only U-turn while the foe is at 100% (sash intact).
SCIZOR_PIVOT_IF_FULL = {"Venusaur"}
# Follow-up switch after a U-turn against these: Dragapult, else Tyranitar
PIVOT_TARGETS = {"Greninja", "Venusaur"}


# Scizor uses one Swords Dance on these (passive, weak to Close Combat)
SCIZOR_SETUP_TARGETS = {"Lapras", "Snorlax"}

# Boosted Scizor uses Close Combat on these instead of Bullet Punch
BOOSTED_CC_TARGETS = SCIZOR_SETUP_TARGETS | {"Tyranitar", "Ferrothorn"}

# Sand chip: bring Tyranitar (Sand Stream) to finish a low foe with sand damage.
# Sand does 1/16 (~6%) per turn. Rock, Steel and Ground types take no sand damage.
SAND_CHIP_HP = 20
SAND_IMMUNE = {"Rock", "Steel", "Ground"}

# Damage estimates (% of target's max HP, min-max roll), from damage calcs.
# Used for "will I survive / will I KO" checks. Add matchups here.
DAMAGE = {
    # 252+ Atk Life Orb Garchomp EQ vs 252 HP / 0+ Def Tyranitar
    ("Garchomp", "Earthquake", "Tyranitar"):       (97.2, 114.6),
    # 252 Atk Tyranitar Ice Punch vs 0 HP / 0 Def Garchomp
    ("Tyranitar", "Ice Punch", "Garchomp"):        (98.5, 116.5),
}


# Togekiss: Tyranitar Rock Slides, and only switches to Scizor once Togekiss
# shows Aura Sphere. The bot can't see opposing moves, so it infers Aura Sphere
# from a big HP drop on Tyranitar in one turn vs Togekiss.
# PLACEHOLDER: set this between Dazzling Gleam's max and Aura Sphere's min.
AURA_SPHERE_HP_DROP = 35


def stage_mult(stage):
    """Stat stage -> multiplier (+1 = 1.5x, +2 = 2x, -1 = 0.67x)."""
    return (2 + stage) / 2 if stage >= 0 else 2 / (2 - stage)


def survives(my_hp, attacker, move, target, atk_boost=0):
    """True if my_hp is above the attacker's max roll (scaled by its boosts)."""
    dmg = DAMAGE.get((attacker, move, target))
    if not dmg:
        return None  # unknown matchup
    return my_hp > dmg[1] * stage_mult(atk_boost)

# Our side, used to score switch-ins type-wise
OUR_TEAM = {
    DRAGAPULT: {"types": ["Dragon", "Ghost"], "attacks": ["Dragon", "Ghost", "Fire", "Bug"]},
    SCIZOR:    {"types": ["Bug", "Steel"],    "attacks": ["Steel", "Bug", "Fighting"]},
    TYRANITAR: {"types": ["Rock", "Dark"],    "attacks": ["Dark", "Rock", "Ice", "Ground"]},
}

# Attacking type -> defending types that aren't 1x
TYPE_CHART = {
    "Normal":   {"Rock": .5, "Ghost": 0, "Steel": .5},
    "Fire":     {"Fire": .5, "Water": .5, "Grass": 2, "Ice": 2, "Bug": 2, "Rock": .5, "Dragon": .5, "Steel": 2},
    "Water":    {"Fire": 2, "Water": .5, "Grass": .5, "Ground": 2, "Rock": 2, "Dragon": .5},
    "Electric": {"Water": 2, "Electric": .5, "Grass": .5, "Ground": 0, "Flying": 2, "Dragon": .5},
    "Grass":    {"Fire": .5, "Water": 2, "Grass": .5, "Poison": .5, "Ground": 2, "Flying": .5,
                 "Bug": .5, "Rock": 2, "Dragon": .5, "Steel": .5},
    "Ice":      {"Fire": .5, "Water": .5, "Grass": 2, "Ice": .5, "Ground": 2, "Flying": 2, "Dragon": 2, "Steel": .5},
    "Fighting": {"Normal": 2, "Ice": 2, "Poison": .5, "Flying": .5, "Psychic": .5, "Bug": .5, "Rock": 2,
                 "Ghost": 0, "Dark": 2, "Steel": 2, "Fairy": .5},
    "Poison":   {"Grass": 2, "Poison": .5, "Ground": .5, "Rock": .5, "Ghost": .5, "Steel": 0, "Fairy": 2},
    "Ground":   {"Fire": 2, "Electric": 2, "Grass": .5, "Poison": 2, "Flying": 0, "Bug": .5, "Rock": 2, "Steel": 2},
    "Flying":   {"Electric": .5, "Grass": 2, "Fighting": 2, "Bug": 2, "Rock": .5, "Steel": .5},
    "Psychic":  {"Fighting": 2, "Poison": 2, "Psychic": .5, "Dark": 0, "Steel": .5},
    "Bug":      {"Fire": .5, "Grass": 2, "Fighting": .5, "Poison": .5, "Flying": .5, "Psychic": 2,
                 "Ghost": .5, "Dark": 2, "Steel": .5, "Fairy": .5},
    "Rock":     {"Fire": 2, "Ice": 2, "Fighting": .5, "Ground": .5, "Flying": 2, "Bug": 2, "Steel": .5},
    "Ghost":    {"Normal": 0, "Psychic": 2, "Ghost": 2, "Dark": .5},
    "Dragon":   {"Dragon": 2, "Steel": .5, "Fairy": 0},
    "Dark":     {"Fighting": .5, "Psychic": 2, "Ghost": 2, "Dark": .5, "Fairy": .5},
    "Steel":    {"Fire": .5, "Water": .5, "Electric": .5, "Ice": 2, "Rock": 2, "Steel": .5, "Fairy": 2},
    "Fairy":    {"Fire": .5, "Fighting": 2, "Poison": .5, "Dragon": 2, "Dark": 2, "Steel": .5},
}


def effectiveness(atk_type, def_types):
    mult = 1.0
    for t in def_types:
        mult *= TYPE_CHART.get(atk_type, {}).get(t, 1.0)
    return mult


# Native L100 max HP, used to turn raw HP into a percentage for entries that
# carry no "condition" (foe and bench). Own side and foe side are separate
# because Scizor/Tyranitar/Dragapult appear on both with different builds.
# Foe values are the portal's default builds; only some were seen on the portal.
OWN_MAXHP = {"Scizor": 281, "Tyranitar": 404, "Dragapult": 317}
FOE_MAXHP = {"Garchomp": 357, "Dragonite": 323, "Tyranitar": 404,
    "Metagross": 364, "Salamence": 331, "Hydreigon": 325, "Dragapult": 317,
    "Volcarona": 311, "Lucario": 281, "Scizor": 344, "Gengar": 261,
    "Gyarados": 331, "Charizard": 297, "Blastoise": 362, "Venusaur": 364,
    "Arcanine": 384, "Excadrill": 361, "Togekiss": 374, "Snorlax": 524,
    "Alakazam": 252, "Lapras": 464, "Corviknight": 400, "Ferrothorn": 352,
    "Greninja": 286}


def _parse_condition(cond):
    """'320/358', '320/358 brn' or '0 fnt' -> (current, max), or None."""
    try:
        first = str(cond).split()[0]
        if "/" in first:
            cur, mx = first.split("/")
            return float(cur), float(mx)
        if first == "0":
            return 0.0, None
    except Exception:
        pass
    return None


def _num(v):
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None


class PokemonAgent:
    def decide(self, observation: dict) -> str:
        """Platform entry point. Never raises, and only returns legal actions."""
        try:
            obs = observation if isinstance(observation, dict) else {}
            if obs.get("team_preview"):
                self._reset_memory()
                action = self._team_order(obs)
            else:
                obs = self._normalize_hp(obs)
                self._track(obs)
                action = self._decide(obs)
                self._remember(obs, action)
        except Exception:
            action = None
        return self._guard(observation, action)

    # ---------------- Safety net ----------------
    def _guard(self, observation, action):
        """Return action if it's legal, otherwise a safe legal one."""
        try:
            obs = observation if isinstance(observation, dict) else {}
            if obs.get("team_preview"):
                return action if isinstance(action, str) and action.startswith("team ") else "team 123"
            moves = [m for m in (obs.get("valid_moves") or []) if isinstance(m, dict) and not m.get("disabled")]
            switches = [s for s in (obs.get("valid_switches") or [])
                        if isinstance(s, dict) and not s.get("fainted") and not s.get("active")]
            legal = {f"move {m.get('index')}" for m in moves} | {f"switch {s.get('index')}" for s in switches}
            if not legal:
                return action if isinstance(action, str) and action else "pass"
            if action in legal:
                return action
            if obs.get("force_switch") and switches:
                return f"switch {switches[0].get('index')}"
            if moves:
                try:
                    best = self._fallback(moves)
                    if best in legal:
                        return best
                except Exception:
                    pass
                return f"move {moves[0].get('index')}"
            return f"switch {switches[0].get('index')}"
        except Exception:
            return "move 1"

    # ---------------- HP scale ----------------
    def _normalize_hp(self, obs):
        """Make every hp_percent a 0-100 percentage, whatever scale the
        platform sends: 0-100 (as documented), 0-1 fractions, or raw HP."""
        me = obs.get("my_active") or {}
        scale = None
        cond = _parse_condition(me.get("condition")) if me.get("condition") is not None else None
        hp = _num(me.get("hp_percent"))
        if cond and cond[1] and hp is not None:
            true_pct = 100.0 * cond[0] / cond[1]
            if abs(hp - true_pct) <= 1.5:
                scale = "percent"
            elif abs(hp * 100 - true_pct) <= 1.5:
                scale = "fraction"
            elif abs(hp - cond[0]) <= 1:
                scale = "raw"
        if scale is None:
            vals = []
            for mon in [me, obs.get("foe") or {}] + list(obs.get("my_team") or []) + list(obs.get("valid_switches") or []):
                if isinstance(mon, dict) and _num(mon.get("hp_percent")) is not None:
                    vals.append(mon["hp_percent"])
            if vals and max(vals) > 100:
                scale = "raw"
            elif vals and max(vals) <= 1 and any(v > 0 for v in vals):
                scale = "fraction"
            else:
                scale = "percent"
        if scale == "percent":
            return obs

        def fix(mon, table):
            if not isinstance(mon, dict) or _num(mon.get("hp_percent")) is None:
                return mon
            mon = dict(mon)
            c = _parse_condition(mon.get("condition")) if mon.get("condition") is not None else None
            if c and c[1]:
                mon["hp_percent"] = 100.0 * c[0] / c[1]
            elif scale == "fraction":
                mon["hp_percent"] = mon["hp_percent"] * 100
            else:  # raw HP, no condition: divide by the known max HP
                mx = table.get(str(mon.get("name") or "").strip().capitalize())
                if scale == "raw" and mx:
                    mon["hp_percent"] = min(100.0 * mon["hp_percent"] / mx, 100.0)
                else:
                    mon["hp_percent"] = min(mon["hp_percent"], 100)
            return mon

        obs = dict(obs)
        if "my_active" in obs:
            obs["my_active"] = fix(obs["my_active"], OWN_MAXHP)
        if "foe" in obs:
            obs["foe"] = fix(obs["foe"], FOE_MAXHP)
        for key in ("my_team", "valid_switches"):
            if isinstance(obs.get(key), list):
                obs[key] = [fix(m, OWN_MAXHP) for m in obs[key]]
        return obs

    # ---------------- Turn memory ----------------
    def _remember(self, obs, action):
        me = (obs.get("my_active") or {}).get("name")
        foe_name = (obs.get("foe") or {}).get("name")
        move = self._move_name(obs, action)
        # Greninja follow-up
        self._last_action = (me, foe_name, action, move)
        # Choice Band lock: Dragapult stays locked into the move it used
        # until it leaves the field.
        if me == DRAGAPULT and move:
            self._lock = move
        else:
            self._lock = None

    def _decide(self, observation):
        foe = observation.get("foe") or {}
        valid_moves = observation.get("valid_moves") or []
        valid_switches = observation.get("valid_switches") or []

        # Fainted, or a switch prompt after U-turn (no moves offered)
        # (A force_switch with nobody to switch to falls through to moves.)
        if valid_switches and (observation.get("force_switch") or not valid_moves):
            return self._pick_switch(observation, foe, valid_switches)

        active = (observation.get("my_active") or {}).get("name", "")

        action = None
        if active == DRAGAPULT:
            action = self._dragapult(observation, foe, valid_moves, valid_switches)
        elif active == SCIZOR:
            action = self._scizor(observation, foe, valid_moves, valid_switches)
        elif active == TYRANITAR:
            action = self._tyranitar(observation, foe, valid_moves, valid_switches)

        if action:
            return action
        return self._fallback(valid_moves)

    # ---------------- Battle memory ----------------
    # Only works if the platform keeps the same agent object between turns.
    # If it doesn't, these stay empty and the bot falls back to safe defaults.
    def _reset_memory(self):
        self._prev = None
        self._aura_sphere_seen = False
        self._last_action = None
        self._lock = None

    def _track(self, obs):
        if not hasattr(self, "_prev"):
            self._reset_memory()
        me = obs.get("my_active") or {}
        foe = obs.get("foe") or {}
        now = (me.get("name"), me.get("hp_percent", 100), foe.get("name"))
        if now[0] != DRAGAPULT:
            self._lock = None
        prev = self._prev
        if (prev and prev[0] == now[0] == TYRANITAR and prev[2] == now[2] == "Togekiss"
                and prev[1] - now[1] >= AURA_SPHERE_HP_DROP):
            self._aura_sphere_seen = True
        self._prev = now

    @staticmethod
    def _move_name(obs, action):
        if action and action.startswith("move "):
            for m in obs.get("valid_moves") or []:
                if f"move {m.get('index')}" == action:
                    return m.get("name")
        return None

    # ---------------- Team preview: Dragapult leads ----------------
    def _team_order(self, obs):
        names = [p.get("name") for p in (obs.get("my_team") or [])]
        if DRAGAPULT in names:
            lead = names.index(DRAGAPULT) + 1
            rest = [str(i + 1) for i in range(len(names)) if i + 1 != lead]
            return "team " + str(lead) + "".join(rest)
        return "team 123"

    # ---------------- Sand chip ----------------
    def _sand_chip(self, obs, foe, valid_switches):
        """Switch to Tyranitar if sand would finish a low foe."""
        if foe.get("hp_percent", 100) > SAND_CHIP_HP:
            return None
        if SAND_IMMUNE & set(foe.get("types", [])):
            return None
        if "sand" in str(obs.get("weather", "")).lower():
            return None  # sand is already up
        return self._switch_to(valid_switches, TYRANITAR)

    # ---------------- Dragapult ----------------
    def _dragapult(self, obs, foe, valid_moves, valid_switches):
        plan = self._dragapult_plan(obs, foe, valid_moves, valid_switches)

        # Choice Band lock: only one move offered, or the move Dragapult used
        # last turn (remembered, in case the platform lists all four)
        locked = valid_moves[0] if len(valid_moves) == 1 else None
        mem = getattr(self, "_lock", None)
        if locked is None and mem:
            locked = next((m for m in valid_moves if m.get("name") == mem and not m.get("disabled")), None)
        if locked is not None:
            if plan and (plan.startswith("switch") or plan == f"move {locked['index']}"):
                return plan
            if locked.get("type_multiplier", 1.0) >= 1:
                return f"move {locked['index']}"
            if valid_switches:
                return self._pick_switch(obs, foe, valid_switches)
            return f"move {locked['index']}"

        return plan

    def _dragapult_plan(self, obs, foe, valid_moves, valid_switches):
        name = foe.get("name", "")
        types = foe.get("types", [])

        # Fairy (Togekiss): U-turn. Immune to Dragon Darts; the follow-up
        # switch sends Scizor.
        if "Fairy" in types:
            uturn = self._move(valid_moves, "U-turn")
            if uturn:
                return uturn

        # Sand kills aren't chased here: they come from the switch-in logic
        # after a U-turn or a faint.
        return self._dragapult_type_move(types, valid_moves)

    def _dragapult_type_move(self, types, valid_moves):
        # Order matters for dual types:
        # Dragon first  -> Dark/Dragon and Dragon/Ghost get Darts
        # Ghost/Psychic before Steel -> Steel/Psychic gets Phantom Force
        if "Dragon" in types:
            return self._move(valid_moves, "Dragon Darts")
        if "Ghost" in types or "Psychic" in types:
            return self._move(valid_moves, "Phantom Force")
        if "Dark" in types:
            return self._move(valid_moves, "U-turn")
        if "Steel" in types or "Grass" in types:
            return self._move(valid_moves, "Flamethrower")
        return self._move(valid_moves, "Dragon Darts")  # neutral

    # ---------------- Scizor ----------------
    def _scizor(self, obs, foe, valid_moves, valid_switches):
        name = foe.get("name", "")
        types = foe.get("types", [])
        atk = ((obs.get("my_active") or {}).get("boosts") or {}).get("atk", 0)
        foe_hp = foe.get("hp_percent", 100)

        # Fire: Scizor is 4x weak, switch to Tyranitar
        if "Fire" in types:
            sw = self._switch_to(valid_switches, TYRANITAR)
            if sw:
                return sw

        # Gyarados (resists everything Scizor has), boosted or not: U-turn into
        # Dragapult if alive (the switch-in chain sends Dragapult), otherwise
        # stay and use Close Combat.
        if name == "Gyarados":
            if self._switch_to(valid_switches, DRAGAPULT):
                uturn = self._move(valid_moves, "U-turn")
                if uturn:
                    return uturn
            cc = self._move(valid_moves, "Close Combat")
            if cc:
                return cc

        # Boosted (Fire is already handled above): Bullet Punch, so priority
        # gets the boosted hit in first, even if Scizor goes down after.
        # Lapras, Snorlax, Tyranitar and Ferrothorn get Close Combat instead.
        # If the foe resists Bullet Punch (Steel, Water), pick by type instead;
        # Greninja keeps Bullet Punch, where priority matters most.
        if atk > 0:
            if name in BOOSTED_CC_TARGETS:
                cc = self._move(valid_moves, "Close Combat")
                if cc:
                    return cc
            bp = next((m for m in valid_moves if m.get("name") == "Bullet Punch" and not m.get("disabled")), None)
            if bp and (bp.get("type_multiplier", 1.0) >= 1 or name == "Greninja"):
                return f"move {bp['index']}"
            return self._type_wise(valid_moves, self.SCIZOR_POWER)

        # Garchomp: U-turn out to Dragapult, or to Tyranitar while its Focus
        # Sash is intact (it comes in free, survives EQ, trades with Ice Punch).
        # Otherwise Scizor stays and fights.
        if name == "Garchomp" and (
            self._switch_to(valid_switches, DRAGAPULT) or self._ttar_sash_ready(valid_switches)
        ):
            uturn = self._move(valid_moves, "U-turn")
            if uturn:
                return uturn

        # Greninja, unboosted: above 85% HP U-turn (Dragapult follows).
        # 85% or below: Bullet Punch; if Scizor survives, switch to Dragapult.
        # A boosted Greninja gets no special handling.
        if name == "Greninja" and not any((foe.get("boosts") or {}).values()):
            my_hp = (obs.get("my_active") or {}).get("hp_percent", 100)
            if my_hp > 85:
                uturn = self._move(valid_moves, "U-turn")
                if uturn:
                    return uturn
            else:
                last = getattr(self, "_last_action", None)
                if last and last[0] == SCIZOR and last[1] == "Greninja" and last[3] == "Bullet Punch":
                    sw = self._switch_to(valid_switches, DRAGAPULT)
                    if sw:
                        return sw
                bp = self._move(valid_moves, "Bullet Punch")
                if bp:
                    return bp

        # Possible Focus Sash (Venusaur) at full HP: U-turn out.
        # Follow-up goes to Dragapult, else Tyranitar.
        if name in SCIZOR_PIVOT_IF_FULL and foe_hp >= 100:
            uturn = self._move(valid_moves, "U-turn")
            if uturn:
                return uturn

        # Tyranitar: Close Combat (4x vs Rock/Dark)
        if name == "Tyranitar":
            return self._move(valid_moves, "Close Combat")

        # Weak to Steel, Scizor at +0, foe at 70% or less: Bullet Punch.
        if atk == 0 and foe_hp <= 70:
            for m in valid_moves:
                if m.get("name") == "Bullet Punch" and m.get("type_multiplier", 1.0) >= 2:
                    return f"move {m['index']}"

        # Lapras, Snorlax: one Swords Dance (+2), then attack
        if name in SCIZOR_SETUP_TARGETS and atk == 0:
            sd = self._move(valid_moves, "Swords Dance")
            if sd:
                return sd

        # Fairy: Bullet Punch (2x, priority, can't be flinched)
        if "Fairy" in types:
            return self._move(valid_moves, "Bullet Punch")

        # Everything else: type-wise
        return self._type_wise(valid_moves, self.SCIZOR_POWER)

    # ---------------- Tyranitar ----------------
    def _tyranitar(self, obs, foe, valid_moves, valid_switches):
        my_active = obs.get("my_active") or {}
        name = foe.get("name", "")
        # Lucario: Fighting hits Tyranitar 4x. Switch to Dragapult
        # (immune to Fighting and Extreme Speed), else Scizor.
        # If both are down, stay and fall through to type-wise (Earthquake).
        if name == "Lucario":
            sw = self._switch_to(valid_switches, DRAGAPULT) or self._switch_to(valid_switches, SCIZOR)
            if sw:
                return sw

        # Garchomp: outspeeds, and Life Orb EQ OHKOs Tyranitar (97.2-114.6%).
        # Sash intact: survive at 1 HP, then Ice Punch. Life Orb recoil has
        # taken Garchomp to 90% or less, under Ice Punch's 98.5% min roll, so
        # it's a guaranteed KO. Rough Skin then KOs Tyranitar: a 1-for-1 trade.
        # Sash gone: switch to Dragapult, else Scizor; stay only as the last one.
        if name == "Garchomp":
            if self._sash_intact(my_active):
                ice = self._move(valid_moves, "Ice Punch")
                if ice:
                    return ice
            sw = self._switch_to(valid_switches, DRAGAPULT) or self._switch_to(valid_switches, SCIZOR)
            if sw:
                return sw

        # Togekiss: Rock Slide. Switch to Scizor only once it has shown Aura Sphere.
        if name == "Togekiss":
            if getattr(self, "_aura_sphere_seen", False):
                sw = self._switch_to(valid_switches, SCIZOR)
                if sw:
                    return sw
            rock = self._move(valid_moves, "Rock Slide")
            if rock:
                return rock

        # Metagross: Crunch over Earthquake
        if name == "Metagross":
            crunch = self._move(valid_moves, "Crunch")
            if crunch:
                return crunch

        mult = {m.get("name"): m.get("type_multiplier", 1.0) for m in valid_moves}
        eq = mult.get("Earthquake", 0)

        # Weak to both Ground and Rock: Rock Slide
        if eq >= 2 and mult.get("Rock Slide", 0) >= 2:
            return self._move(valid_moves, "Rock Slide")

        # Only weak to Ground among our moves: neutral hit first (pops a
        # possible Air Balloon), then Earthquake once the foe is below 100%.
        if eq >= 2 and not any(mult.get(n, 0) >= 2 for n in ("Crunch", "Rock Slide", "Ice Punch")):
            if foe.get("hp_percent", 100) >= 100:
                others = [m for m in valid_moves
                          if m.get("name") in self.TYRANITAR_POWER and m.get("name") != "Earthquake"
                          and m.get("type_multiplier", 1.0) > 0 and not m.get("disabled")]
                if others:
                    best = max(others, key=lambda m: (m.get("type_multiplier", 1.0) == 1,
                                                       self.TYRANITAR_POWER[m["name"]]))
                    return f"move {best['index']}"
            return self._move(valid_moves, "Earthquake")

        # TODO: more Tyranitar exceptions go here
        return self._type_wise(valid_moves, self.TYRANITAR_POWER)

    @staticmethod
    def _sash_intact(mon):
        """Focus Sash only works from full HP. If the platform reports our item,
        use it; otherwise assume it's intact while Tyranitar is at 100%
        (Tyranitar takes no sand damage, so any HP loss means it was hit)."""
        mon = mon or {}
        if mon.get("item") is not None:
            return "sash" in str(mon.get("item")).lower() and mon.get("hp_percent", 0) >= 100
        return mon.get("hp_percent", 0) >= 100

    def _ttar_sash_ready(self, valid_switches):
        """Tyranitar is on the bench with its Focus Sash intact."""
        for s in valid_switches:
            if s.get("name") == TYRANITAR and not s.get("fainted"):
                return self._sash_intact(s)
        return False

    # Effective power before type effectiveness (STAB and items included)
    # Bullet Punch 40 x1.5 Technician x1.5 STAB x1.2 Metal Coat = 108
    SCIZOR_POWER = {"Bullet Punch": 108, "U-turn": 105, "Close Combat": 120}
    # Crunch 80 x1.5 STAB, Rock Slide 75 x1.5 STAB, Earthquake 100, Ice Punch 75
    TYRANITAR_POWER = {"Crunch": 120, "Rock Slide": 112, "Earthquake": 100, "Ice Punch": 75}

    @staticmethod
    def _type_wise(valid_moves, power):
        """Highest type multiplier wins; ties go to the harder hit."""
        attacks = [m for m in valid_moves if m.get("name") in power and not m.get("disabled")]
        if not attacks:
            return None
        best = max(attacks, key=lambda m: (m.get("type_multiplier", 1.0), power[m["name"]]))
        if best.get("type_multiplier", 1.0) == 0:
            return None  # everything is immune: let the fallback handle it
        return f"move {best['index']}"

    # ---------------- Switching ----------------
    def _pick_switch(self, obs, foe, valid_switches):
        if not valid_switches:
            return "pass"
        name = foe.get("name", "")
        types = foe.get("types", [])

        # 1. Fire: Tyranitar (Scizor is 4x weak)
        if "Fire" in types:
            sw = self._switch_to(valid_switches, TYRANITAR)
            if sw:
                return sw
        # 2. Garchomp: Dragapult (outspeeds, 2x Darts), else Tyranitar with its
        #    Focus Sash intact (trades via Ice Punch), else Scizor.
        if name == "Garchomp":
            sw = (self._switch_to(valid_switches, DRAGAPULT)
                  or (self._switch_to(valid_switches, TYRANITAR) if self._ttar_sash_ready(valid_switches) else None)
                  or self._switch_to(valid_switches, SCIZOR))
            if sw:
                return sw
        # 2b. Lucario: Dragapult, else Scizor (never Tyranitar, 4x weak to Fighting)
        if name == "Lucario":
            sw = self._switch_to(valid_switches, DRAGAPULT) or self._switch_to(valid_switches, SCIZOR)
            if sw:
                return sw
        # 3. Fairy: Scizor
        if "Fairy" in types:
            sw = self._switch_to(valid_switches, SCIZOR)
            if sw:
                return sw
        # 4. Low foe that sand can finish: Tyranitar
        sand = self._sand_chip(obs, foe, valid_switches)
        if sand:
            return sand
        # 5. Gyarados: Dragapult (else the type score decides)
        if name == "Gyarados":
            sw = self._switch_to(valid_switches, DRAGAPULT)
            if sw:
                return sw
        # 6. Greninja / Venusaur: Dragapult, else Tyranitar (never Scizor)
        if name in PIVOT_TARGETS:
            sw = self._switch_to(valid_switches, DRAGAPULT) or self._switch_to(valid_switches, TYRANITAR)
            if sw:
                return sw

        # 7. Type-wise: best (our attack vs them) minus (their STAB vs us), then HP
        def score(s):
            info = OUR_TEAM.get(s.get("name"))
            if not info:
                return (-99, s.get("hp_percent", 0))
            offense = max(effectiveness(a, types) for a in info["attacks"])
            danger = max((effectiveness(t, info["types"]) for t in types), default=1.0)
            return (offense - danger, s.get("hp_percent", 0))

        best = max(valid_switches, key=score)
        return f"switch {best['index']}"

    # ---------------- Helpers ----------------
    @staticmethod
    def _move(valid_moves, move_name):
        for m in valid_moves:
            if m.get("name") == move_name and not m.get("disabled"):
                return f"move {m['index']}"
        return None

    @staticmethod
    def _switch_to(valid_switches, mon_name):
        for s in valid_switches:
            if s.get("name") == mon_name and not s.get("fainted") and not s.get("active"):
                return f"switch {s['index']}"
        return None

    @staticmethod
    def _fallback(valid_moves):
        attacks = [m for m in valid_moves if (m.get("base_power") or 0) > 0]
        if attacks:
            best = max(
                attacks,
                key=lambda m: (m.get("base_power") or 0)
                * m.get("type_multiplier", 1.0)
                * (1.5 if m.get("stab") else 1.0),
            )
            return f"move {best['index']}"
        if valid_moves:
            return f"move {valid_moves[0]['index']}"
        return "pass"
